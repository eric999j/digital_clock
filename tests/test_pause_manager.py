import unittest
from unittest.mock import MagicMock, call

from services.pause_manager import PauseManager
from core.events import Events


class TestPauseManager(unittest.TestCase):
    def setUp(self):
        self.mock_config_mgr = MagicMock()
        self.mock_notify = MagicMock()
        self.manager = PauseManager(self.mock_config_mgr, self.mock_notify)

    def test_get_pause_state_uses_provided_config_without_loading(self):
        config_snapshot = {
            'reminder_paused': True,
            'hourly_web_reminder': {'paused': False},
            'on_vacation': True
        }
        self.mock_config_mgr.load_config.side_effect = AssertionError("should not read config manager")

        self.assertTrue(self.manager.get_pause_state('reminder', config=config_snapshot))
        self.assertFalse(self.manager.get_pause_state('hourly_web', config=config_snapshot))
        self.assertTrue(self.manager.get_pause_state('vacation', config=config_snapshot))
        self.assertFalse(self.manager.get_pause_state('unknown', config=config_snapshot))

    def test_toggle_vacation_start_batches_config_save(self):
        config = {
            'reminder_paused': False,
            'hourly_web_reminder': {'paused': False},
            'on_vacation': False
        }
        self.mock_config_mgr.load_config.return_value = config
        pomodoro_stop = MagicMock()

        self.manager.toggle_vacation(pomodoro_stop)

        pomodoro_stop.assert_called_once()
        self.mock_config_mgr.load_config.assert_called_once()
        self.mock_config_mgr.save_config.assert_called_once_with(config)
        self.assertTrue(config['reminder_paused'])
        self.assertTrue(config['hourly_web_reminder']['paused'])
        self.assertTrue(config['on_vacation'])
        self.assertEqual(
            config['vacation_previous_state'],
            {'reminder_paused': False, 'hourly_web_paused': False}
        )
        self.mock_notify.assert_has_calls([
            call(Events.REMINDER_PAUSE_TOGGLED, True),
            call(Events.HOURLY_WEB_PAUSE_TOGGLED, True),
            call(Events.VACATION_TOGGLED, True),
        ])

    def test_toggle_vacation_end_batches_config_save(self):
        config = {
            'reminder_paused': True,
            'hourly_web_reminder': {'paused': True},
            'on_vacation': True,
            'vacation_previous_state': {
                'reminder_paused': False,
                'hourly_web_paused': False
            }
        }
        self.mock_config_mgr.load_config.return_value = config

        self.manager.toggle_vacation(MagicMock())

        self.mock_config_mgr.load_config.assert_called_once()
        self.mock_config_mgr.save_config.assert_called_once_with(config)
        self.assertFalse(config['reminder_paused'])
        self.assertFalse(config['hourly_web_reminder']['paused'])
        self.assertFalse(config['on_vacation'])
        self.mock_notify.assert_has_calls([
            call(Events.REMINDER_PAUSE_TOGGLED, False),
            call(Events.HOURLY_WEB_PAUSE_TOGGLED, False),
            call(Events.VACATION_TOGGLED, False),
        ])


if __name__ == '__main__':
    unittest.main()
