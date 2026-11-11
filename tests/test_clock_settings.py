import unittest
from unittest.mock import MagicMock, patch

from ui.main_window import DigitalClock
from ui.theme_utils import contrast_ratio, random_theme
from services.config_service import ConfigManager


class TestRandomTheme(unittest.TestCase):
    def test_deleted_builtin_themes_stay_deleted_after_config_merge(self) -> None:
        manager = ConfigManager()
        merged = manager._merge_config({'deleted_themes': ['green'], 'themes': {'custom_test': {
            'name': '收藏', 'bg': '#000000', 'fg': '#FFFFFF',
        }}})
        self.assertNotIn('green', merged['themes'])
        self.assertIn('blue', merged['themes'])
        self.assertIn('custom_test', merged['themes'])

    def test_generated_themes_have_sufficient_contrast(self) -> None:
        templates = [
            {'bg': '#1E3A5F', 'fg': '#A8D8FF'},
            {'bg': '#C7EDCC', 'fg': '#2F4F2F'},
        ]
        colors = set()
        for _ in range(200):
            theme = random_theme(templates)
            self.assertGreaterEqual(contrast_ratio(theme['bg'], theme['fg']), 4.5)
            colors.add((theme['bg'], theme['fg']))
        self.assertGreater(len(colors), 1)

    def test_falls_back_when_templates_are_not_readable(self) -> None:
        theme = random_theme([{'bg': '#FFFFFF', 'fg': '#FFFFFF'}])
        self.assertGreaterEqual(contrast_ratio(theme['bg'], theme['fg']), 4.5)


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

    def test_random_theme_is_applied_and_stored(self) -> None:
        self.ui.config['themes'] = {}
        self.ui.logic.config_manager.default_config = {'themes': {'blue': {'bg': '#1E3A5F', 'fg': '#A8D8FF'}}}
        self.ui.apply_theme = MagicMock()
        self.ui.apply_random_theme()
        theme = self.ui.config['themes']['__random__']
        self.assertGreaterEqual(contrast_ratio(theme['bg'], theme['fg']), 4.5)
        self.ui.apply_theme.assert_called_once_with('__random__')

    def test_save_theme_copies_colors_and_rejects_duplicate_names(self) -> None:
        self.ui.config['themes'] = {'blue': {'name': '紳士藍', 'bg': '#1E3A5F', 'fg': '#A8D8FF'}}
        self.ui.context_menu = MagicMock()
        self.ui.apply_theme = MagicMock()
        source = {'name': '隨機配色', 'bg': '#123456', 'fg': '#FFFFFF'}
        self.ui._save_named_theme(' 我的配色 ', source)
        key = self.ui.apply_theme.call_args.args[0]
        self.assertEqual(self.ui.config['themes'][key], {'name': '我的配色', 'bg': '#123456', 'fg': '#FFFFFF'})
        source['bg'] = '#000000'
        self.assertEqual(self.ui.config['themes'][key]['bg'], '#123456')
        self.ui.context_menu.refresh_theme_menu.assert_called_once()
        for name in ('', '紳士藍', '我的配色', '隨機配色', 'x' * 41):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.ui._save_named_theme(name, source)

    def test_delete_builtin_theme_records_deletion_and_changes_current_theme(self) -> None:
        self.ui.config['themes'] = {'blue': {'name': '藍'}, 'green': {'name': '綠'}}
        self.ui.config['appearance']['theme'] = 'blue'
        self.ui.logic.config_manager.default_config = {'themes': {'blue': {}, 'green': {}}}
        self.ui.context_menu = MagicMock()
        self.ui.apply_theme = MagicMock()
        self.ui._delete_theme('blue')
        self.assertNotIn('blue', self.ui.config['themes'])
        self.assertEqual(self.ui.config['deleted_themes'], ['blue'])
        self.ui.apply_theme.assert_called_once_with('green')

    def test_delete_other_theme_saves_without_switching(self) -> None:
        self.ui.config['themes'] = {'blue': {'name': '藍'}, 'custom_x': {'name': '收藏'}}
        self.ui.config['appearance']['theme'] = 'blue'
        self.ui.logic.config_manager.default_config = {'themes': {'blue': {}}}
        self.ui.context_menu = MagicMock()
        self.ui.apply_theme = MagicMock()
        self.ui._delete_theme('custom_x')
        self.assertNotIn('custom_x', self.ui.config['themes'])
        self.ui.apply_theme.assert_not_called()
        self.ui.logic.schedule_save.assert_called_once_with(self.ui.config)

    def test_delete_last_theme_generates_fallback(self) -> None:
        self.ui.config['themes'] = {'blue': {'name': '藍'}}
        self.ui.config['appearance']['theme'] = 'blue'
        self.ui.logic.config_manager.default_config = {'themes': {'blue': {}}}
        self.ui.context_menu = MagicMock()
        self.ui.apply_random_theme = MagicMock()
        self.ui._delete_theme('blue')
        self.ui.apply_random_theme.assert_called_once()

    def test_confirm_delete_only_removes_after_confirmation(self) -> None:
        self.ui.config['themes'] = {'custom_x': {'name': '收藏', 'bg': '#000000', 'fg': '#FFFFFF'}}
        self.ui.config['appearance']['theme'] = 'custom_x'
        self.ui._delete_theme = MagicMock()
        with patch('ui.main_window.themed_confirm') as confirm:
            self.ui.confirm_delete_theme('custom_x')
        self.ui._delete_theme.assert_not_called()
        confirm.call_args.args[2]()
        self.ui._delete_theme.assert_called_once_with('custom_x')


if __name__ == '__main__':
    unittest.main()
