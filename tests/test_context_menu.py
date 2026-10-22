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
        ConfigManager._instance = None
        try:
            from ui.main_window import DigitalClock

            container = ServiceContainer()
            container.register("config_manager", ConfigManager())
            cls.clock = DigitalClock(container)
        except tk.TclError as e:
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

    def test_top_level_menu_order_and_reminder_placement(self):
        labels = self._labels(self.clock.context_menu)
        entries = [label for label in labels if label != "---"]

        self.assertEqual(entries, ["休假模式", "提醒", "整點網頁", "倒數計時", "番茄鐘", "時鐘設定", "離開"])
        # 不應出現連續或頭尾的分隔線
        self.assertNotEqual(labels[0], "---")
        self.assertNotEqual(labels[-1], "---")
        self.assertFalse(any(a == b == "---" for a, b in zip(labels, labels[1:], strict=False)))


if __name__ == "__main__":
    unittest.main()
