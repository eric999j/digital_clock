"""TodoWindow 與到期提醒訊息格式測試（無顯示器時略過）。"""
import tempfile
import tkinter as tk
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.todo_commands import POSITION_AFTER, POSITION_BEFORE, POSITION_INTO, POSITION_PROMOTE, POSITION_ROOT
from services.todo_service import TodoService
from ui.main_window import DigitalClock
from ui.todo_window import TodoWindow, format_short_date

LIGHT = {'bg': '#FDF2E9', 'fg': '#8B4513'}
DARK = {'bg': '#1E3A5F', 'fg': '#A8D8FF'}


class StubConfigManager:
    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir

    def load_config(self, read_only: bool = False) -> dict:
        return {}

    def save_config(self, config: dict) -> None:
        pass


class TestFormatShortDate(unittest.TestCase):
    def test_same_year_short_and_other_year_full(self) -> None:
        today = date(2026, 11, 5)
        self.assertEqual(format_short_date(date(2026, 3, 4), today), "03/04")
        self.assertEqual(format_short_date(date(2027, 3, 4), today), "2027/03/04")
        self.assertEqual(format_short_date(None, today), "")


class TestTodoDueMessage(unittest.TestCase):
    def test_groups_by_status_and_sanitizes_markdown(self) -> None:
        message = DigitalClock._format_todo_due_message([
            {'text': '*粗體*', 'status': 'overdue', 'due_date': '2026-11-01', 'link': 'https://example.com'},
            {'text': '今日', 'status': 'today', 'due_date': '2026-11-05', 'link': 'javascript:alert(1)'},
        ])
        self.assertIn("**逾期（1 項）**", message)
        self.assertIn("**今日到期（1 項）**", message)
        self.assertIn("[＊粗體＊](https://example.com)", message)
        self.assertNotIn("javascript", message)

    def test_limit_adds_overflow_line(self) -> None:
        items = [{'text': str(i), 'status': 'today', 'due_date': '2026-11-05'} for i in range(5)]
        message = DigitalClock._format_todo_due_message(items, limit=2)
        self.assertIn("還有 3 項", message)


class TestTodoImportExportDialogs(unittest.TestCase):
    def test_import_offers_markdown_and_imports_selected_file(self) -> None:
        window = SimpleNamespace(service=MagicMock(), theme=LIGHT, _after_change=MagicMock(), _status_var=MagicMock())
        window.service.import_file.return_value = 1
        with patch("ui.todo_window.filedialog.askopenfilename", return_value="todo.md") as dialog:
            TodoWindow._import(window)
        self.assertIn("*.md", str(dialog.call_args.kwargs["filetypes"]))
        window.service.import_file.assert_called_once_with("todo.md")

    def test_export_confirms_before_opening_save_dialog(self) -> None:
        window = SimpleNamespace(theme=LIGHT, _export_markdown=MagicMock())
        with patch("ui.todo_window.themed_confirm") as confirm, patch("ui.todo_window.filedialog.asksaveasfilename") as save:
            TodoWindow._export(window)
        save.assert_not_called()
        self.assertIn("清空", confirm.call_args.args[1])
        self.assertIn("匯入會附加", confirm.call_args.args[1])
        confirm.call_args.args[2]()
        window._export_markdown.assert_called_once()


class TestTodoWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.root = tk.Tk()
        except tk.TclError as e:
            raise unittest.SkipTest(f"No display available: {e}") from e
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.root.destroy()

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.service = TodoService(StubConfigManager(Path(self._tmp.name)), MagicMock())
        self.closed: list[str] = []
        self.window = TodoWindow(self.root, self.service, LIGHT, on_close=self.closed.append)
        self.addCleanup(lambda: self.window.winfo_exists() and self.window.destroy())
        self.root.update()

    def tags(self, iid: str) -> tuple[str, ...]:
        return tuple(self.window.tree.item(iid, 'tags'))

    def test_quick_add_inserts_row_and_clears_entry(self) -> None:
        self.window._entry_var.set("新待辦")
        self.window._quick_add()
        (iid,) = self.window.tree.get_children()
        self.assertEqual(self.window.tree.item(iid, 'text'), "新待辦")
        self.assertEqual(self.window._entry_var.get(), "")
        self.assertIn("待辦 1", self.window._stats_var.get())

    def test_due_tags_and_priority_colors(self) -> None:
        today = date.today()
        overdue = self.service.add_task("逾期", due_date=today - timedelta(days=1))
        due_today = self.service.add_task("今日", due_date=today)
        soon = self.service.add_task("將到期", due_date=today + timedelta(days=2))
        high = self.service.add_task("高", priority="high")
        done = self.service.add_task("完成", due_date=today - timedelta(days=1), is_done=True)
        self.window.refresh()
        self.assertIn('bg_overdue', self.tags(overdue.id))
        self.assertIn('bg_today', self.tags(due_today.id))
        self.assertIn('bg_soon', self.tags(soon.id))
        self.assertIn('fg_high', self.tags(high.id))
        self.assertIn('fg_done', self.tags(done.id))
        self.assertFalse(any(t.startswith('bg_') for t in self.tags(done.id)))

    def test_parent_uses_bold_and_done_uses_strike_font_tags(self) -> None:
        parent = self.service.add_task("父")
        self.service.add_task("子", parent_id=parent.id)
        self.service.toggle_done([parent.id])
        self.window.refresh()
        self.assertIn('font_110', self.tags(parent.id))

    def test_search_filters_rows_and_shows_empty_hint(self) -> None:
        self.service.add_task("牛奶")
        self.service.add_task("麵包")
        self.window.refresh()
        self.window._search_var.set("牛")
        self.window._run_search()
        self.assertEqual(len(self.window.tree.get_children()), 1)
        self.window._search_var.set("不存在")
        self.window._run_search()
        self.assertEqual(self.window.tree.get_children(), ())
        self.assertIn("沒有符合", self.window._empty_label.cget("text"))

    def test_toggle_selected_and_undo_buttons(self) -> None:
        task = self.service.add_task("a")
        self.window.refresh()
        self.window.tree.selection_set(task.id)
        self.window._toggle_selected()
        self.assertTrue(task.is_done)
        self.assertIn('disabled', self.window._redo_button.state())
        self.window._undo()
        self.assertFalse(task.is_done)
        self.assertNotIn('disabled', self.window._redo_button.state())

    def test_collapsed_state_survives_refresh(self) -> None:
        parent = self.service.add_task("父")
        self.service.add_task("子", parent_id=parent.id)
        self.window.refresh()
        self.window._set_all_open(False)
        self.window.refresh()
        self.assertFalse(self.window.tree.item(parent.id, 'open'))

    def test_resolve_drop_positions(self) -> None:
        a = self.service.add_task("a")
        b = self.service.add_task("b")
        child = self.service.add_task("c", parent_id=a.id)
        self.window.refresh()
        top, height = 100, 20
        self.window.tree.bbox = MagicMock(return_value=(0, top, 200, height))  # 視窗未顯示時無版面可量
        resolve = self.window._resolve_drop
        self.assertEqual(resolve(a.id, b.id, top + 1, 0), (POSITION_BEFORE, b.id))
        self.assertEqual(resolve(a.id, b.id, top + height // 2, 0), (POSITION_INTO, b.id))
        self.assertEqual(resolve(a.id, b.id, top + height - 1, 0), (POSITION_AFTER, b.id))
        self.assertEqual(resolve(a.id, '', 0, 0), (POSITION_ROOT, None))
        self.assertEqual(resolve(child.id, b.id, top + 1, -40), (POSITION_PROMOTE, None))
        self.assertEqual(resolve(a.id, a.id, top, 0), (None, None))

    def test_apply_theme_recolors_tags_for_dark_clock_theme(self) -> None:
        task = self.service.add_task("逾期", due_date=date.today() - timedelta(days=1))
        self.window.refresh()
        light_bg = self.window.tree.tag_configure('bg_overdue', 'background')
        self.window.apply_theme(DARK)
        self.assertNotEqual(self.window.tree.tag_configure('bg_overdue', 'background'), light_bg)
        self.assertEqual(self.window.cget('bg'), DARK['bg'])
        self.assertIn('bg_overdue', self.tags(task.id))

    def test_header_is_gray_with_black_text_in_any_clock_theme(self) -> None:
        def header_labels() -> list[tk.Label]:
            return [w for w in self.window._header.winfo_children() if isinstance(w, tk.Label)]

        for theme in (LIGHT, DARK):
            self.window.apply_theme(theme)
            labels = header_labels()
            self.assertEqual([label.cget('text') for label in labels], ["項目", "完成", "專案", "優先級", "開始", "截止"])
            for label in labels:
                self.assertEqual(str(label.cget('fg')).lower(), '#000000')
                self.assertEqual(str(label.cget('bg')).lower(), '#d9d9d9')

    def _hit(self, iid: str, element: str = 'text', state: int = 0, column: str = '#0') -> SimpleNamespace:
        """模擬滑鼠落在指定列、欄的指定元件上（視窗未顯示時無版面可量）。"""
        self.window.tree.identify_row = MagicMock(return_value=iid)
        self.window.tree.identify_column = MagicMock(return_value=column)
        self.window.tree.identify_element = MagicMock(return_value=element)
        return SimpleNamespace(x=10, y=10, state=state)

    def test_click_on_link_text_opens_link_once_and_only_when_plain_click(self) -> None:
        linked = self.service.add_task("連結", link="https://example.com")
        plain = self.service.add_task("無連結")
        with patch("ui.todo_window.webbrowser.open_new_tab") as opener:
            self.window._maybe_open_link(self._hit(plain.id), plain.id)
            self.window._maybe_open_link(self._hit(linked.id, state=0x4), linked.id)  # Ctrl 多選
            self.window._maybe_open_link(self._hit(linked.id), plain.id)  # 按下與放開不同列
            opener.assert_not_called()

            self.window._maybe_open_link(self._hit(linked.id), linked.id)
            self.window._maybe_open_link(self._hit(linked.id), linked.id)  # 雙擊的第二下
            opener.assert_called_once_with("https://example.com")

    def test_click_on_other_column_of_linked_row_does_not_open(self) -> None:
        linked = self.service.add_task("連結", link="https://example.com")
        with patch("ui.todo_window.webbrowser.open_new_tab") as opener:
            self.window._maybe_open_link(self._hit(linked.id, element='cell'), linked.id)
            # 資料欄的文字（element 仍是 text）也不觸發
            self.window._maybe_open_link(self._hit(linked.id, column='#3'), linked.id)
        opener.assert_not_called()

    def test_unsafe_link_is_refused_with_error_popup(self) -> None:
        task = self.service.add_task("壞連結")
        task.link = "file:///C:/Windows/System32/calc.exe"
        with patch("ui.todo_window.webbrowser.open_new_tab") as opener, \
                patch("ui.todo_window.themed_error") as error:
            self.window._maybe_open_link(self._hit(task.id), task.id)
        opener.assert_not_called()
        error.assert_called_once()

    def test_double_click_on_link_text_does_not_open_edit_dialog(self) -> None:
        linked = self.service.add_task("連結", link="https://example.com")
        self.assertEqual(self.window._on_double_click(self._hit(linked.id)), 'break')

    def test_hover_shows_hand_cursor_only_over_link_text(self) -> None:
        linked = self.service.add_task("連結", link="https://example.com")
        plain = self.service.add_task("無連結")
        self.window._on_hover(self._hit(linked.id))
        self.assertEqual(str(self.window.tree.cget('cursor')), 'hand2')
        self.window._on_hover(self._hit(plain.id))
        self.assertEqual(str(self.window.tree.cget('cursor')), '')

    def test_close_reports_size_and_destroys(self) -> None:
        self.window.close()
        self.assertEqual(len(self.closed), 1)
        self.assertRegex(self.closed[0], r"^\d+x\d+$")
        self.assertFalse(self.window.winfo_exists())


if __name__ == "__main__":
    unittest.main()
