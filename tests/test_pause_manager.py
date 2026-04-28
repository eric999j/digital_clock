import unittest
from unittest.mock import MagicMock

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


if __name__ == '__main__':
    unittest.main()
