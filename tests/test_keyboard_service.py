import unittest
from unittest.mock import MagicMock, patch

from pynput.keyboard import Key, KeyCode

from services.config_service import ConfigManager
from services.keyboard_service import KeyboardService


class TestKeyboardService(unittest.TestCase):
    def setUp(self):
        self.mock_config_mgr = MagicMock()
        self.mock_config_mgr.load_config.return_value = {
            'system': {
                'screenshot_keys': ['cmd_l', 'shift', 's'],
                'key_map': {
                    'cmd_l': 'cmd_l',
                    'shift': 'shift',
                }
            }
        }
        self.mock_callback = MagicMock()
        self.service = KeyboardService(self.mock_config_mgr, self.mock_callback)

    def test_load_config_sets_screenshot_keys(self):
        self.assertEqual(self.service.WIN_SCREENSHOT_KEYS, {'cmd_l', 'shift', 's'})

    def test_load_config_builds_key_map(self):
        self.assertIn(Key.cmd_l, self.service.KEY_MAP)
        self.assertIn(Key.shift, self.service.KEY_MAP)

    @patch('services.keyboard_service.keyboard.Listener')
    def test_start_creates_listener(self, mock_listener_cls):
        self.service.start()
        mock_listener_cls.assert_called_once()
        mock_listener_cls.return_value.start.assert_called_once()
        self.assertIsNotNone(self.service.listener)

    @patch('services.keyboard_service.keyboard.Listener')
    def test_start_idempotent(self, mock_listener_cls):
        self.service.start()
        self.service.start()
        mock_listener_cls.assert_called_once()

    @patch('services.keyboard_service.keyboard.Listener')
    def test_stop_stops_listener(self, mock_listener_cls):
        self.service.start()
        self.service.stop()
        mock_listener_cls.return_value.stop.assert_called_once()
        self.assertIsNone(self.service.listener)

    def test_stop_when_not_started(self):
        self.service.stop()
        self.assertIsNone(self.service.listener)

    def test_on_press_adds_mapped_key(self):
        self.service._on_press(Key.shift)
        self.assertIn('shift', self.service.pressed_keys)

    def test_on_press_adds_char_key(self):
        mock_key = MagicMock()
        mock_key.char = 's'
        self.service._on_press(mock_key)
        self.assertIn('s', self.service.pressed_keys)

    def test_on_key_release_removes_key(self):
        self.service.pressed_keys.add('shift')
        self.service._on_key_release(Key.shift)
        self.assertNotIn('shift', self.service.pressed_keys)

    def test_on_key_release_nonexistent_key_no_error(self):
        self.service._on_key_release(Key.shift)

    def test_screenshot_callback_triggered(self):
        self.service.pressed_keys = {'cmd_l', 'shift'}
        mock_key = MagicMock()
        mock_key.char = 's'
        self.service._on_press(mock_key)
        self.mock_callback.assert_called_once()

    def test_screenshot_callback_not_triggered_incomplete_combo(self):
        self.service.pressed_keys = {'cmd_l'}
        mock_key = MagicMock()
        mock_key.char = 's'
        self.service._on_press(mock_key)
        self.mock_callback.assert_not_called()

    def test_on_press_attribute_error_ignored(self):
        mock_key = MagicMock(spec=[])
        del mock_key.char
        self.service._on_press(mock_key)
        self.mock_callback.assert_not_called()


class TestScreenshotShortcutWithDefaultConfig(unittest.TestCase):
    """以預設設定驗證 Win+Shift+S 與 PrtScn，並重現 pynput 在 Shift 按住時回報大寫字元的行為。"""

    def setUp(self):
        defaults = ConfigManager().default_config['system']
        mgr = MagicMock()
        mgr.load_config.return_value = {'system': defaults}
        self.callback = MagicMock()
        self.service = KeyboardService(mgr, self.callback)

    @staticmethod
    def _char(value: str) -> KeyCode:
        return KeyCode.from_char(value)

    def _press_release(self, *keys) -> None:
        for key in keys:
            self.service._on_press(key)
        for key in reversed(keys):
            self.service._on_key_release(key)

    def test_win_shift_s_triggers_even_though_pynput_reports_uppercase(self):
        self._press_release(Key.cmd_l, Key.shift, self._char('S'))
        self.callback.assert_called_once()

    def test_right_hand_modifiers_also_trigger(self):
        self._press_release(Key.cmd_r, Key.shift_r, self._char('S'))
        self.callback.assert_called_once()

    def test_no_stale_keys_remain_after_release(self):
        # Shift 先放開時，'S' 的釋放事件會以小寫回報
        self.service._on_press(Key.cmd_l)
        self.service._on_press(Key.shift)
        self.service._on_press(self._char('S'))
        self.service._on_key_release(Key.shift)
        self.service._on_key_release(self._char('s'))
        self.service._on_key_release(Key.cmd_l)
        self.assertEqual(self.service.pressed_keys, set())

    def test_triggers_again_on_next_shortcut_but_not_while_held(self):
        self.service._on_press(Key.cmd_l)
        self.service._on_press(Key.shift)
        self.service._on_press(self._char('S'))
        self.service._on_press(self._char('S'))  # \u9577\u6309\u81ea\u52d5\u91cd\u8907
        self.assertEqual(self.callback.call_count, 1)
        self._press_release(self._char('S'))
        self.service._on_press(self._char('S'))
        self.assertEqual(self.callback.call_count, 2)

    def test_plain_shift_s_does_not_trigger(self):
        self._press_release(Key.shift, self._char('S'))
        self.callback.assert_not_called()

    def test_print_screen_triggers_once_even_when_held(self):
        self.service._on_press(Key.print_screen)
        self.service._on_press(Key.print_screen)
        self.callback.assert_called_once()
        self.service._on_key_release(Key.print_screen)
        self.service._on_press(Key.print_screen)
        self.assertEqual(self.callback.call_count, 2)


if __name__ == '__main__':
    unittest.main()
