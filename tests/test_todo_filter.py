"""TodoFilter 篩選、搜尋與統計測試。"""
import unittest
from datetime import date

from core.todo_filter import (
    FILTER_ALL,
    FILTER_COMPLETED,
    FILTER_DUE_TODAY,
    FILTER_DUE_WEEK,
    FILTER_HIGH,
    FILTER_INCOMPLETE,
    FILTER_NO_DUE,
    FILTER_OVERDUE,
    TodoFilter,
)
from core.todo_task import TodoTask

TODAY = date(2026, 11, 5)


def texts(nodes) -> list[str]:
    return [n.task.text for n in nodes]


class TestTodoFilter(unittest.TestCase):
    def setUp(self) -> None:
        self.child_done = TodoTask("子已完成", is_done=True)
        self.child_high = TodoTask("子高優先", priority="high", due_date=date(2026, 11, 5))
        self.parent = TodoTask("父項", children=[self.child_done, self.child_high], project="Alpha")
        self.overdue = TodoTask("逾期", due_date=date(2026, 11, 1))
        self.week = TodoTask("本週", due_date=date(2026, 11, 10))
        self.done_overdue = TodoTask("已完成逾期", due_date=date(2026, 11, 1), is_done=True)
        self.tasks = [self.parent, self.overdue, self.week, self.done_overdue]

    def test_all_keeps_full_tree(self) -> None:
        nodes = TodoFilter.filter_tasks(self.tasks, FILTER_ALL, TODAY)
        self.assertEqual(texts(nodes), ["父項", "逾期", "本週", "已完成逾期"])
        self.assertEqual(texts(nodes[0].children), ["子已完成", "子高優先"])

    def test_incomplete_keeps_ancestor_of_match(self) -> None:
        nodes = TodoFilter.filter_tasks(self.tasks, FILTER_INCOMPLETE, TODAY)
        self.assertEqual(texts(nodes), ["父項", "逾期", "本週"])
        self.assertEqual(texts(nodes[0].children), ["子高優先"])

    def test_high_priority_keeps_ancestor(self) -> None:
        nodes = TodoFilter.filter_tasks(self.tasks, FILTER_HIGH, TODAY)
        self.assertEqual(texts(nodes), ["父項"])
        self.assertEqual(texts(nodes[0].children), ["子高優先"])

    def test_completed(self) -> None:
        nodes = TodoFilter.filter_tasks(self.tasks, FILTER_COMPLETED, TODAY)
        self.assertEqual(texts(nodes), ["父項", "已完成逾期"])

    def test_due_modes_skip_done_tasks(self) -> None:
        self.assertEqual(texts(TodoFilter.filter_tasks(self.tasks, FILTER_OVERDUE, TODAY)), ["逾期"])
        self.assertEqual(texts(TodoFilter.filter_tasks(self.tasks, FILTER_DUE_TODAY, TODAY)), ["父項"])
        self.assertEqual(texts(TodoFilter.filter_tasks(self.tasks, FILTER_DUE_WEEK, TODAY)), ["本週"])

    def test_no_due(self) -> None:
        nodes = TodoFilter.filter_tasks(self.tasks, FILTER_NO_DUE, TODAY)
        self.assertEqual(texts(nodes), ["父項"])
        self.assertEqual(texts(nodes[0].children), ["子已完成"])

    def test_search_matches_text_and_project_case_insensitively(self) -> None:
        self.assertEqual(texts(TodoFilter.apply(self.tasks, FILTER_ALL, "逾期", TODAY)), ["逾期", "已完成逾期"])
        nodes = TodoFilter.apply(self.tasks, FILTER_ALL, "alpha", TODAY)
        self.assertEqual(texts(nodes), ["父項"])

    def test_search_child_keeps_parent(self) -> None:
        nodes = TodoFilter.apply(self.tasks, FILTER_ALL, "高優先", TODAY)
        self.assertEqual(texts(nodes), ["父項"])
        self.assertEqual(texts(nodes[0].children), ["子高優先"])

    def test_empty_query_returns_all(self) -> None:
        self.assertEqual(len(TodoFilter.apply(self.tasks, FILTER_ALL, "  ", TODAY)), 4)

    def test_unknown_mode_falls_back_to_all(self) -> None:
        self.assertEqual(len(TodoFilter.filter_tasks(self.tasks, "bogus", TODAY)), 4)

    def test_count_tasks_counts_leaves_and_skips_done_parent_descendants(self) -> None:
        done_parent = TodoTask("完成父項", is_done=True, children=[TodoTask("c1", is_done=True), TodoTask("c2", is_done=True)])
        total, pending, done = TodoFilter.count_tasks([self.parent, done_parent])
        # 父項→2 個葉（1 完成、1 待辦）；完成父項算 1 項完成
        self.assertEqual((total, pending, done), (3, 1, 2))


if __name__ == "__main__":
    unittest.main()
