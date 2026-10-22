import tkinter as tk
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from core.clock_logic import ClockLogic
from services.countdown_service import CountdownService
from services.timezone_service import ZoneTime
from ui import popup_utils
from ui.main_window import DigitalClock


class TestSnoozeLabel(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(popup_utils._format_snooze_label(5), "5 分鐘後")
        self.assertEqual(popup_utils._format_snooze_label(30), "30 分鐘後")
        self.assertEqual(popup_utils._format_snooze_label(60), "1 小時後")
        self.assertEqual(popup_utils._format_snooze_label(120), "2 小時後")
        self.assertEqual(popup_utils._format_snooze_label(90), "90 分鐘後")


class TestReminderPopupSnooze(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except tk.TclError as e:
            raise unittest.SkipTest(f"No display available: {e}") from e

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    @staticmethod
    def _find(widget, widget_class):
        for child in widget.winfo_children():
            if child.winfo_class() == widget_class:
                return child
            found = TestReminderPopupSnooze._find(child, widget_class)
            if found is not None:
                return found
        return None

    def test_popup_without_snooze_has_no_snooze_button(self):
        popup = popup_utils.show_reminder_popup_window(self.root, "hello")
        self.addCleanup(popup.destroy)
        self.assertIsNone(self._find(popup, "Menubutton"))

    def test_snooze_requires_both_options_and_callback(self):
        popup = popup_utils.show_reminder_popup_window(self.root, "hello", snooze_minutes=(5, 10))
        self.addCleanup(popup.destroy)
        self.assertIsNone(self._find(popup, "Menubutton"))

    def test_snooze_menu_lists_options_and_invokes_callback(self):
        callback = MagicMock()
        popup = popup_utils.show_reminder_popup_window(
            self.root, "hello", snooze_minutes=(5, 10, 60), on_snooze=callback,
        )
        self.addCleanup(lambda: popup.winfo_exists() and popup.destroy())

        button = self._find(popup, "Menubutton")
        self.assertIsNotNone(button)
        menu = popup.nametowidget(button.cget("menu"))
        labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)]
        self.assertEqual(labels, ["5 分鐘後", "10 分鐘後", "1 小時後"])

        menu.invoke(1)

        callback.assert_called_once_with(10)
        self.assertFalse(popup.winfo_exists())

    def test_popup_closes_even_if_snooze_callback_fails(self):
        callback = MagicMock(side_effect=RuntimeError("boom"))
        popup = popup_utils.show_reminder_popup_window(
            self.root, "hello", snooze_minutes=(5,), on_snooze=callback,
        )
        menu = popup.nametowidget(self._find(popup, "Menubutton").cget("menu"))

        menu.invoke(0)

        callback.assert_called_once_with(5)
        self.assertFalse(popup.winfo_exists())


class TestMainWindowHandlers(unittest.TestCase):
    def _make_ui(self):
        ui = DigitalClock.__new__(DigitalClock)
        ui.config = {
            'appearance': {'theme': 'caramel', 'time_format': '24h'},
            'window': {'width': 200, 'height': 70, 'x': 10, 'y': 10},
            'reminders': [],
            'timezones': {'selected': []},
        }
        ui.TIME_FORMATS = {'24h': '%H:%M', '12h': '%I:%M %p'}
        ui.logic = MagicMock()
        ui.root = MagicMock()
        ui._info_lines = []
        return ui

    def test_reminder_snoozed_syncs_only_reminders(self):
        ui = self._make_ui()
        ui.logic.get_config.return_value = {
            'appearance': {'theme': 'earth'},
            'reminders': [{'title': 'snoozed'}],
        }
        ui._update_reminder_menu = MagicMock()

        ui._on_reminder_snoozed({'title': 'snoozed'}, 10)

        self.assertEqual(ui.config['reminders'], [{'title': 'snoozed'}])
        self.assertEqual(ui.config['appearance']['theme'], 'caramel')
        ui._update_reminder_menu.assert_called_once()

    def test_timezones_updated_syncs_only_timezones_and_refreshes(self):
        ui = self._make_ui()
        ui.logic.get_config.return_value = {
            'appearance': {'theme': 'earth'},
            'timezones': {'selected': ['UTC']},
        }
        ui._refresh_info_lines = MagicMock()

        ui._on_timezones_updated(['UTC'])

        self.assertEqual(ui.config['timezones'], {'selected': ['UTC']})
        self.assertEqual(ui.config['appearance']['theme'], 'caramel')
        ui._refresh_info_lines.assert_called_once()

    def test_compose_info_lines_with_countdown_and_zones(self):
        ui = self._make_ui()
        countdown = CountdownService(MagicMock(), clock=lambda: 0.0)
        countdown.start(125, "泡麵")
        ui.logic.countdown_service = countdown
        tokyo = ZoneTime("Asia/Tokyo", "東京", datetime(2026, 1, 2, 0, 5, tzinfo=ZoneInfo("Asia/Tokyo")), 1)
        london = ZoneTime("Europe/London", "倫敦", datetime(2026, 1, 1, 15, 5, tzinfo=ZoneInfo("Europe/London")), 0)
        ui.logic.get_zone_times.return_value = [tokyo, london]

        self.assertEqual(
            ui._compose_info_lines(),
            ["泡麵 倒數 02:05", "東京 00:05 (+1)", "倫敦 15:05"],
        )

    def test_compose_info_lines_paused_and_12h(self):
        ui = self._make_ui()
        ui.config['appearance']['time_format'] = '12h'
        countdown = CountdownService(MagicMock(), clock=lambda: 0.0)
        countdown.start(60)
        countdown.pause()
        ui.logic.countdown_service = countdown
        ny = ZoneTime("America/New_York", "紐約", datetime(2026, 1, 1, 13, 5, tzinfo=ZoneInfo("America/New_York")), -1)
        ui.logic.get_zone_times.return_value = [ny]

        self.assertEqual(ui._compose_info_lines(), ["倒數 01:00 (暫停)", "紐約 01:05 下午 (-1)"])

    def test_compose_info_lines_empty_when_nothing_to_show(self):
        ui = self._make_ui()
        ui.logic.countdown_service = CountdownService(MagicMock())
        ui.logic.get_zone_times.return_value = []
        self.assertEqual(ui._compose_info_lines(), [])

    def test_set_info_lines_is_noop_when_unchanged(self):
        ui = self._make_ui()
        ui._info_lines = ["a"]
        ui._apply_window_size = MagicMock()
        ui._render_info_band = MagicMock()

        ui._set_info_lines(["a"])

        ui._apply_window_size.assert_not_called()
        ui._render_info_band.assert_not_called()

    def test_set_info_lines_resizes_only_when_band_height_changes(self):
        ui = self._make_ui()
        ui._info_line_px = 16
        ui._base_height = 70
        ui._last_render_state = {}
        ui._apply_window_size = MagicMock()
        ui._redraw_background = MagicMock()
        ui._update_display_time = MagicMock()
        ui._render_info_band = MagicMock()

        ui._set_info_lines(["a"])
        ui._apply_window_size.assert_called_once_with(200, 70 + 16 + ui.INFO_BAND_PADDING)

        ui._apply_window_size.reset_mock()
        ui._set_info_lines(["b"])  # 行數相同：只更新文字
        ui._apply_window_size.assert_not_called()
        self.assertEqual(ui._render_info_band.call_count, 2)

        ui._set_info_lines([])  # 隱藏資訊列：還原高度
        ui._apply_window_size.assert_called_once_with(200, 70)

    def test_countdown_finished_rings_bell_and_shows_popup(self):
        ui = self._make_ui()
        ui._refresh_info_lines = MagicMock()
        ui._get_current_theme = MagicMock(return_value=None)

        # 函式內才 import，因此需在呼叫前先替換
        with patch("ui.popup_utils.show_reminder_popup_window") as show:
            ui._on_countdown_finished("泡麵", 300)
            (scheduled,), _ = ui.root.after_idle.call_args
            scheduled()

        ui._refresh_info_lines.assert_called_once()
        ui.root.bell.assert_called_once()
        args, kwargs = show.call_args
        self.assertIn("「泡麵」倒數 05:00 結束了", args)
        self.assertEqual(kwargs["title"], "倒數計時")

    def test_drag_is_clamped_to_screen(self):
        ui = self._make_ui()
        ui.drag_offset = {'x': 0, 'y': 0}
        ui.root.winfo_x.return_value = 100
        ui.root.winfo_y.return_value = 100
        ui.root.winfo_width.return_value = 200
        ui.root.winfo_height.return_value = 70

        with patch("ui.main_window.get_screen_bounds", return_value=(0, 0, 1920, 1080)):
            ui._drag(SimpleNamespace(x=-9999, y=-9999))
            ui.root.geometry.assert_called_with('+0+0')
            self.assertEqual((ui.config['window']['x'], ui.config['window']['y']), (0, 0))

            ui._drag(SimpleNamespace(x=99999, y=99999))
            ui.root.geometry.assert_called_with('+1720+1010')
            ui.logic.schedule_window_position_save.assert_called_with(1720, 1010)

    def test_apply_window_size_moves_window_back_into_view_and_saves(self):
        ui = self._make_ui()
        ui.root.winfo_x.return_value = 1800
        ui.root.winfo_y.return_value = 1040

        with patch("ui.main_window.get_screen_bounds", return_value=(0, 0, 1920, 1080)):
            ui._apply_window_size(237, 185)

        ui.root.geometry.assert_called_once_with('237x185+1683+895')
        ui.logic.schedule_window_position_save.assert_called_once_with(1683, 895)
        self.assertEqual((ui.config['window']['x'], ui.config['window']['y']), (1683, 895))

    def test_apply_window_size_keeps_position_when_already_visible(self):
        ui = self._make_ui()
        ui.root.winfo_x.return_value = 100
        ui.root.winfo_y.return_value = 100

        with patch("ui.main_window.get_screen_bounds", return_value=(0, 0, 1920, 1080)):
            ui._apply_window_size(237, 185)

        ui.root.geometry.assert_called_once_with('237x185+100+100')
        ui.logic.schedule_window_position_save.assert_not_called()


class TestClockLogicScheduler(unittest.TestCase):
    def _logic(self, ui):
        logic = ClockLogic.__new__(ClockLogic)
        logic.ui = ui
        logic._save_delay_ms = 500
        logic._save_after_id = None
        logic._pending_config = None
        logic._pending_window_position = None
        return logic

    def test_uses_root_when_ui_controller_is_not_a_tk_widget(self):
        """DigitalClock 本身沒有 after()，排程必須落在其 root 上。"""
        ui = SimpleNamespace(root=MagicMock())
        ui.root.after.return_value = "after-1"
        logic = self._logic(ui)

        logic.schedule_window_position_save(5, 6)
        logic.schedule_window_position_save(7, 8)

        self.assertEqual(ui.root.after.call_count, 2)
        ui.root.after_cancel.assert_called_once_with("after-1")

    def test_prefers_ui_after_when_available(self):
        ui = MagicMock()
        logic = self._logic(ui)
        logic.schedule_window_position_save(1, 2)
        ui.after.assert_called_once()

    def test_flush_cancels_through_root(self):
        ui = SimpleNamespace(root=MagicMock())
        ui.root.after.return_value = "after-1"
        logic = self._logic(ui)
        logic.config_manager = MagicMock()
        logic.get_config = MagicMock(return_value={})
        logic.schedule_window_position_save(5, 6)

        logic.flush_pending_save()

        ui.root.after_cancel.assert_called_once_with("after-1")
        logic.config_manager.save_config.assert_called_once()


if __name__ == "__main__":
    unittest.main()
