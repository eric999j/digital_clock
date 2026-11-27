"""ClockLogic 對 UI 暴露的相容代理介面。"""
from datetime import datetime
from typing import Any

from core.events import Events
from services.timezone_service import ZoneTime


class ClockLogicFacade:
    """將 UI-facing 方法與 ClockLogic 的服務協調與生命週期分離。"""

    def add_reminder(
        self,
        time_data: Any,
        message: str,
        weekdays: list[str],
        original_reminder: dict[str, Any] | None = None,
        title: str = "",
        allow_during_quiet: bool = False,
    ) -> None:
        self.reminder_service.add_reminder(
            time_data,
            message,
            weekdays,
            original_reminder,
            title,
            allow_during_quiet,
        )

    def delete_reminder(
        self,
        reminder_to_delete: dict[str, Any],
        notify: bool = True,
    ) -> None:
        self.reminder_service.delete_reminder(reminder_to_delete, notify)

    def get_snooze_options(self) -> tuple[int, ...]:
        """回傳提醒彈窗可選的「稍後提醒」分鐘數。"""
        return self.reminder_service.SNOOZE_OPTIONS_MINUTES

    def snooze_reminder(
        self,
        reminder: dict[str, Any],
        minutes: int,
    ) -> None:
        """將已觸發的提醒延後指定分鐘再提醒。"""
        self.reminder_service.snooze_reminder(reminder, minutes)

    def start_countdown(self, seconds: int, label: str = "") -> None:
        """開始（或取代）倒數計時。"""
        self.countdown_service.start(seconds, label)

    def toggle_countdown_pause(self) -> None:
        """暫停或繼續倒數計時。"""
        self.countdown_service.toggle_pause()

    def cancel_countdown(self) -> None:
        """取消倒數計時。"""
        self.countdown_service.cancel()

    def open_countdown_window(self) -> None:
        """請求 UI 開啟自訂倒數視窗（透過事件解耦）。"""
        self.notify_observers(Events.OPEN_COUNTDOWN_WINDOW)

    def get_zone_times(self, now: datetime | None = None) -> list[ZoneTime]:
        """取得已選時區的目前時間，供 UI 顯示。"""
        return self.timezone_service.get_zone_times(
            now, self.config_manager.load_config(read_only=True)
        )

    def toggle_timezone(self, key: str) -> bool:
        """切換時區顯示；回傳切換後是否為已選。"""
        return self.timezone_service.toggle_zone(key)

    def get_timezone_choices(self) -> tuple[dict[str, str], list[str]]:
        """回傳可用時區與已選時區。"""
        return (
            self.timezone_service.available_zones(),
            self.timezone_service.get_selected(),
        )

    def check_reminders(self, now: datetime | None = None) -> None:
        """將每秒功能檢查委派給協調器。"""
        self.check_coordinator.check(now)

    def update_hourly_web_reminder(
        self,
        url_rules: list[dict],
        work_days_only: bool | None = None,
    ) -> None:
        self.hourly_service.update_config(url_rules, work_days_only)

    def toggle_hourly_web_pause(self) -> None:
        self.pause_manager.toggle_pause("hourly_web")

    def is_hourly_web_paused(self) -> bool:
        return self.pause_manager.get_pause_state("hourly_web")

    def toggle_reminder_pause(self) -> None:
        self.pause_manager.toggle_pause("reminder")

    def is_reminder_paused(self) -> bool:
        return self.pause_manager.get_pause_state("reminder")

    def toggle_vacation(self) -> None:
        self.pause_manager.toggle_vacation()

    def is_on_vacation(self) -> bool:
        return self.pause_manager.get_pause_state("vacation")

    def add_vacation_schedule(
        self,
        start: str,
        end: str,
        note: str = "",
    ) -> None:
        """新增休假排程。"""
        self.vacation_schedule_service.add_schedule(start, end, note)

    def delete_vacation_schedule(self, schedule: dict[str, Any]) -> None:
        """刪除休假排程。"""
        self.vacation_schedule_service.delete_schedule(schedule)

    def update_vacation_schedule(
        self,
        schedule: dict[str, Any],
        start: str,
        end: str,
        note: str = "",
    ) -> None:
        """更新休假排程。"""
        self.vacation_schedule_service.update_schedule(schedule, start, end, note)

    def list_vacation_schedules(self) -> list[dict[str, Any]]:
        """列出所有休假排程。"""
        return self.vacation_schedule_service.list_schedules()

    def open_vacation_schedule_window(self) -> None:
        """請求 UI 開啟休假排程設定視窗。"""
        self.notify_observers(Events.OPEN_VACATION_SCHEDULE_WINDOW)

    def open_calendar_sync_window(self) -> None:
        """請求 UI 開啟行事曆同步設定視窗。"""
        self.notify_observers(Events.OPEN_CALENDAR_SYNC_WINDOW)

    def get_calendar_sync_settings(self) -> dict[str, Any]:
        """取得行事曆同步設定。"""
        return self.calendar_sync_service.get_settings()

    def update_calendar_sync_settings(
        self,
        enabled: bool,
        ics_url: str,
        refresh_minutes: int,
        lead_minutes: int,
        show_in_meeting: bool = True,
    ) -> None:
        """更新行事曆同步設定並立即重新同步。"""
        self.calendar_sync_service.update_settings(
            enabled,
            ics_url,
            refresh_minutes,
            lead_minutes,
            show_in_meeting,
        )

    def test_calendar_connection(self, ics_url: str) -> int:
        """測試 ICS 連線。"""
        return self.calendar_sync_service.test_connection(ics_url)

    def open_reminder_window(
        self,
        reminder_to_edit: dict[str, Any] | None = None,
    ) -> None:
        """請求 UI 開啟設定提醒的視窗。"""
        self.notify_observers(Events.OPEN_REMINDER_WINDOW, reminder_to_edit)

    def open_hourly_web_window(self) -> None:
        """請求 UI 開啟整點啟動設定視窗。"""
        self.notify_observers(Events.OPEN_HOURLY_WEB_WINDOW)

    def open_notification_center(self) -> None:
        """請求 UI 開啟通知中心。"""
        self.notify_observers(Events.OPEN_NOTIFICATION_CENTER)

    def get_notification_settings(self) -> dict[str, bool]:
        """取得智慧通知設定。"""
        return self.notification_center.get_settings()

    def update_notification_settings(self, **changes: bool) -> None:
        """更新智慧通知設定。"""
        self.notification_center.update_settings(**changes)

    def open_todo_window(self) -> None:
        """請求 UI 開啟待辦事項視窗。"""
        self.notify_observers(Events.OPEN_TODO_WINDOW)

    def toggle_todo_remind(self) -> None:
        """切換「整點提醒到期待辦」。"""
        self.todo_service.set_remind_enabled(
            not self.todo_service.is_remind_enabled()
        )

    def is_todo_remind_enabled(self) -> bool:
        return self.todo_service.is_remind_enabled()
