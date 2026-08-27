import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

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
        self.service.strategy.check.return_value = []

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
        self.service.strategy.check.return_value = []

        self.service.check(now=now)
        self.mock_config_mgr.load_config.assert_called_once()
        self.service.strategy.check.assert_called_once_with(loaded_config['hourly_web_reminder'], now)

    def test_check_opens_all_matched_urls(self):
        """當 strategy 命中多個 URL 時，全部都要開啟。"""
        now = datetime(2025, 1, 1, 9, 0, 0)
        urls = ['https://a.example', 'https://b.example', 'https://c.example']
        self.service.strategy.check.return_value = urls

        with patch('services.hourly_web_service.webbrowser.open') as mock_open, \
                patch.object(self.service, '_bring_browser_to_front') as mock_bring:
            self.service.check(now=now, config={'hourly_web_reminder': {}})

        self.assertEqual(mock_open.call_count, 3)
        for url in urls:
            mock_open.assert_any_call(url, new=2)
        mock_bring.assert_called_once()

    def test_check_skips_unsafe_urls_and_opens_the_rest(self):
        """不安全 URL 應被跳過但不影響其餘 URL 開啟。"""
        now = datetime(2025, 1, 1, 9, 0, 0)
        self.service.strategy.check.return_value = [
            'javascript:alert(1)',  # 不安全
            'https://safe.example',
        ]

        with patch('services.hourly_web_service.webbrowser.open') as mock_open, \
                patch.object(self.service, '_bring_browser_to_front') as mock_bring:
            self.service.check(now=now, config={'hourly_web_reminder': {}})

        mock_open.assert_called_once_with('https://safe.example', new=2)
        mock_bring.assert_called_once()

    def test_check_all_unsafe_urls_does_not_call_bring_front(self):
        """全部 URL 都不安全時，不應呼叫 _bring_browser_to_front。"""
        now = datetime(2025, 1, 1, 9, 0, 0)
        self.service.strategy.check.return_value = ['javascript:alert(1)']

        with patch('services.hourly_web_service.webbrowser.open') as mock_open, \
                patch.object(self.service, '_bring_browser_to_front') as mock_bring:
            self.service.check(now=now, config={'hourly_web_reminder': {}})

        mock_open.assert_not_called()
        mock_bring.assert_not_called()


if __name__ == '__main__':
    unittest.main()
