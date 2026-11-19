"""功能設定與工具視窗協調器。"""
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ui.main_window import DigitalClock

logger = logging.getLogger(__name__)


class WindowController:
    """集中建立功能視窗並維持單例視窗行為。"""

    def __init__(self, ui: "DigitalClock") -> None:
        self.ui = ui

    def open_countdown(self) -> None:
        """開啟自訂倒數視窗。"""
        from ui.countdown_window import CountdownWindow

        def open_window() -> None:
            try:
                CountdownWindow(
                    self.ui.root,
                    self.ui.logic.start_countdown,
                    self.ui._get_current_theme(),
                )
            except Exception as e:
                logger.error("Error opening countdown window: %s", e)

        self.ui.root.after_idle(open_window)

    def open_reminder(
        self,
        reminder_to_edit: dict[str, Any] | None = None,
    ) -> None:
        """開啟新增或編輯提醒視窗。"""
        from ui.reminder_window import ReminderWindow

        def open_window() -> None:
            try:
                ReminderWindow(
                    self.ui.root,
                    self.ui.logic.add_reminder,
                    self.ui._get_current_theme(),
                    reminder_to_edit,
                    geometry=self.ui.config['ui_behavior']['reminder_window_geometry'],
                )
            except Exception as e:
                logger.error("Error opening reminder window: %s", e)

        self.ui.root.after_idle(open_window)

    def open_hourly(self) -> None:
        """開啟整點啟動設定視窗。"""
        from ui.hourly_web_window import HourlyWebWindow

        def open_window() -> None:
            try:
                theme = self.ui._get_current_theme()
                fresh = self.ui.logic.get_config()
                self.ui.config['hourly_web_reminder'] = fresh.get(
                    'hourly_web_reminder',
                    {},
                )
                self.ui.config['reminders'] = fresh.get('reminders', [])
                self.ui.config['vacation_schedules'] = fresh.get(
                    'vacation_schedules',
                    [],
                )
                HourlyWebWindow(
                    self.ui.root,
                    self.ui.logic.update_hourly_web_reminder,
                    theme,
                    self.ui.config['hourly_web_reminder'],
                    geometry=self.ui.config['ui_behavior'][
                        'hourly_web_window_geometry'
                    ],
                )
            except Exception as e:
                logger.error("Error opening hourly web window: %s", e)

        self.ui.root.after_idle(open_window)

    def open_notification_center(self) -> None:
        """開啟通知中心；已存在時帶回前景並標記已讀。"""
        from ui.notification_window import NotificationWindow

        def open_window() -> None:
            try:
                existing = self.ui._live_notification_window()
                if existing is not None:
                    existing.deiconify()
                    existing.lift()
                    existing.refresh()
                    self.ui.logic.notification_center.mark_all_read()
                    return
                self.ui._notification_window = NotificationWindow(
                    self.ui.root,
                    self.ui.logic.notification_center,
                    self.ui._get_current_theme(),
                )
            except Exception as e:
                logger.error("Error opening notification center: %s", e)

        self.ui.root.after_idle(open_window)

    def open_todo(self) -> None:
        """開啟待辦視窗；已存在時只帶回前景。"""
        from ui.todo_window import TodoWindow

        def open_window() -> None:
            try:
                existing = self.ui._live_todo_window()
                if existing is not None:
                    existing.deiconify()
                    existing.lift()
                    existing.focus_force()
                    return
                geometry = self.ui.config['ui_behavior'].get(
                    'todo_window_geometry',
                    '760x560',
                )
                self.ui._todo_window = TodoWindow(
                    self.ui.root,
                    self.ui.logic.todo_service,
                    self.ui._get_current_theme(),
                    geometry=geometry,
                    on_close=self.ui._save_todo_window_geometry,
                )
            except Exception as e:
                logger.error("Error opening todo window: %s", e)

        self.ui.root.after_idle(open_window)

    def open_vacation_schedule(
        self,
        schedule_to_edit: dict[str, Any] | None = None,
    ) -> None:
        """開啟新增或編輯勿擾排程視窗。"""
        from ui.vacation_schedule_window import VacationScheduleWindow

        def open_window() -> None:
            try:
                VacationScheduleWindow(
                    self.ui.root,
                    self.ui.logic.add_vacation_schedule,
                    self.ui._get_current_theme(),
                    schedule_to_edit=schedule_to_edit,
                    update_callback=self.ui.logic.update_vacation_schedule,
                )
            except Exception as e:
                logger.error("Error opening vacation schedule window: %s", e)

        self.ui.root.after_idle(open_window)

    def open_calendar_sync(self) -> None:
        """開啟行事曆同步設定視窗。"""
        from ui.calendar_sync_window import CalendarSyncWindow

        def open_window() -> None:
            try:
                CalendarSyncWindow(
                    self.ui.root,
                    self.ui.logic.get_calendar_sync_settings(),
                    self.ui._save_calendar_sync_settings,
                    self.ui.logic.test_calendar_connection,
                    self.ui._get_current_theme(),
                )
            except Exception as e:
                logger.error("Error opening calendar sync window: %s", e)

        self.ui.root.after_idle(open_window)
