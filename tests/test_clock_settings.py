import unittest
from unittest.mock import MagicMock

from ui.main_window import DigitalClock


class TestClockSettings(unittest.TestCase):
    """時鐘外觀設定行為測試。"""

    def setUp(self) -> None:
        self.ui = DigitalClock.__new__(DigitalClock)
        self.ui.config = {
            'appearance': {
                'font_family': 'Arial',
                'font_size': 56,
                'time_format': '24h',
                'date_format': 'full',
                'corner_radius': 30,
            },
            'window': {
                'alpha_focused': 1.0,
                'alpha_unfocused': 0.5,
            },
        }
        self.ui.DATE_FORMATS = {'full': '%Y年%m月%d日 ', 'short': '%Y-%m-%d'}
        self.ui.logic = MagicMock()
        self.ui.root = MagicMock()
        self.ui.font_size_var = MagicMock()
        self.ui.date_format_var = MagicMock()
        self.ui.alpha_focused_var = MagicMock()
        self.ui.alpha_unfocused_var = MagicMock()
        self.ui.corner_radius_var = MagicMock()

    def test_date_format_is_stored_in_current_config(self) -> None:
        self.ui.change_date_format('short')

        self.assertEqual(self.ui.config['appearance']['date_format'], 'short')
        self.ui.date_format_var.set.assert_called_once_with('short')
        self.ui.logic.schedule_save.assert_called_once_with(self.ui.config)

    def test_focused_alpha_is_applied_and_saved(self) -> None:
        self.ui.change_window_alpha(True, 0.8)

        self.assertEqual(self.ui.config['window']['alpha_focused'], 0.8)
        self.ui.alpha_focused_var.set.assert_called_once_with(0.8)
        self.ui.root.attributes.assert_called_once_with('-alpha', 0.8)
        self.ui.logic.schedule_save.assert_called_once_with(self.ui.config)

    def test_corner_radius_is_redrawn_and_saved(self) -> None:
        self.ui._redraw_background = MagicMock()

        self.ui.change_corner_radius(20)

        self.assertEqual(self.ui.CORNER_RADIUS, 20)
        self.assertEqual(self.ui.config['appearance']['corner_radius'], 20)
        self.ui.corner_radius_var.set.assert_called_once_with(20)
        self.ui._redraw_background.assert_called_once()
        self.ui.logic.schedule_save.assert_called_once_with(self.ui.config)

    def test_consecutive_changes_save_all_current_values(self) -> None:
        self.ui.change_date_format('short')
        self.ui.change_window_alpha(False, 0.7)

        saved_config = self.ui.logic.schedule_save.call_args[0][0]
        self.assertEqual(saved_config['appearance']['date_format'], 'short')
        self.assertEqual(saved_config['window']['alpha_unfocused'], 0.7)


if __name__ == '__main__':
    unittest.main()
