"""整點網頁服務，負責整點網頁提醒。"""
import logging
import webbrowser
from collections.abc import Callable
from datetime import datetime
from typing import Any

from services.config_service import ConfigManager

logger = logging.getLogger(__name__)
from core.events import Events
from core.url_validator import is_safe_url
from strategies.hourly_web_strategy import HourlyWebReminderStrategy


class HourlyWebService:
    """處理整點網頁提醒的邏輯。"""

    def __init__(self, config_manager: ConfigManager, notify_callback: Callable[[str, Any], None]):
        """
        初始化整點網頁服務。

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
        """更新整點網頁設定，並將第一樢記錄到 url/start_hour/end_hour 供舊版相容。"""
        config = self.config
        hw = config.setdefault('hourly_web_reminder', {})
        hw['url_rules'] = url_rules
        if url_rules:
            hw['url'] = url_rules[0]['url']
            hw['start_hour'] = url_rules[0]['start_hour']
            hw['end_hour'] = url_rules[0]['end_hour']
        self.config_manager.save_config(config)
        self.notify(Events.HOURLY_WEB_UPDATED, None)

    def check(self, now: datetime | None = None, config: dict[str, Any] | None = None) -> None:
        """
        檢查是否需要觸發整點網頁提醒。

        Args:
            now: 可選的當前時間快照
            config: 可選的設定快照；未提供時才從 ConfigManager 讀取
        """
        # 暫停邏輯需由呼叫者或 PauseManager 處理，這裡僅檢查時間與設定
        # 但 Strategy 中包含了檢查 'paused' 屬性的邏輯
        current_time = now if now is not None else datetime.now()
        config_data = config if config is not None else self.config
        hourly_config = config_data.get('hourly_web_reminder', {})

        urls = self.strategy.check(hourly_config, current_time)
        if not urls:
            return

        opened_any = False
        for url in urls:
            if not is_safe_url(url):
                logger.warning("Refusing to open URL with unsupported scheme: %r", url)
                continue
            try:
                webbrowser.open(url, new=2)
                self.notify(Events.HOURLY_WEB_DUE, url)
                opened_any = True
            except Exception as e:
                logger.error("Error opening URL: %s", e)

        if opened_any:
            self._bring_browser_to_front()

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
