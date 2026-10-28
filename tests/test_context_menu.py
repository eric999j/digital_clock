import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.container import ServiceContainer
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
        ConfigManager._instance = None
        try:
            from ui.main_window import DigitalClock

            container = ServiceContainer()
            container.register("config_manager", ConfigManager())
            cls.clock = DigitalClock(container)
        except tk.TclError as e:
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
            ConfigManager._instance = None
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
        for name in ("pomodoro_menu", "hourly_web_menu", "countdown_menu", "timezone_menu"):
            with self.subTest(attribute=name):
                self.assertTrue(hasattr(menu, name))

    def test_timezone_is_first_entry_of_clock_settings(self):
        menu = self.clock.context_menu
        labels = self._labels(menu)
        settings = menu.nametowidget(menu.entrycget(labels.index("時鐘設定"), "menu"))

        self.assertEqual(self._labels(settings)[:2], ["多時區", "---"])
        self.assertIs(settings.nametowidget(settings.entrycget(0, "menu")), menu.timezone_menu)

    def test_productivity_menu_sits_below_hourly_web_and_holds_pomodoro_and_countdown(self):
        menu = self.clock.context_menu
        labels = self._labels(menu)
        self.assertEqual(labels[labels.index("整點啟動") + 1:labels.index("整點啟動") + 3], ["---", "效率提升"])

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

    def test_pomodoro_menu_has_no_status_entry(self):
        self.assertEqual(self._labels(self.clock.context_menu.pomodoro_menu), ["開始專注", "停止"])

    def test_top_level_menu_order_and_reminder_placement(self):
        labels = self._labels(self.clock.context_menu)
        entries = [label for label in labels if label != "---"]

        self.assertEqual(entries, ["休假模式", "提醒", "整點啟動", "效率提升", "時鐘設定", "離開"])
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
