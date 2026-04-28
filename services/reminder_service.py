"""提醒服務，負責管理和檢查提醒。"""
from collections.abc import Callable
from datetime import datetime
from typing import Any

from core.events import Events
from services.config_service import ConfigManager
from strategies.reminder_strategy import ReminderStrategy


class ReminderService:
    """處理提醒的新增、刪除、檢查與過期清理。"""

    def __init__(self, config_manager: ConfigManager, notify_callback: Callable[[str, Any], None]):
        """
        初始化提醒服務。

        Args:
            config_manager: 設定管理器
            notify_callback: 通知回調函數 (event, *args)
        """
        self.config_manager = config_manager
        self.notify = notify_callback
        self.strategy = ReminderStrategy()

    @property
    def config(self) -> dict[str, Any]:
        return self.config_manager.load_config()

    def add_reminder(self, time_data: Any, message: str, weekdays: list[str], original_reminder: dict[str, Any] | None = None, title: str = "") -> None:
        """新增或更新提醒。"""
        is_update = original_reminder is not None

        if is_update:
            self.delete_reminder(original_reminder, notify=False)

        if weekdays:
            # 週期性提醒
            reminder_data = {
                "time": time_data,
                "message": message,
                "weekdays": weekdays,
                "title": title
            }
        else:
            # 單次提醒
            reminder_data = {
                "datetime": time_data.strftime('%Y-%m-%d %H:%M:%S'),
                "message": message,
                "weekdays": [],
                "title": title
            }

        config = self.config
        if 'reminders' not in config:
            config['reminders'] = []

        config['reminders'].append(reminder_data)
        config['reminders'] = sorted(
            config['reminders'],
            key=lambda r: r.get('datetime') or r.get('time')
        )
        self.config_manager.save_config(config)

        if is_update:
            self.notify(Events.REMINDER_UPDATED, reminder_data)
        else:
            self.notify(Events.REMINDER_ADDED, reminder_data)

    def delete_reminder(self, reminder_to_delete: dict[str, Any], notify: bool = True) -> None:
        """
        刪除提醒。

        以「全欄位相等」做比對，僅移除第一筆相符的提醒；如有多筆完全重複的提醒，
        其餘不會被誤刪。
        """
        config = self.config
        reminders = config.get('reminders', [])
        for idx, existing in enumerate(reminders):
            if existing == reminder_to_delete:
                del reminders[idx]
                self._save_config(config)
                if notify:
                    self.notify(Events.REMINDER_DELETED, reminder_to_delete)
                return

    def check_reminders(
        self,
        is_paused: bool,
        now: datetime | None = None,
        config: dict[str, Any] | None = None
    ) -> None:
        """
        檢查提醒。

        Args:
            is_paused: 是否暫停提醒
            now: 可選的當前時間快照
            config: 可選的設定快照；未提供時才從 ConfigManager 讀取
        """
        if is_paused:
            return

        current_time = now if now is not None else datetime.now()
        config_data = config if config is not None else self.config
        reminders = config_data.get('reminders', [])
        time_format = config_data.get('appearance', {}).get('time_formats', {}).get('24h', '%H:%M')
        triggered_reminders = self.strategy.check(reminders, current_time, time_format=time_format)

        reminders_to_delete = []
        for reminder in triggered_reminders:
            self.notify(Events.REMINDER_DUE, reminder)
            # 只刪除單次提醒
            if not reminder.get('weekdays'):
                reminders_to_delete.append(reminder)

        if reminders_to_delete:
            for reminder in reminders_to_delete:
                if reminder in config_data.get('reminders', []):
                    config_data['reminders'].remove(reminder)
            self._save_config(config_data)

    def remove_expired_reminders(self) -> None:
        """移除過期提醒。"""
        now = datetime.now()
        config = self.config
        reminders = config.get('reminders', [])
        original_count = len(reminders)

        active_reminders = []
        for r in reminders:
            if r.get('weekdays'): # 保留週期性提醒
                active_reminders.append(r)
            elif 'datetime' in r and datetime.strptime(r['datetime'], '%Y-%m-%d %H:%M:%S') > now:
                active_reminders.append(r)

        if len(active_reminders) < original_count:
            config['reminders'] = active_reminders
            self._save_config(config)

    def _save_config(self, config: dict[str, Any]) -> None:
        """儲存設定。"""
        self.config_manager.save_config(config)
