"""功能檢查協調器測試。"""
import unittest
from datetime import datetime
from unittest.mock import MagicMock, call

from core.check_coordinator import CheckCoordinator


class TestCheckCoordinator(unittest.TestCase):
    def test_preserves_feature_order_and_shared_time(self) -> None:
        calls = []
        now = datetime(2026, 11, 18, 9, 0)
        config_manager = MagicMock()
        schedule_snapshot = {'vacation_schedules': []}
        feature_snapshot = {'hourly_web_reminder': {}, 'todo': {}, 'reminders': []}
        config_manager.load_config.side_effect = [schedule_snapshot, feature_snapshot]

        def named(name):
            service = MagicMock()
            method = service.check
            method.side_effect = lambda *args, **kwargs: calls.append(
                (
                    name,
                    kwargs.get('now'),
                    kwargs.get('config'),
                    args[0] if args else None,
                )
            )
            return service

        vacation = named('vacation')
        calendar = named('calendar')
        hourly = named('hourly')
        todo = named('todo')
        reminder = MagicMock()
        reminder.check_reminders.side_effect = lambda paused, **kwargs: calls.append(
            ('reminder', kwargs.get('now'), kwargs.get('config'), paused)
        )
        pause_manager = MagicMock()
        pause_manager.is_manually_paused.side_effect = [False, False]
        coordinator = CheckCoordinator(
            config_manager,
            vacation,
            calendar,
            hourly,
            todo,
            reminder,
            pause_manager,
        )

        coordinator.check(now)

        self.assertEqual(
            [call[0] for call in calls],
            ['vacation', 'calendar', 'hourly', 'todo', 'reminder'],
        )
        self.assertTrue(all(call[1] == now for call in calls))
        self.assertIs(calls[0][2], schedule_snapshot)
        self.assertIs(calls[2][2], feature_snapshot)
        self.assertIs(calls[3][2], feature_snapshot)
        self.assertIs(calls[4][2], feature_snapshot)
        self.assertIs(calls[3][3], False)
        self.assertEqual(
            pause_manager.is_manually_paused.call_args_list,
            [
                call('hourly_web', config=feature_snapshot),
                call('reminder', config=feature_snapshot),
            ],
        )


if __name__ == '__main__':
    unittest.main()
