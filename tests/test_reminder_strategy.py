import unittest
from datetime import datetime

from strategies.reminder_strategy import ReminderStrategy


class TestReminderStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = ReminderStrategy()

    # --- 單次提醒 ---

    def test_onetime_reminder_triggered_when_past_due(self):
        reminders = [{'datetime': '2025-01-01 09:00:00', 'message': 'test', 'weekdays': []}]
        now = datetime(2025, 1, 1, 9, 0, 1)
        result = self.strategy.check(reminders, now)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['message'], 'test')

    def test_onetime_reminder_triggered_at_exact_time(self):
        reminders = [{'datetime': '2025-01-01 09:00:00', 'message': 'exact', 'weekdays': []}]
        now = datetime(2025, 1, 1, 9, 0, 0)
        result = self.strategy.check(reminders, now)
        self.assertEqual(len(result), 1)

    def test_onetime_reminder_not_triggered_before_time(self):
        reminders = [{'datetime': '2025-01-01 09:00:00', 'message': 'future', 'weekdays': []}]
        now = datetime(2025, 1, 1, 8, 59, 59)
        result = self.strategy.check(reminders, now)
        self.assertEqual(len(result), 0)

    def test_onetime_reminder_invalid_datetime_skipped(self):
        reminders = [{'datetime': 'invalid-date', 'message': 'bad', 'weekdays': []}]
        now = datetime(2025, 1, 1, 9, 0, 0)
        result = self.strategy.check(reminders, now)
        self.assertEqual(len(result), 0)

    # --- 週期提醒 ---

    def test_weekly_reminder_triggered_on_matching_day_and_time(self):
        # 2025-01-06 是週一
        reminders = [{'time': '09:00', 'message': 'weekly', 'weekdays': ['週一']}]
        now = datetime(2025, 1, 6, 9, 0, 0)
        result = self.strategy.check(reminders, now)
        self.assertEqual(len(result), 1)

    def test_weekly_reminder_not_triggered_wrong_day(self):
        # 2025-01-07 是週二
        reminders = [{'time': '09:00', 'message': 'weekly', 'weekdays': ['週一']}]
        now = datetime(2025, 1, 7, 9, 0, 0)
        result = self.strategy.check(reminders, now)
        self.assertEqual(len(result), 0)

    def test_weekly_reminder_not_triggered_wrong_time(self):
        # 2025-01-06 是週一
        reminders = [{'time': '09:00', 'message': 'weekly', 'weekdays': ['週一']}]
        now = datetime(2025, 1, 6, 10, 0, 0)
        result = self.strategy.check(reminders, now)
        self.assertEqual(len(result), 0)

    def test_weekly_reminder_dedup_same_minute(self):
        """同一分鐘內不應重複觸發週期提醒。"""
        reminders = [{'time': '09:00', 'message': 'weekly', 'weekdays': ['週一']}]
        now = datetime(2025, 1, 6, 9, 0, 0)

        result1 = self.strategy.check(reminders, now)
        self.assertEqual(len(result1), 1)

        result2 = self.strategy.check(reminders, now)
        self.assertEqual(len(result2), 0)

    def test_weekly_reminder_triggers_again_next_minute(self):
        """跨分鐘後應可再次觸發。"""
        reminders = [{'time': '09:00', 'message': 'weekly', 'weekdays': ['週一']}]
        now1 = datetime(2025, 1, 6, 9, 0, 0)
        self.strategy.check(reminders, now1)

        # 下週一同時間
        now2 = datetime(2025, 1, 13, 9, 0, 0)
        result = self.strategy.check(reminders, now2)
        self.assertEqual(len(result), 1)

    def test_weekly_reminder_invalid_weekday_skipped(self):
        reminders = [{'time': '09:00', 'message': 'bad', 'weekdays': ['無效日']}]
        now = datetime(2025, 1, 6, 9, 0, 0)
        result = self.strategy.check(reminders, now)
        self.assertEqual(len(result), 0)

    def test_weekly_multiple_weekdays(self):
        # 2025-01-10 是週五
        reminders = [{'time': '09:00', 'message': 'multi', 'weekdays': ['週一', '週五']}]
        now = datetime(2025, 1, 10, 9, 0, 0)
        result = self.strategy.check(reminders, now)
        self.assertEqual(len(result), 1)

    # --- 混合測試 ---

    def test_mixed_reminders(self):
        """同時包含單次和週期提醒。"""
        reminders = [
            {'datetime': '2025-01-06 09:00:00', 'message': 'onetime', 'weekdays': []},
            {'time': '09:00', 'message': 'weekly', 'weekdays': ['週一']},
        ]
        now = datetime(2025, 1, 6, 9, 0, 0)
        result = self.strategy.check(reminders, now)
        self.assertEqual(len(result), 2)

    def test_empty_reminders_returns_empty(self):
        result = self.strategy.check([], datetime(2025, 1, 1, 9, 0, 0))
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
