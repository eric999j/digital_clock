import unittest
from datetime import datetime
from unittest.mock import MagicMock

from services.hourly_web_service import HourlyWebService


class TestHourlyWebService(unittest.TestCase):
    def setUp(self):
        self.mock_config_mgr = MagicMock()
        self.mock_notify = MagicMock()
        self.service = HourlyWebService(self.mock_config_mgr, self.mock_notify)
        self.service.strategy = MagicMock()

    def test_check_uses_provided_config_without_loading(self):
        now = datetime(2025, 1, 1, 9, 0, 0)
        config_snapshot = {
            'hourly_web_reminder': {
                'url': 'https://example.com',
                'start_hour': 8,
                'end_hour': 17,
                'paused': False,
                'work_days_only': False
            }
        }
        self.mock_config_mgr.load_config.side_effect = AssertionError("should not read config manager")
        self.service.strategy.check.return_value = False

        self.service.check(now=now, config=config_snapshot)
        self.service.strategy.check.assert_called_once_with(config_snapshot['hourly_web_reminder'], now)

    def test_check_loads_config_without_snapshot(self):
        now = datetime(2025, 1, 1, 9, 0, 0)
        loaded_config = {
            'hourly_web_reminder': {
                'url': 'https://example.com',
                'start_hour': 8,
                'end_hour': 17
            }
        }
        self.mock_config_mgr.load_config.return_value = loaded_config
        self.service.strategy.check.return_value = False

        self.service.check(now=now)
        self.mock_config_mgr.load_config.assert_called_once()
        self.service.strategy.check.assert_called_once_with(loaded_config['hourly_web_reminder'], now)


if __name__ == '__main__':
    unittest.main()
