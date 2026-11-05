"""TodoStore 持久化、匯入與 Markdown 匯出測試。"""
import json
import tempfile
import unittest
from pathlib import Path

from core.todo_task import TodoTask
from services.todo_store import TodoStore, export_markdown, read_tasks_file


class TestTodoStore(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "sub" / "todos.json"
        self.store = TodoStore(self.path)

    def test_load_missing_file_returns_empty(self) -> None:
        self.assertEqual(self.store.load(), ([], ""))

    def test_save_then_load_roundtrip(self) -> None:
        tasks = [TodoTask("a", children=[TodoTask("b")])]
        self.assertEqual(self.store.save(tasks), "")
        loaded, message = self.store.load()
        self.assertEqual(message, "")
        self.assertEqual(loaded[0].children[0].text, "b")
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["version"], 1)
        self.assertFalse(self.path.with_name("todos.json.tmp").exists())

    def test_corrupted_file_is_backed_up(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        loaded, message = self.store.load()
        self.assertEqual(loaded, [])
        self.assertIn("損毀", message)
        self.assertTrue(self.path.with_name("todos.json.bak").exists())
        self.assertFalse(self.path.exists())

    def test_wrong_shape_is_treated_as_corrupted(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"tasks": "oops"}', encoding="utf-8")
        loaded, message = self.store.load()
        self.assertEqual(loaded, [])
        self.assertTrue(message)

    def test_read_tasks_file_accepts_legacy_list(self) -> None:
        legacy = Path(self._tmp.name) / "tasks.json"
        legacy.write_text(json.dumps([{"text": "舊任務", "due_date": "2026-09-30"}], ensure_ascii=False), encoding="utf-8")
        tasks = read_tasks_file(legacy)
        self.assertEqual(tasks[0].text, "舊任務")

    def test_read_tasks_file_invalid_json_raises_value_error(self) -> None:
        bad = Path(self._tmp.name) / "bad.json"
        bad.write_text("nope", encoding="utf-8")
        with self.assertRaises(ValueError):
            read_tasks_file(bad)

    def test_save_reports_error(self) -> None:
        blocker = Path(self._tmp.name) / "file"
        blocker.write_text("x", encoding="utf-8")
        store = TodoStore(blocker / "todos.json")  # 父路徑是檔案，無法建立目錄
        self.assertIn("無法儲存", store.save([TodoTask("a")]))


class TestExportMarkdown(unittest.TestCase):
    def test_nested_checkboxes_links_and_inherited_done(self) -> None:
        tasks = [
            TodoTask("父", is_done=True, children=[TodoTask("子")]),
            TodoTask("連結", link="https://example.com"),
        ]
        self.assertEqual(
            export_markdown(tasks),
            "- [x] 父\n  - [x] 子\n- [ ] [連結](https://example.com)\n",
        )

    def test_empty_is_empty_string(self) -> None:
        self.assertEqual(export_markdown([]), "")


if __name__ == "__main__":
    unittest.main()
