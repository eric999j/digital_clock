import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from ui.hourly_web_window import HourlyWebWindow
from ui.main_window import DigitalClock


class TestHourlyWebUpdatedThemeSync(unittest.TestCase):
    def test_on_hourly_web_updated_preserves_in_memory_theme(self):
        ui = DigitalClock.__new__(DigitalClock)
        ui.config = {
            'appearance': {'theme': 'caramel'},
            'hourly_web_reminder': {'url_rules': []},
            'reminders': [],
            'vacation_schedules': [],
        }
        ui.logic = MagicMock()
        ui.logic.get_config.return_value = {
            'appearance': {'theme': 'earth'},
            'hourly_web_reminder': {'url_rules': [{'url': 'https://example.com', 'start_hour': 9, 'end_hour': 10}]},
            'reminders': [{'title': 't'}],
            'vacation_schedules': [{'start': '2026-09-02', 'end': '2026-09-02'}],
        }
        ui._show_themed_info = MagicMock()

        ui._on_hourly_web_updated()

        self.assertEqual(ui.config['appearance']['theme'], 'caramel')
        self.assertEqual(len(ui.config['hourly_web_reminder']['url_rules']), 1)
        self.assertEqual(len(ui.config['reminders']), 1)
        self.assertEqual(len(ui.config['vacation_schedules']), 1)
        ui._show_themed_info.assert_called_once_with('整點網頁提醒設定已更新！')


class TestHourlyWebWindowRuleContextMenu(unittest.TestCase):
    def test_right_click_on_rule_selects_and_opens_context_menu(self):
        window = HourlyWebWindow.__new__(HourlyWebWindow)
        window._rules_listbox = MagicMock()
        window._rules_menu = MagicMock()
        window._rules_listbox.size.return_value = 2
        window._rules_listbox.nearest.return_value = 1
        window._rules_listbox.bbox.return_value = (0, 20, 100, 16)

        event = SimpleNamespace(y=25, x_root=100, y_root=200)
        window._show_rules_context_menu(event)

        window._rules_listbox.selection_clear.assert_called_once()
        window._rules_listbox.selection_set.assert_called_once_with(1)
        window._rules_listbox.activate.assert_called_once_with(1)
        window._rules_menu.tk_popup.assert_called_once_with(100, 200)
        window._rules_menu.grab_release.assert_called_once()

    def test_right_click_outside_rule_does_not_open_context_menu(self):
        window = HourlyWebWindow.__new__(HourlyWebWindow)
        window._rules_listbox = MagicMock()
        window._rules_menu = MagicMock()
        window._rules_listbox.size.return_value = 1
        window._rules_listbox.nearest.return_value = 0
        window._rules_listbox.bbox.return_value = (0, 20, 100, 16)

        event = SimpleNamespace(y=60, x_root=100, y_root=200)
        window._show_rules_context_menu(event)

        window._rules_listbox.selection_set.assert_not_called()
        window._rules_menu.tk_popup.assert_not_called()


if __name__ == '__main__':
    unittest.main()
