import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services.config_service import ConfigManager


class TestContextMenuIntegration(unittest.TestCase):
    """以真實 DigitalClock 驗證右鍵選單：_show_context_menu 會吞掉例外，只能靠日誌與 tk_popup 判斷。"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._home = patch.object(Path, "home", return_value=Path(cls._tmp.name))
        cls._home.start()
        # 無頭 CI（xvfb）上真實 pynput 監聽可能卡死，右鍵選單測試不需要它
        cls._keyboard = patch("services.keyboard_service.KeyboardService.start")
        cls._keyboard.start()
        # 初始化失敗時 DigitalClock 會跳 messagebox，無頭環境會永遠阻塞
        cls._showerror = patch("ui.main_window.messagebox.showerror")
        cls._showerror.start()
        try:
            from ui.main_window import DigitalClock

            cls.clock = DigitalClock(ConfigManager())
        except tk.TclError as e:
            cls._showerror.stop()
            cls._keyboard.stop()
            cls._home.stop()
            cls._tmp.cleanup()
            raise unittest.SkipTest(f"No display available: {e}") from e
        cls.clock.root.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.clock.logic.on_close()
        finally:
            cls._showerror.stop()
            cls._keyboard.stop()
            cls._home.stop()
            cls._tmp.cleanup()

    @staticmethod
    def _labels(menu):
        end = menu.index("end")
        if end is None:
            return []
        return ["---" if menu.type(i) == "separator" else menu.entrycget(i, "label") for i in range(end + 1)]

    def test_right_click_shows_menu_without_errors(self):
        clock = self.clock
        event = SimpleNamespace(x_root=100, y_root=100)

        with patch("ui.main_window.logger") as log, patch.object(clock.context_menu, "tk_popup") as popup:
            clock._show_context_menu(event)

        log.error.assert_not_called()
        popup.assert_called_once_with(100, 100)

    def test_dynamic_submenus_are_exposed_as_attributes(self):
        menu = self.clock.context_menu
        for name in ("pomodoro_menu", "hourly_web_menu", "todo_menu", "countdown_menu", "timezone_menu"):
            with self.subTest(attribute=name):
                self.assertTrue(hasattr(menu, name))

    def test_timezone_is_first_entry_of_clock_settings(self):
        menu = self.clock.context_menu
        labels = self._labels(menu)
        settings = menu.nametowidget(menu.entrycget(labels.index("時鐘設定"), "menu"))

        self.assertEqual(self._labels(settings)[:2], ["多時區", "---"])
        self.assertIs(settings.nametowidget(settings.entrycget(0, "menu")), menu.timezone_menu)

    def test_random_theme_is_last_and_saved_theme_is_selectable(self):
        clock = self.clock
        menu = clock.context_menu
        original = clock.config['appearance']['theme']
        try:
            menu.open_theme_menu()
            self.assertEqual(menu._theme_list.get(tk.END), '隨機配色')
            menu._select_theme('__random__')
            generated = dict(clock._get_current_theme())
            self.assertEqual(clock.config['appearance']['theme'], '__random__')
            clock._save_named_theme('測試收藏', generated)
            key = clock.config['appearance']['theme']
            self.assertIn('測試收藏', menu._theme_list.get(0, tk.END))
            self.assertEqual(menu._theme_list.get(tk.END), '隨機配色')
            menu._select_theme(key)
            self.assertEqual(clock._get_current_theme()['bg'], generated['bg'])
            self.assertEqual(clock.config['appearance']['theme'], key)
            clock.logic.flush_pending_save()
            reloaded = ConfigManager().load_config()
            self.assertEqual(reloaded['appearance']['theme'], key)
            self.assertEqual(reloaded['themes'][key], clock.config['themes'][key])
            menu._select_theme('__random__')
            self.assertEqual(clock.config['themes'][key]['bg'], generated['bg'])
        finally:
            clock.apply_theme(original, save=False)
            clock.config['themes'].pop('__random__', None)
            if 'key' in locals():
                clock.config['themes'].pop(key, None)
            clock.context_menu.refresh_theme_menu()
            menu._theme_window.destroy()

    def test_right_click_theme_offers_delete_and_persists_builtin_removal(self):
        clock = self.clock
        menu = clock.context_menu
        original_theme = clock.config['appearance']['theme']
        original_themes = dict(clock.config['themes'])
        original_deleted = list(clock.config.get('deleted_themes', []))
        try:
            menu.open_theme_menu()
            clock.root.update()
            index = menu._theme_keys.index('green')
            bounds = menu._theme_list.bbox(index)
            popup = menu._theme_context_menu
            with patch.object(popup, 'tk_popup') as post:
                menu._theme_list.event_generate('<Button-3>', x=5, y=bounds[1] + 2)
                post.assert_called_once()
                self.assertTrue(popup.winfo_exists())
                self.assertEqual(popup.entrycget(0, 'label'), '刪除配色')
                popup.invoke(0)
                clock.root.update()
            confirm = next(child for child in clock.root.winfo_children()
                           if isinstance(child, tk.Toplevel) and child.title() == '刪除配色')
            outer = confirm.winfo_children()[0]
            buttons = outer.winfo_children()[-1]
            next(button for button in buttons.winfo_children() if button.cget('text') == '刪除').invoke()
            clock.root.update()
            clock.logic.flush_pending_save()
            self.assertNotIn('green', ConfigManager().load_config()['themes'])
            self.assertNotIn('green', menu._theme_keys)
        finally:
            clock.config['themes'] = original_themes
            clock.config['deleted_themes'] = original_deleted
            clock.apply_theme(original_theme, save=False)
            menu._theme_window.destroy()

    def test_save_theme_dialog_accepts_a_name(self):
        clock = self.clock
        original = clock.config['appearance']['theme']
        before = set(clock.config['themes'])
        try:
            clock.save_current_theme()
            dialog = next(child for child in clock.root.winfo_children()
                          if isinstance(child, tk.Toplevel) and child.title() == '儲存目前配色')
            frame = dialog.winfo_children()[0]
            entry = next(child for child in frame.winfo_children() if isinstance(child, tk.Entry))
            entry.insert(0, '自訂測試')
            buttons = next(child for child in frame.winfo_children() if isinstance(child, tk.Frame))
            next(child for child in buttons.winfo_children() if child.cget('text') == '儲存').invoke()
            self.assertFalse(dialog.winfo_exists())
            self.assertEqual(clock._get_current_theme()['name'], '自訂測試')
        finally:
            clock.apply_theme(original, save=False)
            for key in set(clock.config['themes']) - before:
                del clock.config['themes'][key]
            clock.context_menu.refresh_theme_menu()

    def test_delete_custom_and_random_themes(self):
        clock = self.clock
        menu = clock.context_menu
        original_theme = clock.config['appearance']['theme']
        original_themes = dict(clock.config['themes'])
        try:
            menu.open_theme_menu()
            clock.apply_random_theme()
            clock._save_named_theme('待刪收藏', dict(clock._get_current_theme()))
            custom_key = clock.config['appearance']['theme']
            clock._delete_theme(custom_key)
            self.assertNotEqual(clock.config['appearance']['theme'], custom_key)
            self.assertNotIn(custom_key, clock.config['themes'])
            clock._delete_theme('__random__')
            self.assertNotIn('__random__', clock.config['themes'])
            clock.logic.flush_pending_save()
            loaded = ConfigManager().load_config()
            self.assertNotIn(custom_key, loaded['themes'])
            self.assertNotIn('__random__', loaded['themes'])
            self.assertEqual(menu._theme_list.get(tk.END), '隨機配色')
        finally:
            clock.config['themes'] = original_themes
            clock.apply_theme(original_theme, save=False)
            menu._theme_window.destroy()

    def test_productivity_menu_sits_below_hourly_web_and_holds_pomodoro_and_countdown(self):
        menu = self.clock.context_menu
        labels = self._labels(menu)
        self.assertEqual(labels[labels.index("待辦事項") + 1:labels.index("待辦事項") + 5],
                         ["---", "通知中心…", "---", "效率提升"])

        productivity = menu.nametowidget(menu.entrycget(labels.index("效率提升"), "menu"))
        self.assertEqual(self._labels(productivity), ["番茄鐘", "倒數計時"])
        self.assertIs(productivity.nametowidget(productivity.entrycget(0, "menu")), menu.pomodoro_menu)
        self.assertIs(productivity.nametowidget(productivity.entrycget(1, "menu")), menu.countdown_menu)

    def test_nested_submenus_receive_theme_colors(self):
        clock = self.clock
        theme = clock.config['themes'][clock.config['appearance']['theme']]
        clock._menu_color_cache_key = None
        clock._update_menu_colors(clock.context_menu)

        for sub in (clock.context_menu.pomodoro_menu, clock.context_menu.countdown_menu):
            self.assertEqual(str(sub.cget("bg")), theme['bg'])
            self.assertEqual(str(sub.cget("fg")), theme['fg'])

    def test_pomodoro_menu_offers_pause_and_cancel_only_while_running(self):
        clock = self.clock
        menu = clock.context_menu.pomodoro_menu
        menu.update_menu()
        self.assertEqual(self._labels(menu), ["開始專注"])

        clock.logic.pomodoro.start_focus()
        try:
            menu.update_menu()
            self.assertEqual(self._labels(menu), ["暫停", "取消番茄鐘", "---", "開始專注"])

            menu.invoke(0)
            self.assertTrue(clock.logic.pomodoro.is_paused)
            self.assertTrue(clock._pomodoro_line.endswith("(暫停)"))
            menu.update_menu()
            self.assertEqual(self._labels(menu)[0], "繼續")

            menu.invoke(0)
            self.assertFalse(clock.logic.pomodoro.is_paused)
            self.assertFalse(clock._pomodoro_line.endswith("(暫停)"))

            menu.invoke(1)
            self.assertEqual(clock.logic.pomodoro.phase, "IDLE")
            self.assertEqual(clock._pomodoro_line, "")
        finally:
            clock.logic.pomodoro.stop()

    def test_todo_menu_sits_between_hourly_and_productivity(self):
        labels = self._labels(self.clock.context_menu)
        start = labels.index("整點啟動")
        self.assertEqual(labels[start:start + 7],
                         ["整點啟動", "---", "待辦事項", "---", "通知中心…", "---", "效率提升"])
        self.assertEqual(self._labels(self.clock.context_menu.hourly_web_menu), ["設定", "暫停"])
        self.assertEqual(self._labels(self.clock.context_menu.todo_menu), ["開啟待辦事項…", "整點提醒到期待辦"])

    def test_notification_menu_shows_unread_count(self):
        menu = self.clock.context_menu
        center = self.clock.logic.notification_center
        center.add("reminder", "t", "m")
        try:
            menu.refresh_notification_menu()
            self.assertIn("通知中心（1 則未讀）…", self._labels(menu))
            center.mark_all_read()
            menu.refresh_notification_menu()
            self.assertIn("通知中心…", self._labels(menu))
        finally:
            center.clear()

    def test_todo_remind_checkbutton_toggles_setting(self):
        clock = self.clock
        menu = clock.context_menu.todo_menu
        before = clock.logic.is_todo_remind_enabled()
        try:
            menu.invoke(1)
            self.assertEqual(clock.logic.is_todo_remind_enabled(), not before)
            clock.context_menu.refresh_todo_menu()
            self.assertEqual(clock.context_menu.todo_remind_var.get(), not before)
        finally:
            if clock.logic.is_todo_remind_enabled() != before:
                clock.logic.toggle_todo_remind()

    def test_info_line_shows_pending_todo_count(self):
        clock = self.clock
        task = clock.logic.todo_service.add_task("資訊列待辦")
        try:
            self.assertIn("待辦 1 項", clock._compose_info_lines())
            clock.config['todo']['show_in_info_bar'] = False
            self.assertFalse(any(line.startswith("待辦") for line in clock._compose_info_lines()))
        finally:
            clock.config['todo']['show_in_info_bar'] = True
            clock.logic.todo_service.delete_tasks([task.id])
        self.assertFalse(any(line.startswith("待辦") for line in clock._compose_info_lines()))

    def test_todo_window_is_single_instance_and_follows_clock_theme(self):
        clock = self.clock
        themes = clock.config['themes']
        original = clock.config['appearance']['theme']
        other = next(key for key in themes if key != original)
        clock._on_open_todo_window()
        clock.root.update()
        window = clock._live_todo_window()
        try:
            self.assertIsNotNone(window)
            clock._on_open_todo_window()
            clock.root.update()
            self.assertIs(clock._live_todo_window(), window)

            clock.apply_theme(other, save=False)
            self.assertEqual(str(window.cget('bg')), themes[other]['bg'])
        finally:
            clock.apply_theme(original, save=False)
            if window is not None:
                window.close()
        self.assertIsNone(clock._live_todo_window())
        self.assertRegex(clock.config['ui_behavior']['todo_window_geometry'], r"^\d+x\d+$")

    def test_countdown_menu_has_no_remaining_entry(self):
        clock = self.clock
        clock.logic.start_countdown(300)
        try:
            menu = clock.context_menu.countdown_menu
            menu.update_menu()
            labels = self._labels(menu)
            self.assertEqual(labels[:3], ["暫停", "取消倒數", "---"])
            self.assertFalse(any("剩餘" in label for label in labels))
        finally:
            clock.logic.cancel_countdown()

    def test_top_level_menu_order_and_reminder_placement(self):
        labels = self._labels(self.clock.context_menu)
        entries = [label for label in labels if label != "---"]

        self.assertEqual(entries, ["勿擾模式", "提醒", "整點啟動", "待辦事項", "通知中心…", "效率提升", "時鐘設定", "離開"])
        # 不應出現連續或頭尾的分隔線
        self.assertNotEqual(labels[0], "---")
        self.assertNotEqual(labels[-1], "---")
        self.assertFalse(any(a == b == "---" for a, b in zip(labels, labels[1:], strict=False)))

    def _walk(self, menu, path=()):
        """走訪選單樹，產生 (路徑, 選單, 索引, 項目型別)。"""
        end = menu.index("end")
        if end is None:
            return
        for i in range(end + 1):
            kind = menu.type(i)
            if kind == "separator":
                continue
            label = menu.entrycget(i, "label")
            yield path + (label,), menu, i, kind
            if kind == "cascade":
                yield from self._walk(menu.nametowidget(menu.entrycget(i, "menu")), path + (label,))

    def _assert_all_entries_clickable(self):
        for path, menu, index, kind in self._walk(self.clock.context_menu):
            with self.subTest(entry=" > ".join(path)):
                command = str(menu.entrycget(index, "command")) if kind != "cascade" else ""
                if str(menu.entrycget(index, "state")) == "disabled":
                    # 停用項目只能是無動作的提示文字（如「無提醒事項」），不可是被誤停用的功能
                    self.assertFalse(command, "有動作的項目不可被停用")
                elif kind == "cascade":
                    self.assertTrue(menu.entrycget(index, "menu"))
                else:
                    self.assertTrue(command)

    def test_every_menu_entry_is_clickable_when_idle(self):
        self.clock.context_menu.countdown_menu.update_menu()
        self._assert_all_entries_clickable()

    def test_every_menu_entry_is_clickable_during_countdown_and_pomodoro(self):
        clock = self.clock
        clock.logic.start_countdown(300)
        clock.logic.pomodoro.start_focus()
        try:
            clock.context_menu.countdown_menu.update_menu()
            self._assert_all_entries_clickable()
        finally:
            clock.logic.cancel_countdown()
            clock.logic.pomodoro.stop()

    def test_pomodoro_focus_is_shown_below_the_clock(self):
        clock = self.clock
        clock.logic.pomodoro.start_focus()
        try:
            lines = clock._compose_info_lines()
            self.assertIn("專注 25:00", lines[0])
            self.assertEqual(clock._info_lines[0], lines[0])
        finally:
            clock.logic.pomodoro.stop()
        self.assertFalse(any(line.startswith("專注") for line in clock._compose_info_lines()))

    def test_info_band_redraw_does_not_reconfigure_font_when_size_is_unchanged(self):
        # 重設使用中的具名字型會讓 Windows 上開啟中的右鍵選單被關閉
        clock = self.clock
        clock.logic.pomodoro.start_focus()
        try:
            with patch.object(clock._info_font, "configure") as configure:
                clock._render_info_band()
                clock._render_info_band()
            configure.assert_not_called()
        finally:
            clock.logic.pomodoro.stop()

    def test_info_band_font_still_shrinks_to_fit_narrow_window(self):
        clock = self.clock
        clock.logic.pomodoro.start_focus()
        original_width = clock.config['window']['width']
        size_before = int(clock._info_font.cget("size"))
        try:
            clock.config['window']['width'] = 40
            clock._render_info_band()
            self.assertLess(int(clock._info_font.cget("size")), size_before)
        finally:
            clock.config['window']['width'] = original_width
            clock._render_info_band()
            clock.logic.pomodoro.stop()
        self.assertEqual(int(clock._info_font.cget("size")), size_before)

    def test_window_is_not_resized_while_menu_is_open(self):
        clock = self.clock
        lines_before = list(clock._info_lines)

        clock._context_menu_open = True
        try:
            clock._set_info_lines([*lines_before, "新增一行"])
            self.assertEqual(clock._info_lines, lines_before)
        finally:
            clock._context_menu_open = False

    def test_deferred_info_lines_are_applied_after_menu_closes(self):
        clock = self.clock
        with patch.object(
            clock.context_menu, "tk_popup", side_effect=lambda *a: clock.logic.pomodoro.start_focus(),
        ):
            clock._show_context_menu(SimpleNamespace(x_root=0, y_root=0))
        try:
            self.assertFalse(clock._context_menu_open)
            self.assertTrue(any(line.startswith("專注") for line in clock._info_lines))
        finally:
            clock.logic.pomodoro.stop()


if __name__ == "__main__":
    unittest.main()
