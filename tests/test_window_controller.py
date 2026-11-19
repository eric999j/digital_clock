"""功能視窗控制器測試。"""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ui.window_controller import WindowController


class TestWindowController(unittest.TestCase):
    def test_open_reminder_uses_compatibility_callback_and_idle_scheduler(self) -> None:
        ui = SimpleNamespace(
            root=MagicMock(),
            logic=SimpleNamespace(add_reminder=MagicMock()),
            config={'ui_behavior': {'reminder_window_geometry': '400x530'}},
            _get_current_theme=MagicMock(return_value={'bg': '#000', 'fg': '#fff'}),
        )
        controller = WindowController(ui)
        reminder = {'message': 'edit'}

        with patch('ui.reminder_window.ReminderWindow') as reminder_window:
            controller.open_reminder(reminder)
            callback = ui.root.after_idle.call_args.args[0]
            callback()

        reminder_window.assert_called_once_with(
            ui.root,
            ui.logic.add_reminder,
            {'bg': '#000', 'fg': '#fff'},
            reminder,
            geometry='400x530',
        )


if __name__ == '__main__':
    unittest.main()
