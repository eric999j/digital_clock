import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from core.events import Events
from services.reminder_service import ReminderService
from strategies.reminder_strategy import ReminderStrategy


class TestSnoozeReminder(unittest.TestCase):
    def setUp(self):
        self.config = {'reminders': [], 'appearance': {'time_formats': {'24h': '%H:%M'}}}
        self.config_mgr = MagicMock()
        self.config_mgr.load_config.return_value = self.config
        self.notify = MagicMock()
        self.service = ReminderService(self.config_mgr, self.notify)
        self.now = datetime(2026, 5, 1, 9, 30, 45, 123456)

    def test_snooze_creates_one_time_reminder_with_same_content(self):
        original = {"time": "09:30", "message": "站起來", "weekdays": ["週一"], "title": "伸展"}

        snoozed = self.service.snooze_reminder(original, 10, now=self.now)

        self.assertEqual(snoozed, {
            "datetime": "2026-05-01 09:40:45",
            "message": "站起來",
            "weekdays": [],
            "title": "伸展",
        })
        self.assertEqual(self.config['reminders'], [snoozed])
        self.config_mgr.save_config.assert_called_once_with(self.config)
        self.notify.assert_called_once_with(Events.REMINDER_SNOOZED, snoozed, 10)

    def test_snoozing_a_weekly_reminder_does_not_touch_the_original_schedule(self):
        weekly = {"time": "09:30", "message": "m", "weekdays": ["週五"], "title": "t"}
        self.config['reminders'].append(weekly)

        self.service.snooze_reminder(weekly, 5, now=self.now)

        self.assertIn(weekly, self.config['reminders'])
        self.assertEqual(len(self.config['reminders']), 2)

    def test_snooze_crosses_midnight(self):
        late = datetime(2026, 12, 31, 23, 58, 0)
        snoozed = self.service.snooze_reminder({"message": "m", "title": "t"}, 5, now=late)
        self.assertEqual(snoozed["datetime"], "2027-01-01 00:03:00")

    def test_snooze_rejects_invalid_minutes(self):
        for bad in (0, -1, ReminderService.MAX_SNOOZE_MINUTES + 1, 5.5, "10", True, None):
            with self.subTest(minutes=bad), self.assertRaises(ValueError):
                self.service.snooze_reminder({"message": "m"}, bad, now=self.now)
        self.config_mgr.save_config.assert_not_called()
        self.notify.assert_not_called()

    def test_snooze_with_missing_fields_defaults_to_empty_strings(self):
        snoozed = self.service.snooze_reminder({}, 5, now=self.now)
        self.assertEqual((snoozed["message"], snoozed["title"]), ("", ""))

    def test_snoozed_reminder_triggers_once_due_and_is_removed(self):
        snoozed = self.service.snooze_reminder({"message": "m", "title": "t"}, 5)
        service = ReminderService(self.config_mgr, self.notify)
        service.strategy = ReminderStrategy()
        self.notify.reset_mock()

        # 尚未到期
        service.check_reminders(False, now=datetime.now(), config=self.config)
        self.notify.assert_not_called()

        # 到期後觸發並移除
        service.check_reminders(False, now=datetime.now() + timedelta(minutes=6), config=self.config)
        self.notify.assert_called_once_with(Events.REMINDER_DUE, snoozed)
        self.assertNotIn(snoozed, self.config['reminders'])

    def test_snooze_options_are_valid(self):
        for minutes in ReminderService.SNOOZE_OPTIONS_MINUTES:
            self.assertTrue(1 <= minutes <= ReminderService.MAX_SNOOZE_MINUTES)


if __name__ == "__main__":
    unittest.main()
