import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.test_task_xml_importer import _EXEC, _WEEKDAY_TRIGGER, _task_xml, _utf16
from ui.hourly_web_window import HourlyWebWindow, _ensure_min_height


class TestEnsureMinHeight(unittest.TestCase):
    def test_raises_small_height_only(self):
        self.assertEqual(_ensure_min_height("560x430"), "560x520")
        self.assertEqual(_ensure_min_height("560x600"), "560x600")
        self.assertEqual(_ensure_min_height("bad"), "bad")


class TestHourlyLaunchWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as e:
            raise unittest.SkipTest(f"無可用顯示器: {e}")
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        self.callback = MagicMock()
        self.window = HourlyWebWindow(self.root, self.callback, {'bg': '#1C1C1C', 'fg': '#FFBF00'}, {})
        self.errors: list[str] = []
        self.window._show_error = self.errors.append

    def tearDown(self):
        if self.window.winfo_exists():
            self.window.destroy()

    def _select_type(self, label: str) -> None:
        self.window._type_combo.set(label)
        self.window._on_type_changed()

    def test_program_fields_only_visible_for_program_type(self):
        self.window.update_idletasks()
        self.assertFalse(self.window._add_args_entry.winfo_manager())
        self._select_type('程式')
        self.assertTrue(self.window._add_args_entry.winfo_manager())
        self.assertEqual(self.window._target_label.cget('text'), '程式:')
        self._select_type('網頁')
        self.assertFalse(self.window._add_args_entry.winfo_manager())

    def test_add_url_rule_keeps_legacy_shape(self):
        self.window._add_url_entry.insert(0, 'https://a.example')
        self.window._add_rule()
        self.assertEqual(self.window._rules, [{'url': 'https://a.example', 'start_hour': 8, 'end_hour': 17}])

    def test_add_program_rule(self):
        import sys
        self._select_type('程式')
        self.window._add_url_entry.insert(0, sys.executable)
        self.window._add_args_entry.insert(0, 'job.py')
        self.window._add_rule()
        rule = self.window._rules[0]
        self.assertEqual((rule['type'], rule['command'], rule['arguments']), ('program', sys.executable, 'job.py'))
        self.assertEqual(self.window._add_url_entry.get(), '')
        self.assertIn('[程式]', self.window._rules_listbox.get(0))

    def test_invalid_inputs_show_error_and_add_nothing(self):
        self.window._add_rule()  # 空白
        self.window._add_url_entry.insert(0, 'file:///etc/passwd')
        self.window._add_rule()  # 不安全 URL
        self.window._add_url_entry.delete(0, tk.END)
        self._select_type('程式')
        self.window._add_url_entry.insert(0, 'definitely_missing_tool_xyz')
        self.window._add_rule()  # 找不到程式
        self.assertEqual(len(self.errors), 3)
        self.assertEqual(self.window._rules, [])

    def test_import_xml_adds_rules_and_skips_duplicates_on_reimport(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'task.xml'
            path.write_bytes(_utf16(_task_xml(_WEEKDAY_TRIGGER, _EXEC)))
            with patch('ui.hourly_web_window.filedialog.askopenfilename', return_value=str(path)), \
                    patch('ui.hourly_web_window.themed_info') as info:
                self.window._import_xml()
                self.window._import_xml()

        self.assertEqual(len(self.window._rules), 1)
        first_msg, second_msg = (c.args[1] for c in info.call_args_list)
        self.assertIn('已匯入 1 條規則', first_msg)
        self.assertIn('1 條重複已略過', second_msg)
        self.assertIn('週一至週五', self.window._rules_listbox.get(0))
        self.callback.assert_not_called()  # 未按儲存前不寫入設定

    def test_import_invalid_xml_shows_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.xml'
            path.write_text('<html/>', encoding='utf-8')
            with patch('ui.hourly_web_window.filedialog.askopenfilename', return_value=str(path)):
                self.window._import_xml()
        self.assertEqual(len(self.errors), 1)
        self.assertEqual(self.window._rules, [])

    def test_import_cancelled_does_nothing(self):
        with patch('ui.hourly_web_window.filedialog.askopenfilename', return_value=''):
            self.window._import_xml()
        self.assertEqual(self.errors, [])

    def test_submit_includes_pending_form_rule_and_closes(self):
        self.window._add_url_entry.insert(0, 'https://pending.example')
        self.window._on_submit()
        self.callback.assert_called_once()
        self.assertEqual(self.callback.call_args.args[0][0]['url'], 'https://pending.example')

    def test_double_click_does_not_launch_program_rule(self):
        self.window._refresh_listbox([{'type': 'program', 'command': 'x.exe', 'start_hour': 9, 'end_hour': 9}])
        self.window._rules_listbox.selection_set(0)
        with patch('ui.hourly_web_window.webbrowser.open') as web, \
                patch('ui.hourly_web_window.launch_program') as launch:
            self.window._open_selected_rule_url(None)
        web.assert_not_called()
        launch.assert_not_called()

    def _imported_rule(self) -> dict:
        return {'type': 'program', 'command': 'C:\\missing\\python.exe', 'arguments': 'job.py',
                'working_dir': 'C:\\Daily', 'start_hour': 9, 'end_hour': 9,
                'weekdays': [0, 1, 2, 3, 4], 'name': '最新公告'}

    def _edit(self, index: int = 0) -> None:
        self.window._rules_listbox.selection_set(index)
        self.window._edit_rule()

    def test_form_has_no_working_dir_field(self):
        self.assertFalse(hasattr(self.window, '_add_cwd_entry'))

    def test_edit_loads_rule_into_form(self):
        self.window._refresh_listbox([self._imported_rule()])
        self._edit()
        self.assertEqual(self.window._add_url_entry.get(), 'C:\\missing\\python.exe')
        self.assertEqual(self.window._add_args_entry.get(), 'job.py')
        self.assertEqual((self.window._start_combo.get(), self.window._end_combo.get()), ('09:00', '09:00'))
        self.assertEqual(self.window._submit_btn.cget('text'), '更新 ✓')

    def test_edit_imported_rule_preserves_hidden_fields(self):
        self.window._refresh_listbox([self._imported_rule()])
        self._edit()
        self.window._end_combo.set('10:00')
        self.window._add_args_entry.delete(0, tk.END)
        self.window._add_args_entry.insert(0, 'new.py')
        self.window._add_rule()

        self.assertEqual(self.errors, [])  # 未更動的缺少程式路徑不應擋下編輯
        self.assertEqual(self.window._rules, [{**self._imported_rule(), 'arguments': 'new.py', 'end_hour': 10}])
        self.assertIsNone(self.window._editing_index)
        self.assertEqual(self.window._submit_btn.cget('text'), '新增 ＋')

    def test_edit_changed_missing_program_is_rejected(self):
        self.window._refresh_listbox([self._imported_rule()])
        self._edit()
        self.window._add_url_entry.delete(0, tk.END)
        self.window._add_url_entry.insert(0, 'definitely_missing_tool_xyz')
        self.window._add_rule()
        self.assertEqual(len(self.errors), 1)
        self.assertEqual(self.window._rules[0]['command'], 'C:\\missing\\python.exe')

    def test_edit_url_rule_keeps_weekdays_and_saves_via_submit(self):
        self.window._refresh_listbox([{'url': 'https://a.example', 'start_hour': 8, 'end_hour': 9,
                                       'weekdays': [5, 6]}])
        self._edit()
        self.window._add_url_entry.delete(0, tk.END)
        self.window._add_url_entry.insert(0, 'https://b.example')
        self.window._on_submit()
        self.callback.assert_called_once_with(
            [{'url': 'https://b.example', 'weekdays': [5, 6], 'start_hour': 8, 'end_hour': 9}])

    def test_edit_type_change_drops_program_only_fields(self):
        self.window._refresh_listbox([self._imported_rule()])
        self._edit()
        self._select_type('網頁')
        self.window._add_url_entry.delete(0, tk.END)
        self.window._add_url_entry.insert(0, 'https://a.example')
        self.window._add_rule()
        self.assertEqual(self.window._rules, [{'url': 'https://a.example', 'weekdays': [0, 1, 2, 3, 4],
                                               'start_hour': 9, 'end_hour': 9}])

    def test_cancel_edit_and_remove_leave_edit_mode(self):
        self.window._refresh_listbox([self._imported_rule()])
        self._edit()
        self.window._end_edit()
        self.assertEqual(self.window._add_url_entry.get(), '')
        self.assertEqual(len(self.window._rules), 1)
        self._edit()
        self.window._remove_rule()
        self.assertIsNone(self.window._editing_index)
        self.assertEqual(self.window._rules, [])

    def test_context_menu_has_edit_entry(self):
        menu = self.window._rules_menu
        labels = [menu.entrycget(i, 'label') for i in range(menu.index(tk.END) + 1)]
        self.assertEqual(labels, ['編輯規則', '刪除此規則'])

    def test_loads_legacy_single_url_config(self):
        window = HourlyWebWindow(self.root, self.callback, None,
                                 {'url': 'https://old.example', 'start_hour': 7, 'end_hour': 9})
        try:
            self.assertEqual(window._rules, [{'url': 'https://old.example', 'start_hour': 7, 'end_hour': 9}])
        finally:
            window.destroy()


if __name__ == '__main__':
    unittest.main()
