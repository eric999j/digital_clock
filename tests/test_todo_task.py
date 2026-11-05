"""TodoTask 資料模型與日期輸入解析測試。"""
import unittest
from datetime import UTC, date, datetime

from core.todo_task import PRIORITY_NORMAL, TodoTask, parse_date_input


class TestTodoTask(unittest.TestCase):
    def test_roundtrip_full_fields(self) -> None:
        child = TodoTask("子項", is_done=True)
        task = TodoTask(
            "父項", children=[child], link="https://example.com", project="專案", priority="high",
            due_date=date(2026, 9, 30), start_date=date(2026, 2, 1),
        )
        restored = TodoTask.from_dict(task.to_dict())
        self.assertEqual(restored.id, task.id)
        self.assertEqual(restored.text, "父項")
        self.assertEqual(restored.link, "https://example.com")
        self.assertEqual(restored.project, "專案")
        self.assertEqual(restored.priority, "high")
        self.assertEqual(restored.due_date, date(2026, 9, 30))
        self.assertEqual(restored.start_date, date(2026, 2, 1))
        self.assertEqual(len(restored.children), 1)
        self.assertTrue(restored.children[0].is_done)

    def test_creation_time_is_utc_aware_and_serialized_with_z(self) -> None:
        task = TodoTask("a", creation_time=datetime(2026, 1, 2, 3, 4, 5))
        self.assertEqual(task.creation_time.tzinfo, UTC)
        self.assertTrue(task.to_dict()["creation_time"].endswith("Z"))

    def test_from_dict_accepts_datetime_in_date_fields(self) -> None:
        restored = TodoTask.from_dict({"text": "a", "due_date": "2026-05-06T10:00:00", "start_date": "2026-05-01T00:00:00Z"})
        self.assertEqual(restored.due_date, date(2026, 5, 6))
        self.assertEqual(restored.start_date, date(2026, 5, 1))

    def test_from_dict_missing_optional_fields_use_defaults(self) -> None:
        restored = TodoTask.from_dict({"text": "a"})
        self.assertFalse(restored.is_done)
        self.assertEqual(restored.priority, PRIORITY_NORMAL)
        self.assertIsNone(restored.due_date)
        self.assertEqual(restored.children, [])
        self.assertTrue(restored.id)

    def test_from_dict_invalid_values_fall_back(self) -> None:
        restored = TodoTask.from_dict({"text": "a", "due_date": "not-a-date", "priority": "urgent", "creation_time": "bad"})
        self.assertIsNone(restored.due_date)
        self.assertEqual(restored.priority, PRIORITY_NORMAL)
        self.assertIsNotNone(restored.start_date)

    def test_from_dict_skips_non_dict_children(self) -> None:
        restored = TodoTask.from_dict({"text": "a", "children": ["x", {"text": "ok"}]})
        self.assertEqual([c.text for c in restored.children], ["ok"])


class TestParseDateInput(unittest.TestCase):
    TODAY = date(2026, 11, 5)

    def test_blank_is_none(self) -> None:
        self.assertIsNone(parse_date_input("  ", self.TODAY))

    def test_shortcuts(self) -> None:
        self.assertEqual(parse_date_input("今天", self.TODAY), date(2026, 11, 5))
        self.assertEqual(parse_date_input("明天", self.TODAY), date(2026, 11, 6))
        self.assertEqual(parse_date_input("下週", self.TODAY), date(2026, 11, 12))

    def test_iso_and_slash(self) -> None:
        self.assertEqual(parse_date_input("2026-12-01", self.TODAY), date(2026, 12, 1))
        self.assertEqual(parse_date_input("2026/12/01", self.TODAY), date(2026, 12, 1))

    def test_invalid_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_date_input("12/01", self.TODAY)


if __name__ == "__main__":
    unittest.main()
