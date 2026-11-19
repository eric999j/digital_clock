"""功能檢查協調器測試。"""
import unittest
from datetime import datetime
from unittest.mock import MagicMock

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
            method.side_effect = lambda **kwargs: calls.append(
                (name, kwargs.get('now'), kwargs.get('config'))
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
        pause_manager.get_pause_state.return_value = False
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
        pause_manager.get_pause_state.assert_called_once_with(
            'reminder', config=feature_snapshot
        )


if __name__ == '__main__':
    unittest.main()
