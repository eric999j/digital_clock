"""TodoService：CRUD、完成連鎖、移動、復原／重做、匯入與事件測試。"""
import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

from core.events import Events
from core.todo_commands import (
    POSITION_AFTER,
    POSITION_BEFORE,
    POSITION_INTO,
    POSITION_PROMOTE,
    POSITION_ROOT,
    CommandHistory,
)
from services.todo_service import TodoService


class StubConfigManager:
    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir
        self.config: dict = {}
        self.saved: list[dict] = []

    def load_config(self, read_only: bool = False) -> dict:
        return self.config if read_only else json.loads(json.dumps(self.config))

    def save_config(self, config: dict) -> None:
        self.config = config
        self.saved.append(config)


class TodoServiceTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.config_manager = StubConfigManager(self.dir)
        self.notify = MagicMock()
        self.service = TodoService(self.config_manager, self.notify)

    def reload(self) -> TodoService:
        return TodoService(self.config_manager, MagicMock())

    def texts(self, tasks=None) -> list[str]:
        return [t.text for t in (self.service.tasks if tasks is None else tasks)]


class TestCrudAndPersistence(TodoServiceTestBase):
    def test_add_task_persists_and_notifies_pending_count(self) -> None:
        task = self.service.add_task("  買牛奶  ", priority="high")
        self.assertEqual(task.text, "買牛奶")
        self.assertEqual(task.priority, "high")
        self.notify.assert_called_with(Events.TODO_UPDATED, 1)
        self.assertEqual(self.texts(self.reload().tasks), ["買牛奶"])

    def test_add_blank_text_is_rejected(self) -> None:
        self.assertIsNone(self.service.add_task("   "))
        self.notify.assert_not_called()

    def test_add_to_unknown_parent_is_rejected(self) -> None:
        self.assertIsNone(self.service.add_task("x", parent_id="missing"))
        self.assertEqual(self.service.tasks, [])

    def test_child_inherits_parent_project_unless_given(self) -> None:
        parent = self.service.add_task("父", project="Alpha")
        inherited = self.service.add_task("子1", parent_id=parent.id)
        explicit = self.service.add_task("子2", parent_id=parent.id, project="Beta")
        self.assertEqual(inherited.project, "Alpha")
        self.assertEqual(explicit.project, "Beta")

    def test_update_text_link_and_blank_normalization(self) -> None:
        task = self.service.add_task("a", link="https://example.com", project="P")
        self.assertTrue(self.service.update_task(task.id, text=" b ", link="", project=""))
        self.assertEqual((task.text, task.link, task.project), ("b", None, None))

    def test_update_rejects_blank_text_and_no_change(self) -> None:
        task = self.service.add_task("a")
        self.assertFalse(self.service.update_task(task.id, text=" "))
        self.assertFalse(self.service.update_task(task.id, text="a"))

    def test_update_project_cascades_to_descendants_and_undo_restores(self) -> None:
        parent = self.service.add_task("父")
        child = self.service.add_task("子", parent_id=parent.id, project="Old")
        self.service.update_task(parent.id, project="New")
        self.assertEqual(child.project, "New")
        self.service.undo()
        self.assertIsNone(parent.project)
        self.assertEqual(child.project, "Old")

    def test_delete_removes_subtree_and_skips_descendant_selection(self) -> None:
        parent = self.service.add_task("父")
        child = self.service.add_task("子", parent_id=parent.id)
        other = self.service.add_task("其他")
        self.assertTrue(self.service.delete_tasks([parent.id, child.id]))
        self.assertEqual(self.texts(), ["其他"])
        self.assertIsNone(self.service.find_task(child.id))
        self.assertIs(self.service.find_task(other.id), other)

    def test_delete_unknown_is_noop(self) -> None:
        self.service.add_task("a")
        self.notify.reset_mock()
        self.assertFalse(self.service.delete_tasks(["missing"]))
        self.assertFalse(self.service.delete_tasks([]))
        self.notify.assert_not_called()

    def test_delete_undo_restores_original_positions(self) -> None:
        a, b, c, d = (self.service.add_task(t) for t in "abcd")
        self.service.delete_tasks([b.id, d.id])
        self.assertEqual(self.texts(), ["a", "c"])
        self.service.undo()
        self.assertEqual(self.texts(), ["a", "b", "c", "d"])
        self.service.redo()
        self.assertEqual(self.texts(), ["a", "c"])

    def test_remove_link_undo_redo(self) -> None:
        task = self.service.add_task("a", link="https://example.com")
        self.assertTrue(self.service.remove_link(task.id))
        self.assertIsNone(task.link)
        self.service.undo()
        self.assertEqual(task.link, "https://example.com")
        self.assertFalse(self.service.remove_link(self.service.add_task("無連結").id))


class TestToggleDone(TodoServiceTestBase):
    def build(self):
        parent = self.service.add_task("父")
        c1 = self.service.add_task("c1", parent_id=parent.id)
        c2 = self.service.add_task("c2", parent_id=parent.id)
        grand = self.service.add_task("g", parent_id=c1.id)
        return parent, c1, c2, grand

    def test_completing_parent_completes_descendants(self) -> None:
        parent, c1, c2, grand = self.build()
        self.service.toggle_done([parent.id])
        self.assertTrue(all(t.is_done for t in (parent, c1, c2, grand)))

    def test_uncompleting_child_uncompletes_ancestors_and_descendants(self) -> None:
        parent, c1, c2, grand = self.build()
        self.service.toggle_done([parent.id])
        self.service.toggle_done([c1.id])
        self.assertFalse(parent.is_done)
        self.assertFalse(c1.is_done)
        self.assertFalse(grand.is_done)
        self.assertTrue(c2.is_done)

    def test_completing_child_alone_does_not_touch_others(self) -> None:
        parent, c1, c2, grand = self.build()
        self.service.toggle_done([c2.id])
        self.assertTrue(c2.is_done)
        self.assertFalse(parent.is_done)
        self.assertFalse(c1.is_done)

    def test_selecting_ancestor_and_descendant_toggles_once(self) -> None:
        parent, c1, _c2, _g = self.build()
        self.service.toggle_done([parent.id, c1.id])
        self.assertTrue(parent.is_done and c1.is_done)

    def test_undo_restores_exact_states(self) -> None:
        parent, c1, c2, grand = self.build()
        self.service.toggle_done([c2.id])
        self.service.toggle_done([parent.id])
        self.service.undo()
        self.assertEqual([t.is_done for t in (parent, c1, c2, grand)], [False, False, True, False])
        self.service.redo()
        self.assertTrue(all(t.is_done for t in (parent, c1, c2, grand)))

    def test_update_is_done_cascades(self) -> None:
        parent, c1, *_ = self.build()
        self.service.update_task(parent.id, is_done=True)
        self.assertTrue(c1.is_done)
        self.service.undo()
        self.assertFalse(parent.is_done or c1.is_done)

    def test_pending_count_tracks_leaf_tasks(self) -> None:
        parent, c1, c2, grand = self.build()
        self.assertEqual(self.service.pending_count(), 2)  # grand 與 c2
        self.service.toggle_done([c2.id])
        self.assertEqual(self.service.pending_count(), 1)


class TestMove(TodoServiceTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.a = self.service.add_task("a")
        self.b = self.service.add_task("b")
        self.c = self.service.add_task("c")
        self.child = self.service.add_task("child", parent_id=self.a.id)

    def test_move_before_and_after_on_same_level(self) -> None:
        self.assertTrue(self.service.move_task(self.c.id, self.a.id, POSITION_BEFORE))
        self.assertEqual(self.texts(), ["c", "a", "b"])
        self.assertTrue(self.service.move_task(self.c.id, self.b.id, POSITION_AFTER))
        self.assertEqual(self.texts(), ["a", "b", "c"])

    def test_move_after_when_task_precedes_target_adjusts_index(self) -> None:
        self.assertTrue(self.service.move_task(self.a.id, self.c.id, POSITION_AFTER))
        self.assertEqual(self.texts(), ["b", "c", "a"])

    def test_move_into_makes_child_and_inherits_project(self) -> None:
        self.service.update_task(self.b.id, project="Proj")
        self.assertTrue(self.service.move_task(self.c.id, self.b.id, POSITION_INTO))
        self.assertEqual(self.texts(self.b.children), ["c"])
        self.assertEqual(self.c.project, "Proj")
        self.service.undo()
        self.assertEqual(self.texts(), ["a", "b", "c"])
        self.assertIsNone(self.c.project)

    def test_promote_places_after_former_parent(self) -> None:
        self.assertTrue(self.service.move_task(self.child.id, None, POSITION_PROMOTE))
        self.assertEqual(self.texts(), ["a", "child", "b", "c"])
        self.assertEqual(self.a.children, [])

    def test_promote_top_level_is_rejected(self) -> None:
        self.assertFalse(self.service.move_task(self.a.id, None, POSITION_PROMOTE))

    def test_move_to_root_appends(self) -> None:
        self.assertTrue(self.service.move_task(self.child.id, None, POSITION_ROOT))
        self.assertEqual(self.texts(), ["a", "b", "c", "child"])

    def test_cannot_move_into_own_descendant_or_self(self) -> None:
        self.assertFalse(self.service.move_task(self.a.id, self.child.id, POSITION_INTO))
        self.assertFalse(self.service.move_task(self.a.id, self.a.id, POSITION_BEFORE))
        self.assertEqual(self.texts(), ["a", "b", "c"])

    def test_noop_moves_are_not_recorded(self) -> None:
        self.assertFalse(self.service.move_task(self.c.id, None, POSITION_ROOT))
        history_size = len(self.service.history.undo_stack)
        self.assertFalse(self.service.move_task(self.a.id, self.b.id, POSITION_BEFORE))
        self.assertEqual(len(self.service.history.undo_stack), history_size)

    def test_undo_redo_move_between_levels(self) -> None:
        self.service.move_task(self.c.id, self.a.id, POSITION_INTO)
        self.assertEqual(self.texts(self.a.children), ["child", "c"])
        self.service.undo()
        self.assertEqual(self.texts(), ["a", "b", "c"])
        self.service.redo()
        self.assertEqual(self.texts(self.a.children), ["child", "c"])


class TestHistory(TodoServiceTestBase):
    def test_add_undo_redo_keeps_same_task_id(self) -> None:
        task = self.service.add_task("a")
        self.service.undo()
        self.assertEqual(self.service.tasks, [])
        self.service.redo()
        self.assertEqual(self.service.tasks[0].id, task.id)

    def test_new_command_clears_redo(self) -> None:
        self.service.add_task("a")
        self.service.undo()
        self.assertTrue(self.service.history.can_redo())
        self.service.add_task("b")
        self.assertFalse(self.service.history.can_redo())

    def test_undo_when_empty_returns_false(self) -> None:
        self.assertFalse(self.service.undo())
        self.assertFalse(self.service.redo())

    def test_undo_persists_to_disk(self) -> None:
        self.service.add_task("a")
        self.service.undo()
        self.assertEqual(self.reload().tasks, [])

    def test_history_is_capped(self) -> None:
        for i in range(CommandHistory.MAX_HISTORY_SIZE + 5):
            self.service.add_task(str(i))
        self.assertEqual(len(self.service.history.undo_stack), CommandHistory.MAX_HISTORY_SIZE)


class TestImportExport(TodoServiceTestBase):
    def write_legacy(self, payload) -> Path:
        path = self.dir / "legacy.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_import_legacy_list_appends_and_is_undoable(self) -> None:
        self.service.add_task("既有")
        path = self.write_legacy([{"id": "x1", "text": "舊1", "children": [{"id": "x2", "text": "舊1-1"}]}, {"text": "舊2"}])
        self.assertEqual(self.service.import_file(path), 2)
        self.assertEqual(self.texts(), ["既有", "舊1", "舊2"])
        self.service.undo()
        self.assertEqual(self.texts(), ["既有"])

    def test_import_regenerates_conflicting_ids(self) -> None:
        existing = self.service.add_task("既有")
        path = self.write_legacy([{"id": existing.id, "text": "撞 id"}])
        self.service.import_file(path)
        ids = [t.id for t in self.service.iter_tasks()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_import_invalid_file_raises_and_keeps_state(self) -> None:
        self.service.add_task("既有")
        bad = self.dir / "bad.json"
        bad.write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.service.import_file(bad)
        with self.assertRaises(OSError):
            self.service.import_file(self.dir / "missing.json")
        self.assertEqual(self.texts(), ["既有"])

    def test_export_markdown(self) -> None:
        parent = self.service.add_task("父")
        self.service.add_task("子", parent_id=parent.id)
        self.assertEqual(self.service.export_markdown(), "- [ ] 父\n  - [ ] 子\n")

    def test_import_markdown_appends_and_is_undoable(self) -> None:
        self.service.add_task("既有")
        path = self.dir / "todo.md"
        path.write_text("- [x] 新項目\n  - [ ] 子項\n", encoding="utf-8")
        self.assertEqual(self.service.import_file(path), 1)
        self.assertEqual(self.texts(), ["既有", "新項目"])
        self.assertEqual(self.service.tasks[1].children[0].text, "子項")
        self.assertTrue(self.service.undo())
        self.assertEqual(self.texts(), ["既有"])


class TestDualExport(TodoServiceTestBase):
    def make_rich_task(self):
        return self.service.add_task(
            "完整", priority="high", due_date=date(2026, 12, 1), project="專案A", link="https://example.com",
        )

    def test_json_export_roundtrips_all_fields_via_restore(self) -> None:
        task = self.make_rich_task()
        self.service.add_task("子", parent_id=task.id)
        path = self.dir / "backup.json"
        self.assertEqual(self.service.export_to_file(path), "json")

        other = TodoService(StubConfigManager(self.dir / "other"), MagicMock())
        self.assertEqual(other.restore_backup(path), 1)
        restored = other.tasks[0]
        self.assertEqual(
            (restored.id, restored.priority, restored.due_date, restored.project, restored.link),
            (task.id, "high", date(2026, 12, 1), "專案A", "https://example.com"),
        )
        self.assertEqual(self.texts(restored.children), ["子"])

    def test_markdown_export_is_readable_and_lossy(self) -> None:
        self.make_rich_task()
        path = self.dir / "todo.md"
        self.assertEqual(self.service.export_to_file(path), "md")
        content = path.read_text(encoding="utf-8")
        self.assertEqual(content, "- [ ] [完整](https://example.com)\n")

    def test_export_rejects_unknown_extension(self) -> None:
        with self.assertRaises(ValueError):
            self.service.export_to_file(self.dir / "todo.txt")

    def test_restore_replaces_everything_and_is_undoable(self) -> None:
        backup_service = TodoService(StubConfigManager(self.dir / "b"), MagicMock())
        backup_service.add_task("備份項")
        path = self.dir / "backup.json"
        backup_service.export_to_file(path)

        self.service.add_task("現有1")
        self.service.add_task("現有2")
        self.notify.reset_mock()
        self.assertEqual(self.service.restore_backup(path), 1)
        self.assertEqual(self.texts(), ["備份項"])
        self.notify.assert_called_once_with(Events.TODO_UPDATED, 1)
        self.assertEqual(self.reload().tasks[0].text, "備份項")

        self.assertTrue(self.service.undo())
        self.assertEqual(self.texts(), ["現有1", "現有2"])
        self.assertTrue(self.service.redo())
        self.assertEqual(self.texts(), ["備份項"])

    def test_restore_rejects_markdown_and_newer_version(self) -> None:
        self.service.add_task("既有")
        md = self.dir / "todo.md"
        md.write_text("- [ ] x\n", encoding="utf-8")
        newer = self.dir / "newer.json"
        newer.write_text(json.dumps({"version": 99, "tasks": []}), encoding="utf-8")
        for path in (md, newer):
            with self.assertRaises(ValueError):
                self.service.restore_backup(path)
        self.assertEqual(self.texts(), ["既有"])


class TestDueReminder(TodoServiceTestBase):
    NOW = datetime(2026, 11, 5, 9, 0, 0)  # 週四整點

    def setUp(self) -> None:
        super().setUp()
        self.service.add_task("逾期", due_date=date(2026, 11, 1), start_date=date(2026, 10, 1))
        self.notify.reset_mock()

    def test_notifies_due_tasks_once_per_hour(self) -> None:
        config = {"todo": {"remind_enabled": True, "start_hour": 9, "end_hour": 17, "work_days_only": True}}
        self.service.check(self.NOW, config)
        self.assertEqual(self.notify.call_count, 1)
        event, items = self.notify.call_args.args
        self.assertEqual(event, Events.TODO_DUE)
        self.assertEqual(items[0]["status"], "overdue")
        self.service.check(self.NOW.replace(second=30), config)
        self.assertEqual(self.notify.call_count, 1)

    def test_skips_when_vacation_or_hourly_paused(self) -> None:
        base = {"todo": {"remind_enabled": True, "start_hour": 9, "end_hour": 17}}
        self.service.check(self.NOW, {**base, "on_vacation": True})
        self.service.check(self.NOW, {**base, "hourly_web_reminder": {"paused": True}})
        self.notify.assert_not_called()

    def test_remind_toggle_roundtrip(self) -> None:
        self.assertTrue(self.service.is_remind_enabled())
        self.service.set_remind_enabled(False)
        self.assertFalse(self.service.is_remind_enabled())
        self.assertFalse(self.config_manager.saved[-1]["todo"]["remind_enabled"])


if __name__ == "__main__":
    unittest.main()
