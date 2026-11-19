"""UI 事件路由相容性測試。"""
import unittest
from unittest.mock import MagicMock

from core.events import Events
from ui.event_router import build_event_handlers


class TestEventRouter(unittest.TestCase):
    def test_routes_all_observed_events_to_existing_handlers(self) -> None:
        ui = MagicMock()
        handlers = build_event_handlers(ui)

        self.assertEqual(
            set(handlers),
            {
                Events.POMODORO_PHASE_CHANGE,
                Events.POMODORO_TICK,
                Events.POMODORO_PHASE_COMPLETE,
                Events.POMODORO_PAUSE_TOGGLED,
                Events.REMINDER_DUE,
                Events.REMINDER_SNOOZED,
                Events.COUNTDOWN_STARTED,
                Events.COUNTDOWN_TICK,
                Events.COUNTDOWN_PAUSE_TOGGLED,
                Events.COUNTDOWN_CANCELLED,
                Events.COUNTDOWN_FINISHED,
                Events.TIMEZONES_UPDATED,
                Events.OPEN_COUNTDOWN_WINDOW,
                Events.REMINDER_ADDED,
                Events.REMINDER_UPDATED,
                Events.REMINDER_DELETED,
                Events.HOURLY_WEB_UPDATED,
                Events.HOURLY_WEB_PAUSE_TOGGLED,
                Events.REMINDER_PAUSE_TOGGLED,
                Events.VACATION_TOGGLED,
                Events.VACATION_SCHEDULE_ADDED,
                Events.VACATION_SCHEDULE_DELETED,
                Events.VACATION_SCHEDULE_UPDATED,
                Events.OPEN_REMINDER_WINDOW,
                Events.OPEN_HOURLY_WEB_WINDOW,
                Events.OPEN_VACATION_SCHEDULE_WINDOW,
                Events.OPEN_CALENDAR_SYNC_WINDOW,
                Events.OPEN_TODO_WINDOW,
                Events.OPEN_NOTIFICATION_CENTER,
                Events.NOTIFICATIONS_CHANGED,
                Events.TODO_UPDATED,
                Events.TODO_DUE,
                Events.TODO_REMIND_TOGGLED,
                Events.CALENDAR_EVENT_UPCOMING,
                Events.CALENDAR_EVENT_STARTED,
                Events.CALENDAR_EVENT_ENDED,
                Events.SCREENSHOT_TRIGGERED,
            },
        )
        handlers[Events.REMINDER_DUE]({'message': 'hello'}, 'extra')
        ui._on_reminder_due.assert_called_once_with({'message': 'hello'}, 'extra')


if __name__ == '__main__':
    unittest.main()
