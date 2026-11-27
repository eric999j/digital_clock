"""每秒功能檢查協調器。"""
from datetime import datetime

from services.calendar_sync_service import CalendarSyncService
from services.config_service import ConfigManager
from services.hourly_web_service import HourlyWebService
from services.pause_manager import PauseManager
from services.reminder_service import ReminderService
from services.todo_service import TodoService
from services.vacation_schedule_service import VacationScheduleService


class CheckCoordinator:
    """依固定順序執行共享同一時間快照的功能檢查。"""

    def __init__(
        self,
        config_manager: ConfigManager,
        vacation_schedule_service: VacationScheduleService,
        calendar_sync_service: CalendarSyncService,
        hourly_service: HourlyWebService,
        todo_service: TodoService,
        reminder_service: ReminderService,
        pause_manager: PauseManager,
    ) -> None:
        self.config_manager = config_manager
        self.vacation_schedule_service = vacation_schedule_service
        self.calendar_sync_service = calendar_sync_service
        self.hourly_service = hourly_service
        self.todo_service = todo_service
        self.reminder_service = reminder_service
        self.pause_manager = pause_manager

    def check(self, now: datetime | None = None) -> None:
        """依暫停來源、整點功能、提醒的既有順序執行一次檢查。"""
        check_time = now or datetime.now()
        self.vacation_schedule_service.check(
            now=check_time,
            config=self.config_manager.load_config(read_only=True),
        )
        self.calendar_sync_service.check(now=check_time)

        config_snapshot = self.config_manager.load_config(read_only=True)
        self.hourly_service.check(now=check_time, config=config_snapshot)
        todo_paused = (
            self.pause_manager.get_pause_state('vacation', config=config_snapshot)
            or self.pause_manager.get_pause_state(
                'hourly_web',
                config=config_snapshot,
            )
        )
        self.todo_service.check(
            todo_paused,
            now=check_time,
            config=config_snapshot,
        )

        is_paused = self.pause_manager.get_pause_state(
            'reminder',
            config=config_snapshot,
        )
        self.reminder_service.check_reminders(
            is_paused,
            now=check_time,
            config=config_snapshot,
        )
