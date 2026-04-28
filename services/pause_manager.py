"""暫停狀態管理器，統一管理各種暫停與休假狀態。"""
from collections.abc import Callable
from typing import Any

from core.events import Events
from services.config_service import ConfigManager


class PauseManager:
    """暫停狀態管理服務。"""

    def __init__(self, config_manager: ConfigManager, notify_callback: Callable[[str, Any], None]):
        """
        初始化暫停管理器。

        Args:
            config_manager: 設定管理器
            notify_callback: 通知回調函數 (event, *args)
        """
        self.config_manager = config_manager
        self.notify = notify_callback

    @property
    def config(self) -> dict[str, Any]:
        return self.config_manager.load_config()

    def get_pause_state(self, key: str, config: dict[str, Any] | None = None) -> bool:
        """
        取得指定功能的暫停狀態。

        Args:
            key: 暫停類型
            config: 可選的設定快照；未提供時才從 ConfigManager 讀取
        """
        config_data = config if config is not None else self.config
        if key == 'reminder':
            return config_data.get('reminder_paused', False)
        elif key == 'hourly_web':
            return config_data.get('hourly_web_reminder', {}).get('paused', False)
        elif key == 'vacation':
            return config_data.get('on_vacation', False)
        return False

    def set_pause_state(self, key: str, paused: bool) -> None:
        """設定指定功能的暫停狀態。"""
        config = self.config
        event_map = {
            'reminder': ('reminder_paused', Events.REMINDER_PAUSE_TOGGLED),
            'hourly_web': (None, Events.HOURLY_WEB_PAUSE_TOGGLED),
            'vacation': ('on_vacation', Events.VACATION_TOGGLED),
        }

        if key not in event_map:
            return

        if key == 'hourly_web':
            if 'hourly_web_reminder' not in config:
                config['hourly_web_reminder'] = {}
            config['hourly_web_reminder']['paused'] = paused
        else:
            config_key, _ = event_map[key]
            config[config_key] = paused

        self.config_manager.save_config(config)

        # 通知
        _, event = event_map[key]
        self.notify(event, paused)

    def toggle_pause(self, key: str) -> None:
        """切換指定功能的暫停狀態。"""
        new_paused = not self.get_pause_state(key)
        self.set_pause_state(key, new_paused)

    def toggle_vacation(self, pomodoro_stop_callback: Callable[[], None]) -> None:
        """
        切換休假模式。

        Args:
            pomodoro_stop_callback: 用於停止番茄鐘的回調函數
        """
        new_vacation = not self.get_pause_state('vacation')
        config = self.config

        if new_vacation:
            # 開始休假: 停止番茄鐘、記住並暫停提醒
            pomodoro_stop_callback()
            config['vacation_previous_state'] = {
                'reminder_paused': self.get_pause_state('reminder'),
                'hourly_web_paused': self.get_pause_state('hourly_web')
            }
            self.config_manager.save_config(config) # 先儲存狀態

            if not self.get_pause_state('reminder'):
                self.set_pause_state('reminder', True)
            if not self.get_pause_state('hourly_web'):
                self.set_pause_state('hourly_web', True)
        else:
            # 結束休假: 恢復之前的狀態
            prev = config.get('vacation_previous_state', {})
            if not prev.get('reminder_paused', False) and self.get_pause_state('reminder'):
                self.set_pause_state('reminder', False)
            if not prev.get('hourly_web_paused', False) and self.get_pause_state('hourly_web'):
                self.set_pause_state('hourly_web', False)

        self.set_pause_state('vacation', new_vacation)
