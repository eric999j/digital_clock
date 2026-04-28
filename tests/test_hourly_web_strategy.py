import unittest
from datetime import datetime

from strategies.hourly_web_strategy import HourlyWebReminderStrategy


class TestHourlyWebReminderStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = HourlyWebReminderStrategy()
        self.base_config = {
            'url': 'https://example.com',
            'start_hour': 8,
            'end_hour': 17,
            'paused': False,
            'work_days_only': True,
        }

    # --- 正常觸發 ---

    def test_triggers_at_start_of_hour_in_range(self):
        # 2025-01-06 是週一
        now = datetime(2025, 1, 6, 9, 0, 0)
        self.assertTrue(self.strategy.check(self.base_config, now))

    def test_triggers_at_minute_one(self):
        now = datetime(2025, 1, 6, 10, 1, 0)
        self.assertTrue(self.strategy.check(self.base_config, now))

    def test_triggers_at_start_hour_boundary(self):
        now = datetime(2025, 1, 6, 8, 0, 0)
        self.assertTrue(self.strategy.check(self.base_config, now))

    def test_triggers_at_end_hour_boundary(self):
        now = datetime(2025, 1, 6, 17, 0, 0)
        self.assertTrue(self.strategy.check(self.base_config, now))

    # --- 不觸發 ---

    def test_not_triggered_when_paused(self):
        config = {**self.base_config, 'paused': True}
        now = datetime(2025, 1, 6, 9, 0, 0)
        self.assertFalse(self.strategy.check(config, now))

    def test_not_triggered_without_url(self):
        config = {**self.base_config, 'url': ''}
        now = datetime(2025, 1, 6, 9, 0, 0)
        self.assertFalse(self.strategy.check(config, now))

    def test_not_triggered_whitespace_only_url(self):
        config = {**self.base_config, 'url': '   '}
        now = datetime(2025, 1, 6, 9, 0, 0)
        self.assertFalse(self.strategy.check(config, now))

    def test_not_triggered_on_weekend_when_work_days_only(self):
        # 2025-01-04 是週六
        now = datetime(2025, 1, 4, 9, 0, 0)
        self.assertFalse(self.strategy.check(self.base_config, now))

    def test_triggered_on_weekend_when_work_days_only_disabled(self):
        config = {**self.base_config, 'work_days_only': False}
        now = datetime(2025, 1, 4, 9, 0, 0)
        self.assertTrue(self.strategy.check(config, now))

    def test_not_triggered_before_start_hour(self):
        now = datetime(2025, 1, 6, 7, 0, 0)
        self.assertFalse(self.strategy.check(self.base_config, now))

    def test_not_triggered_after_end_hour(self):
        now = datetime(2025, 1, 6, 18, 0, 0)
        self.assertFalse(self.strategy.check(self.base_config, now))

    def test_not_triggered_after_minute_one(self):
        now = datetime(2025, 1, 6, 9, 2, 0)
        self.assertFalse(self.strategy.check(self.base_config, now))

    # --- 去重 ---

    def test_same_hour_not_triggered_twice(self):
        now = datetime(2025, 1, 6, 9, 0, 0)
        self.assertTrue(self.strategy.check(self.base_config, now))
        self.assertFalse(self.strategy.check(self.base_config, now))

    def test_different_hour_triggers_again(self):
        now1 = datetime(2025, 1, 6, 9, 0, 0)
        self.assertTrue(self.strategy.check(self.base_config, now1))

        now2 = datetime(2025, 1, 6, 10, 0, 0)
        self.assertTrue(self.strategy.check(self.base_config, now2))

    # --- 狀態隔離 ---

    def test_fresh_instance_has_no_triggered_hour(self):
        self.assertEqual(self.strategy.last_triggered_hour, -1)


if __name__ == '__main__':
    unittest.main()
