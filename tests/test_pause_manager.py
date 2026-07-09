import unittest
from unittest.mock import MagicMock, call

from core.events import Events
from services.pause_manager import PauseManager


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
        # 預設來源為 manual
        self.assertEqual(config['on_vacation_source'], 'manual')
        self.assertEqual(
            config['vacation_previous_state'],
            {'reminder_paused': False, 'hourly_web_paused': False}
        )
        self.mock_notify.assert_has_calls([
            call(Events.REMINDER_PAUSE_TOGGLED, True),
            call(Events.HOURLY_WEB_PAUSE_TOGGLED, True),
            call(Events.VACATION_TOGGLED, True),
        ])

    def test_toggle_vacation_start_with_schedule_source(self):
        config = {
            'reminder_paused': False,
            'hourly_web_reminder': {'paused': False},
            'on_vacation': False
        }
        self.mock_config_mgr.load_config.return_value = config

        self.manager.toggle_vacation(MagicMock(), source='schedule')

        self.assertTrue(config['on_vacation'])
        self.assertEqual(config['on_vacation_source'], 'schedule')

    def test_toggle_vacation_end_batches_config_save(self):
        config = {
            'reminder_paused': True,
            'hourly_web_reminder': {'paused': True},
            'on_vacation': True,
            'on_vacation_source': 'manual',
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
        # 離開休假時清除來源標記
        self.assertNotIn('on_vacation_source', config)
        self.mock_notify.assert_has_calls([
            call(Events.REMINDER_PAUSE_TOGGLED, False),
            call(Events.HOURLY_WEB_PAUSE_TOGGLED, False),
            call(Events.VACATION_TOGGLED, False),
        ])

    def test_get_vacation_source_returns_none_when_not_on_vacation(self):
        snapshot = {'on_vacation': False, 'on_vacation_source': 'schedule'}
        self.assertIsNone(self.manager.get_vacation_source(config=snapshot))

    def test_get_vacation_source_returns_source_when_on_vacation(self):
        snapshot = {'on_vacation': True, 'on_vacation_source': 'schedule'}
        self.assertEqual(self.manager.get_vacation_source(config=snapshot), 'schedule')


if __name__ == '__main__':
    unittest.main()
