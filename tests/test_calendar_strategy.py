"""CalendarVacationStrategy 測試。"""
import unittest
from datetime import datetime

from strategies.calendar_strategy import CalendarVacationStrategy


def _ev(start: str, end: str, summary: str = "會議") -> dict:
    return {'start': datetime.fromisoformat(start), 'end': datetime.fromisoformat(end), 'summary': summary}


class CalendarVacationStrategyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = CalendarVacationStrategy()

    def test_inside_event_is_active(self) -> None:
        result = self.strategy.check([_ev("2026-05-01T10:00", "2026-05-01T12:00")],
                                     datetime(2026, 5, 1, 11, 0))
        self.assertTrue(result['active'])
        self.assertEqual(result['current']['summary'], "會議")

    def test_boundaries_start_inclusive_end_exclusive(self) -> None:
        events = [_ev("2026-05-01T10:00", "2026-05-01T12:00")]
        self.assertTrue(self.strategy.check(events, datetime(2026, 5, 1, 10, 0))['active'])
        self.assertFalse(self.strategy.check(events, datetime(2026, 5, 1, 12, 0))['active'])

    def test_back_to_back_events_are_merged(self) -> None:
        events = [_ev("2026-05-01T10:00", "2026-05-01T11:00"),
                  _ev("2026-05-01T11:00", "2026-05-01T12:00")]
        result = self.strategy.check(events, datetime(2026, 5, 1, 11, 0))
        self.assertTrue(result['active'])
        self.assertEqual(result['current']['end'], datetime(2026, 5, 1, 12, 0))

    def test_upcoming_within_lead_window(self) -> None:
        events = [_ev("2026-05-01T10:00", "2026-05-01T11:00")]
        near = self.strategy.check(events, datetime(2026, 5, 1, 9, 55), lead_minutes=10)
        far = self.strategy.check(events, datetime(2026, 5, 1, 9, 30), lead_minutes=10)
        none = self.strategy.check(events, datetime(2026, 5, 1, 9, 55), lead_minutes=0)
        self.assertFalse(near['active'])
        self.assertIsNotNone(near['upcoming'])
        self.assertIsNone(far['upcoming'])
        self.assertIsNone(none['upcoming'])

    def test_invalid_intervals_ignored(self) -> None:
        events = [_ev("2026-05-01T12:00", "2026-05-01T10:00"), {'start': None, 'end': None}]
        result = self.strategy.check(events, datetime(2026, 5, 1, 11, 0))
        self.assertFalse(result['active'])


if __name__ == '__main__':
    unittest.main()
