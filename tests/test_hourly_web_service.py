import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from core.program_launcher import LaunchError
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
        self.service.strategy.check.return_value = [{'url': u} for u in urls]

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
            {'url': 'javascript:alert(1)'},  # 不安全
            {'url': 'https://safe.example'},
        ]

        with patch('services.hourly_web_service.webbrowser.open') as mock_open, \
                patch.object(self.service, '_bring_browser_to_front') as mock_bring:
            self.service.check(now=now, config={'hourly_web_reminder': {}})

        mock_open.assert_called_once_with('https://safe.example', new=2)
        mock_bring.assert_called_once()

    def test_check_all_unsafe_urls_does_not_call_bring_front(self):
        """全部 URL 都不安全時，不應呼叫 _bring_browser_to_front。"""
        now = datetime(2025, 1, 1, 9, 0, 0)
        self.service.strategy.check.return_value = [{'url': 'javascript:alert(1)'}]

        with patch('services.hourly_web_service.webbrowser.open') as mock_open, \
                patch.object(self.service, '_bring_browser_to_front') as mock_bring:
            self.service.check(now=now, config={'hourly_web_reminder': {}})

        mock_open.assert_not_called()
        mock_bring.assert_not_called()

    def test_check_launches_program_rule(self):
        now = datetime(2025, 1, 6, 9, 0, 0)
        self.service.strategy.check.return_value = [{
            'type': 'program', 'command': 'python.exe', 'arguments': 'a.py', 'working_dir': 'C:\\w',
        }]

        with patch('services.hourly_web_service.launch_program') as mock_launch, \
                patch('services.hourly_web_service.webbrowser.open') as mock_open, \
                patch.object(self.service, '_bring_browser_to_front') as mock_bring:
            self.service.check(now=now, config={'hourly_web_reminder': {}})

        mock_launch.assert_called_once_with('python.exe', 'a.py', 'C:\\w')
        mock_open.assert_not_called()
        mock_bring.assert_not_called()

    def test_program_failure_does_not_block_other_rules(self):
        now = datetime(2025, 1, 6, 9, 0, 0)
        self.service.strategy.check.return_value = [
            {'type': 'program', 'command': 'missing.exe'},
            {'url': 'https://safe.example'},
        ]

        with patch('services.hourly_web_service.launch_program', side_effect=LaunchError('x')), \
                patch('services.hourly_web_service.webbrowser.open') as mock_open, \
                patch.object(self.service, '_bring_browser_to_front'):
            self.service.check(now=now, config={'hourly_web_reminder': {}})

        mock_open.assert_called_once_with('https://safe.example', new=2)

    def test_unsafe_program_rule_is_never_launched_but_others_still_run(self):
        now = datetime(2025, 1, 6, 9, 0, 0)
        self.service.strategy.check.return_value = [
            {'type': 'program', 'command': 'shutdown.exe', 'arguments': '/s /t 0'},
            {'url': 'https://safe.example'},
        ]

        with patch('services.hourly_web_service.launch_program') as mock_launch, \
                patch('services.hourly_web_service.webbrowser.open') as mock_open, \
                patch.object(self.service, '_bring_browser_to_front'):
            self.service.check(now=now, config={'hourly_web_reminder': {}})

        mock_launch.assert_not_called()
        mock_open.assert_called_once_with('https://safe.example', new=2)

    def test_update_config_saves_mixed_rules_and_syncs_legacy_fields_from_first_url(self):
        config = {}
        self.mock_config_mgr.load_config.return_value = config
        rules = [
            {'type': 'program', 'command': 'p.exe', 'start_hour': 9, 'end_hour': 9},
            {'url': 'https://a.example', 'start_hour': 8, 'end_hour': 12},
        ]

        self.service.update_config(rules)

        hw = config['hourly_web_reminder']
        self.assertEqual(hw['url_rules'], rules)
        self.assertEqual((hw['url'], hw['start_hour'], hw['end_hour']), ('https://a.example', 8, 12))
        self.mock_config_mgr.save_config.assert_called_once_with(config)

    def test_update_config_without_url_rules_clears_legacy_url(self):
        config = {'hourly_web_reminder': {'url': 'https://old.example'}}
        self.mock_config_mgr.load_config.return_value = config

        self.service.update_config([])

        self.assertEqual(config['hourly_web_reminder']['url'], '')

    def test_update_config_saves_skip_safety_and_ignores_startup_rules_for_legacy_fields(self):
        config = {'hourly_web_reminder': {}}
        self.mock_config_mgr.load_config.return_value = config
        rules = [{'url': 'https://s.example', 'trigger': 'startup'},
                 {'url': 'https://a.example', 'start_hour': 8, 'end_hour': 12}]

        self.service.update_config(rules, True)

        hw = config['hourly_web_reminder']
        self.assertTrue(hw['skip_safety_check'])
        self.assertEqual(hw['url'], 'https://a.example')
        self.service.update_config(rules)  # None 表示維持原設定
        self.assertTrue(hw['skip_safety_check'])

    def test_run_startup_rules_launches_only_enabled_startup_rules(self):
        rules = [
            {'type': 'program', 'command': 'a.exe', 'trigger': 'startup'},
            {'type': 'program', 'command': 'b.exe', 'trigger': 'startup', 'enabled': False},
            {'type': 'program', 'command': 'c.exe', 'start_hour': 0, 'end_hour': 23},
            {'url': 'https://s.example', 'trigger': 'startup'},
        ]
        with patch.object(self.service, '_launch_rule_program') as launch, \
                patch.object(self.service, '_open_url') as open_url:
            self.service.run_startup_rules({'hourly_web_reminder': {'url_rules': rules}})

        launch.assert_called_once_with(rules[0], False)
        open_url.assert_called_once_with('https://s.example')

    def test_run_startup_rules_respects_pause(self):
        rules = [{'type': 'program', 'command': 'a.exe', 'trigger': 'startup'}]
        with patch.object(self.service, '_launch_rule_program') as launch:
            self.service.run_startup_rules({'hourly_web_reminder': {'url_rules': rules, 'paused': True}})
        launch.assert_not_called()

    def test_launch_program_blocked_unless_safety_skipped(self):
        rule = {'type': 'program', 'command': 'shutdown', 'arguments': '/r /f /t 0'}
        with patch('services.hourly_web_service.launch_program') as launch:
            self.service._launch_rule_program(rule)
            launch.assert_not_called()
            self.service._launch_rule_program(rule, skip_safety=True)
            launch.assert_called_once_with('shutdown', '/r /f /t 0', '')

    def test_check_passes_skip_safety_setting_to_launch(self):
        rule = {'type': 'program', 'command': 'shutdown'}
        self.service.strategy.check.return_value = [rule]
        with patch.object(self.service, '_launch_rule_program') as launch:
            self.service.check(now=datetime(2025, 1, 1, 9), config={'hourly_web_reminder': {'skip_safety_check': True}})
        launch.assert_called_once_with(rule, True)


if __name__ == '__main__':
    unittest.main()
