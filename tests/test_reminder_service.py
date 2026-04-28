import unittest
from datetime import datetime
from unittest.mock import MagicMock

from services.reminder_service import ReminderService


class TestReminderService(unittest.TestCase):
    def setUp(self):
        self.mock_config_mgr = MagicMock()
        # Setup initial empty config with minimal appearance for check_reminders
        self.config_data = {
            'reminders': [],
            'appearance': {
                'time_formats': {'24h': '%H:%M'}
            }
        }
        self.mock_config_mgr.load_config.return_value = self.config_data
        self.mock_config_mgr.config = self.config_data # Access direct property if used

        self.mock_notify = MagicMock()
        self.service = ReminderService(self.mock_config_mgr, self.mock_notify)

    def test_add_reminder_one_time(self):
        dt = datetime(2025, 12, 25, 10, 0, 0)
        self.service.add_reminder(dt, "Test Message", [], title="Test Title")

        self.mock_config_mgr.save_config.assert_called()
        self.assertEqual(len(self.config_data['reminders']), 1)
        r = self.config_data['reminders'][0]
        self.assertEqual(r['message'], "Test Message")
        self.assertEqual(r['title'], "Test Title")
        self.assertIn("2025-12-25", r['datetime'])

    def test_add_reminder_weekly(self):
        self.service.add_reminder("10:00", "Weekly Msg", ["週一", "週五"], title="Weekly")

        self.assertEqual(len(self.config_data['reminders']), 1)
        r = self.config_data['reminders'][0]
        self.assertEqual(r['weekdays'], ["週一", "週五"])
        self.assertEqual(r['time'], "10:00")

    def test_delete_reminder(self):
        # Setup existing reminder
        reminder = {
            "datetime": "2025-12-25 10:00:00",
            "message": "To Delete",
            "weekdays": [],
            "title": "Delete Me"
        }
        self.config_data['reminders'].append(reminder)

        self.service.delete_reminder(reminder)

        self.assertEqual(len(self.config_data['reminders']), 0)
        self.mock_config_mgr.save_config.assert_called()

    def test_check_reminders(self):
        # Mock strategy
        self.service.strategy = MagicMock()

        reminder = {
            "datetime": "2025-12-25 10:00:00",
            "message": "Due",
            "weekdays": []
        }
        self.service.strategy.check.return_value = [reminder]
        self.config_data['reminders'] = [reminder]

        # Act
        self.service.check_reminders(is_paused=False)

        # Assert
        # Should notify
        self.mock_notify.assert_called()
        args = self.mock_notify.call_args[0]
        self.assertIn(reminder, args) # The event args

        # Should delete (since it's one-time)
        self.assertEqual(len(self.config_data['reminders']), 0)
        self.mock_config_mgr.save_config.assert_called()

    def test_check_reminders_uses_provided_config_without_load(self):
        self.service.strategy = MagicMock()
        provided_config = {
            'reminders': [],
            'appearance': {
                'time_formats': {'24h': '%H:%M'}
            }
        }
        now = datetime(2025, 1, 1, 10, 0, 0)

        self.mock_config_mgr.load_config.side_effect = AssertionError("should not read config manager")
        self.service.strategy.check.return_value = []

        self.service.check_reminders(is_paused=False, now=now, config=provided_config)
        self.service.strategy.check.assert_called_once_with([], now, time_format='%H:%M')

if __name__ == '__main__':
    unittest.main()
