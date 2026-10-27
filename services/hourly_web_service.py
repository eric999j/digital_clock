"""整點啟動服務，負責整點開啟網頁或啟動程式。"""
import logging
import webbrowser
from collections.abc import Callable
from datetime import datetime
from typing import Any

from services.config_service import ConfigManager

logger = logging.getLogger(__name__)
from core.events import Events
from core.launch_rules import RULE_PROGRAM, RULE_URL, rule_target, rule_type
from core.program_launcher import LaunchError, launch_program
from core.url_validator import is_safe_url
from strategies.hourly_web_strategy import HourlyWebReminderStrategy


class HourlyWebService:
    """處理整點啟動（網頁與程式）的邏輯。"""

    def __init__(self, config_manager: ConfigManager, notify_callback: Callable[[str, Any], None]):
        """
        初始化整點啟動服務。

        Args:
            config_manager: 設定管理器
            notify_callback: 通知回調函數 (event, *args)
        """
        self.config_manager = config_manager
        self.notify = notify_callback
        self.strategy = HourlyWebReminderStrategy()

    @property
    def config(self) -> dict[str, Any]:
        return self.config_manager.load_config()

    def update_config(self, url_rules: list[dict]) -> None:
        """更新整點啟動規則，並將第一筆網頁規則同步到 url/start_hour/end_hour 供舊版相容。"""
        config = self.config
        hw = config.setdefault('hourly_web_reminder', {})
        hw['url_rules'] = url_rules
        first_url_rule = next((r for r in url_rules if rule_type(r) == RULE_URL), None)
        if first_url_rule:
            hw['url'] = first_url_rule['url']
            hw['start_hour'] = first_url_rule['start_hour']
            hw['end_hour'] = first_url_rule['end_hour']
        else:
            # 清空舊欄位，避免規則刪光後策略退回舊版單一 URL 而復活
            hw['url'] = ''
        self.config_manager.save_config(config)
        self.notify(Events.HOURLY_WEB_UPDATED, None)

    def check(self, now: datetime | None = None, config: dict[str, Any] | None = None) -> None:
        """
        檢查是否需要觸發整點啟動。

        Args:
            now: 可選的當前時間快照
            config: 可選的設定快照；未提供時才從 ConfigManager 讀取
        """
        # 暫停邏輯需由呼叫者或 PauseManager 處理，這裡僅檢查時間與設定
        # 但 Strategy 中包含了檢查 'paused' 屬性的邏輯
        current_time = now if now is not None else datetime.now()
        config_data = config if config is not None else self.config
        hourly_config = config_data.get('hourly_web_reminder', {})

        rules = self.strategy.check(hourly_config, current_time)
        if not rules:
            return

        opened_any = False
        for rule in rules:
            if rule_type(rule) == RULE_PROGRAM:
                self._launch_rule_program(rule)
            elif self._open_url(rule_target(rule)):
                opened_any = True

        if opened_any:
            self._bring_browser_to_front()

    def _open_url(self, url: str) -> bool:
        if not is_safe_url(url):
            logger.warning("Refusing to open URL with unsupported scheme: %r", url)
            return False
        try:
            webbrowser.open(url, new=2)
            self.notify(Events.HOURLY_WEB_DUE, url)
            return True
        except Exception as e:
            logger.error("Error opening URL: %s", e)
            return False

    def _launch_rule_program(self, rule: dict[str, Any]) -> None:
        command = rule_target(rule)
        try:
            launch_program(command, rule.get('arguments', ''), rule.get('working_dir', ''))
            self.notify(Events.HOURLY_WEB_DUE, command)
        except LaunchError as e:
            logger.error("Hourly launch failed: %s", e)

    def _bring_browser_to_front(self) -> None:
        """嘗試將瀏覽器視窗帶到最前面（僅 Windows）。"""
        import sys
        if sys.platform != "win32":
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.AllowSetForegroundWindow(user32.GetCurrentProcessId())
        except Exception as e:
            logger.debug("AllowSetForegroundWindow failed: %s", e)
