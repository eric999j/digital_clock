"""VacationScheduleStrategy 測試。"""
import unittest
from datetime import date

from strategies.vacation_schedule_strategy import VacationScheduleStrategy


class TestVacationScheduleStrategy(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = VacationScheduleStrategy()
        self.today = date(2026, 7, 10)

    def test_classifies_expired_active_future(self) -> None:
        schedules = [
            {'start': '2026-07-01', 'end': '2026-07-05', 'note': '過去'},
            {'start': '2026-07-05', 'end': '2026-07-15', 'note': '進行中'},
            {'start': '2026-08-01', 'end': '2026-08-05', 'note': '未來'},
        ]

        result = self.strategy.check(schedules, self.today)

        self.assertEqual(len(result['expired']), 1)
        self.assertEqual(result['expired'][0]['note'], '過去')
        self.assertEqual(len(result['active']), 1)
        self.assertEqual(result['active'][0]['note'], '進行中')
        self.assertEqual(len(result['future']), 1)
        self.assertEqual(result['future'][0]['note'], '未來')
        self.assertEqual(result['invalid'], [])

    def test_boundary_start_equals_today_is_active(self) -> None:
        schedules = [{'start': '2026-07-10', 'end': '2026-07-15'}]
        result = self.strategy.check(schedules, self.today)
        self.assertEqual(len(result['active']), 1)
        self.assertEqual(result['expired'], [])
        self.assertEqual(result['future'], [])

    def test_boundary_end_equals_today_is_active(self) -> None:
        schedules = [{'start': '2026-07-01', 'end': '2026-07-10'}]
        result = self.strategy.check(schedules, self.today)
        self.assertEqual(len(result['active']), 1)
        self.assertEqual(result['expired'], [])

    def test_single_day_schedule_active(self) -> None:
        schedules = [{'start': '2026-07-10', 'end': '2026-07-10'}]
        result = self.strategy.check(schedules, self.today)
        self.assertEqual(len(result['active']), 1)

    def test_invalid_when_end_before_start(self) -> None:
        schedules = [{'start': '2026-07-15', 'end': '2026-07-10'}]
        result = self.strategy.check(schedules, self.today)
        self.assertEqual(len(result['invalid']), 1)
        self.assertEqual(result['active'], [])
        self.assertEqual(result['expired'], [])
        self.assertEqual(result['future'], [])

    def test_invalid_when_missing_field(self) -> None:
        schedules = [{'start': '2026-07-10'}]
        result = self.strategy.check(schedules, self.today)
        self.assertEqual(len(result['invalid']), 1)

    def test_invalid_when_date_string_malformed(self) -> None:
        schedules = [{'start': 'not-a-date', 'end': '2026-07-15'}]
        result = self.strategy.check(schedules, self.today)
        self.assertEqual(len(result['invalid']), 1)

    def test_empty_schedules(self) -> None:
        result = self.strategy.check([], self.today)
        self.assertEqual(result, {'expired': [], 'active': [], 'future': [], 'invalid': []})


if __name__ == '__main__':
    unittest.main()
