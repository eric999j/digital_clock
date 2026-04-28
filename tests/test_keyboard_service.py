import unittest
from unittest.mock import MagicMock, patch

from pynput.keyboard import Key

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


if __name__ == '__main__':
    unittest.main()
