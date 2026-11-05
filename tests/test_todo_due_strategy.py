"""TodoDueStrategy 觸發條件與去重測試。"""
import unittest
from datetime import date, datetime

from core.todo_task import TodoTask
from strategies.todo_due_strategy import TodoDueStrategy

CONFIG = {"remind_enabled": True, "start_hour": 9, "end_hour": 17, "work_days_only": True}
THURSDAY_9AM = datetime(2026, 11, 5, 9, 0, 0)


def make_tasks() -> list[TodoTask]:
    return [
        TodoTask("今日", due_date=date(2026, 11, 5), start_date=date(2026, 11, 1)),
        TodoTask("逾期", due_date=date(2026, 11, 1), start_date=date(2026, 10, 1)),
        TodoTask("未來", due_date=date(2026, 11, 9), start_date=date(2026, 11, 1)),
        TodoTask("已完成", due_date=date(2026, 11, 1), start_date=date(2026, 10, 1), is_done=True),
        TodoTask("尚未開始", due_date=date(2026, 11, 5), start_date=date(2026, 11, 6)),
        TodoTask("無截止日", start_date=date(2026, 11, 1)),
    ]


class TestTodoDueStrategy(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = TodoDueStrategy()

    def test_returns_overdue_first_then_today(self) -> None:
        items = self.strategy.check(CONFIG, make_tasks(), THURSDAY_9AM)
        self.assertEqual([i["text"] for i in items], ["逾期", "今日"])
        self.assertEqual([i["status"] for i in items], ["overdue", "today"])

    def test_nested_children_are_included(self) -> None:
        parent = TodoTask("父", start_date=date(2026, 11, 1), children=[TodoTask("子", due_date=date(2026, 11, 5), start_date=date(2026, 11, 1))])
        items = self.strategy.check(CONFIG, [parent], THURSDAY_9AM)
        self.assertEqual([i["text"] for i in items], ["子"])

    def test_once_per_hour(self) -> None:
        self.assertTrue(self.strategy.check(CONFIG, make_tasks(), THURSDAY_9AM))
        self.assertEqual(self.strategy.check(CONFIG, make_tasks(), THURSDAY_9AM.replace(minute=1)), [])
        self.assertTrue(self.strategy.check(CONFIG, make_tasks(), THURSDAY_9AM.replace(hour=10)))

    def test_only_within_first_minutes_of_the_hour(self) -> None:
        self.assertEqual(self.strategy.check(CONFIG, make_tasks(), THURSDAY_9AM.replace(minute=2)), [])

    def test_outside_hours_does_not_trigger(self) -> None:
        self.assertEqual(self.strategy.check(CONFIG, make_tasks(), THURSDAY_9AM.replace(hour=8)), [])
        self.assertEqual(self.strategy.check(CONFIG, make_tasks(), THURSDAY_9AM.replace(hour=18)), [])

    def test_weekend_respects_work_days_only(self) -> None:
        saturday = datetime(2026, 11, 7, 9, 0, 0)
        self.assertEqual(self.strategy.check(CONFIG, make_tasks(), saturday), [])
        self.assertTrue(TodoDueStrategy().check({**CONFIG, "work_days_only": False}, make_tasks(), saturday))

    def test_disabled(self) -> None:
        self.assertEqual(self.strategy.check({**CONFIG, "remind_enabled": False}, make_tasks(), THURSDAY_9AM), [])

    def test_nothing_due_does_not_consume_the_hour(self) -> None:
        self.assertEqual(self.strategy.check(CONFIG, [], THURSDAY_9AM), [])
        self.assertTrue(self.strategy.check(CONFIG, make_tasks(), THURSDAY_9AM.replace(minute=1)))


if __name__ == "__main__":
    unittest.main()
