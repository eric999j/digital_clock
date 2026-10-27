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

    def test_same_hour_next_day_triggers_again(self):
        now1 = datetime(2025, 1, 6, 9, 0, 0)
        self.assertTrue(self.strategy.check(self.base_config, now1))

        now2 = datetime(2025, 1, 7, 9, 0, 0)
        self.assertTrue(self.strategy.check(self.base_config, now2))

    # --- 狀態隔離 ---

    def test_fresh_instance_has_no_triggered_hour(self):
        self.assertEqual(self.strategy.last_triggered_hour, -1)

    # --- url_rules 多命中 ---

    def test_url_rules_returns_all_matched_urls(self):
        """同一時段有多個規則命中時應全部回傳。"""
        config = {
            'url_rules': [
                {'url': 'https://a.example', 'start_hour': 8, 'end_hour': 12},
                {'url': 'https://b.example', 'start_hour': 9, 'end_hour': 10},
                {'url': 'https://c.example', 'start_hour': 13, 'end_hour': 17},
            ],
            'paused': False,
            'work_days_only': False,
        }
        now = datetime(2025, 1, 6, 9, 0, 0)
        result = self.strategy.check(config, now)
        self.assertEqual([r['url'] for r in result], ['https://a.example', 'https://b.example'])

    def test_url_rules_returns_empty_when_no_match(self):
        """時段外沒有命中應回傳空 list。"""
        config = {
            'url_rules': [
                {'url': 'https://a.example', 'start_hour': 8, 'end_hour': 10},
            ],
            'paused': False,
            'work_days_only': False,
        }
        now = datetime(2025, 1, 6, 15, 0, 0)
        self.assertEqual(self.strategy.check(config, now), [])

    def test_url_rules_dedupe_same_url(self):
        """相同 URL 命中多條規則時，只回傳一次避免重複開啟。"""
        config = {
            'url_rules': [
                {'url': 'https://a.example', 'start_hour': 8, 'end_hour': 12},
                {'url': 'https://a.example', 'start_hour': 9, 'end_hour': 10},
            ],
            'paused': False,
            'work_days_only': False,
        }
        now = datetime(2025, 1, 6, 9, 0, 0)
        result = self.strategy.check(config, now)
        self.assertEqual([r['url'] for r in result], ['https://a.example'])

    # --- 程式規則與每規則星期 ---

    def _program_rule(self, **overrides):
        return {
            'type': 'program', 'command': 'python.exe', 'arguments': 'a.py',
            'start_hour': 9, 'end_hour': 9, **overrides,
        }

    def test_program_rule_is_returned_with_all_fields(self):
        rule = self._program_rule()
        config = {'url_rules': [rule], 'work_days_only': True}
        self.assertEqual(self.strategy.check(config, datetime(2025, 1, 6, 9, 0)), [rule])

    def test_url_and_program_rules_can_fire_in_same_hour(self):
        config = {'url_rules': [
            {'url': 'https://a.example', 'start_hour': 9, 'end_hour': 9},
            self._program_rule(),
        ]}
        self.assertEqual(len(self.strategy.check(config, datetime(2025, 1, 6, 9, 0))), 2)

    def test_same_program_with_different_arguments_not_deduped(self):
        config = {'url_rules': [self._program_rule(), self._program_rule(arguments='b.py')]}
        self.assertEqual(len(self.strategy.check(config, datetime(2025, 1, 6, 9, 0))), 2)

    def test_same_program_and_arguments_deduped(self):
        config = {'url_rules': [self._program_rule(), self._program_rule()]}
        self.assertEqual(len(self.strategy.check(config, datetime(2025, 1, 6, 9, 0))), 1)

    def test_rule_weekdays_override_work_days_only(self):
        """規則指定週六時，即使全域僅工作日也要觸發。"""
        config = {'url_rules': [self._program_rule(weekdays=[5])], 'work_days_only': True}
        self.assertEqual(len(self.strategy.check(config, datetime(2025, 1, 4, 9, 0))), 1)

    def test_rule_weekdays_exclude_other_days(self):
        config = {'url_rules': [self._program_rule(weekdays=[0, 1, 2, 3, 4])], 'work_days_only': False}
        self.assertEqual(self.strategy.check(config, datetime(2025, 1, 4, 9, 0)), [])

    def test_empty_command_is_ignored(self):
        config = {'url_rules': [self._program_rule(command='  ')]}
        self.assertEqual(self.strategy.check(config, datetime(2025, 1, 6, 9, 0)), [])


if __name__ == '__main__':
    unittest.main()
