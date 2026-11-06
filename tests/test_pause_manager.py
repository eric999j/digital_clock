import unittest
from unittest.mock import MagicMock, call

from core.events import Events
from services.pause_manager import PauseManager


class TestPauseManager(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_config_mgr = MagicMock()
        self.mock_notify = MagicMock()
        self.manager = PauseManager(self.mock_config_mgr, self.mock_notify)

    def test_get_pause_state_uses_provided_config_without_loading(self) -> None:
        config_snapshot = {
            'pause_sources': {'reminder': ['manual'], 'hourly_web': []},
            'vacation_sources': ['calendar'],
        }
        self.mock_config_mgr.load_config.side_effect = AssertionError("should not read config manager")

        self.assertTrue(self.manager.get_pause_state('reminder', config=config_snapshot))
        self.assertFalse(self.manager.get_pause_state('hourly_web', config=config_snapshot))
        self.assertTrue(self.manager.get_pause_state('vacation', config=config_snapshot))
        self.assertFalse(self.manager.get_pause_state('unknown', config=config_snapshot))

    def test_vacation_adds_shared_pause_source_and_stops_pomodoro(self) -> None:
        config = {'reminder_paused': False, 'hourly_web_reminder': {'paused': False}, 'on_vacation': False}
        self.mock_config_mgr.load_config.return_value = config
        pomodoro_stop = MagicMock()
        self.manager.set_pomodoro_stop(pomodoro_stop)

        self.manager.set_vacation_source('schedule', True)

        pomodoro_stop.assert_called_once()
        self.assertEqual(config['vacation_sources'], ['schedule'])
        self.assertEqual(config['pause_sources']['reminder'], ['vacation'])
        self.assertEqual(config['pause_sources']['hourly_web'], ['vacation'])
        self.mock_notify.assert_has_calls([
            call(Events.REMINDER_PAUSE_TOGGLED, True),
            call(Events.HOURLY_WEB_PAUSE_TOGGLED, True),
            call(Events.VACATION_TOGGLED, True),
        ])

    def test_manual_pause_survives_vacation_end(self) -> None:
        config = {'reminder_paused': False, 'hourly_web_reminder': {'paused': False}, 'on_vacation': False}
        self.mock_config_mgr.load_config.return_value = config

        self.manager.set_vacation_source('calendar', True)
        self.manager.set_pause_state('reminder', True)
        self.manager.set_vacation_source('calendar', False)

        self.assertTrue(config['reminder_paused'])
        self.assertEqual(config['pause_sources']['reminder'], ['manual'])
        self.assertFalse(config['hourly_web_reminder']['paused'])
        self.assertFalse(config['on_vacation'])

    def test_sources_release_only_their_own_vacation_hold(self) -> None:
        config = {'reminder_paused': False, 'hourly_web_reminder': {'paused': False}, 'on_vacation': False}
        self.mock_config_mgr.load_config.return_value = config

        self.manager.set_vacation_source('calendar', True)
        self.manager.set_vacation_source('schedule', True)
        self.manager.set_vacation_source('calendar', False)

        self.assertTrue(config['on_vacation'])
        self.assertEqual(config['vacation_sources'], ['schedule'])
        self.assertTrue(self.manager.has_vacation_source('schedule', config))
        self.manager.set_vacation_source('schedule', False)
        self.assertFalse(config['on_vacation'])

    def test_legacy_snapshot_is_migrated_without_losing_manual_pause(self) -> None:
        config = {
            'reminder_paused': True,
            'hourly_web_reminder': {'paused': True},
            'on_vacation': True,
            'on_vacation_source': 'manual',
            'vacation_previous_state': {'reminder_paused': True, 'hourly_web_paused': False},
        }
        self.mock_config_mgr.load_config.return_value = config

        self.manager.set_vacation_source('manual', False)

        self.assertEqual(config['pause_sources']['reminder'], ['manual'])
        self.assertEqual(config['pause_sources']['hourly_web'], [])
        self.assertTrue(config['reminder_paused'])
        self.assertFalse(config['hourly_web_reminder']['paused'])
        self.assertNotIn('vacation_previous_state', config)


if __name__ == '__main__':
    unittest.main()
