import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.config_service import ConfigManager


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory needed for the tests
        self.test_dir = tempfile.mkdtemp()
        self.patcher = patch('pathlib.Path.home', return_value=Path(self.test_dir))
        self.mock_home = self.patcher.start()

        # Reset Singleton
        ConfigManager._instance = None

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.test_dir)
        ConfigManager._instance = None

    def test_singleton(self):
        conf1 = ConfigManager()
        conf2 = ConfigManager()
        self.assertIs(conf1, conf2)

    def test_default_values(self):
        conf_mgr = ConfigManager()
        config = conf_mgr.load_config()

        self.assertIn('window', config)
        self.assertIn('appearance', config)
        self.assertIn('ui_behavior', config)
        self.assertIn('animation', config['ui_behavior'])
        self.assertIn('relaxed_idle_refresh_ms', config['ui_behavior']['animation'])
        self.assertIn('relax_after_ms', config['ui_behavior']['animation'])
        self.assertIn('system', config)
        self.assertIn('performance_monitor', config['system'])
        self.assertFalse(config['system']['performance_monitor']['enabled'])
        self.assertEqual(config['version'], "1.0")

    def test_load_save_config(self):
        conf_mgr = ConfigManager()
        config = conf_mgr.load_config()
        # Modify config
        config['window']['width'] = 999
        conf_mgr.save_config(config)

        # Reset instance to force reload
        ConfigManager._instance = None
        new_mgr = ConfigManager()
        new_config = new_mgr.load_config()

        self.assertEqual(new_config['window']['width'], 999)

    def test_merge_deep_structure(self):
        # Create a partial config file
        conf_mgr = ConfigManager()
        config = conf_mgr.load_config()
        conf_mgr.save_config(config) # Create default

        # Manually corrupt/change the file to miss some keys
        with open(conf_mgr.config_file, 'w', encoding='utf-8') as f:
            json.dump({"new_key": "new_value", "window": {"x": 100}}, f)

        # Reset and reload
        ConfigManager._instance = None
        new_mgr = ConfigManager()
        new_config = new_mgr.load_config()

        # 'x' should be 100
        self.assertEqual(new_config['window']['x'], 100)
        # 'width' should be restored from default (200) because it was missing
        self.assertEqual(new_config['window']['width'], 200)
        # 'new_key' should be preserved
        self.assertEqual(new_config['new_key'], "new_value")

    def test_load_returns_independent_copy_for_defaults(self):
        conf_mgr = ConfigManager()
        config = conf_mgr.load_config()
        config['window']['width'] = 777

        reloaded = conf_mgr.load_config()
        self.assertEqual(reloaded['window']['width'], 200)

    def test_load_uses_cache_when_file_unchanged(self):
        conf_mgr = ConfigManager()
        conf_mgr.save_config(conf_mgr.load_config())

        with patch('builtins.open', side_effect=AssertionError("cache miss")):
            cached = conf_mgr.load_config()

        self.assertEqual(cached['version'], "1.0")

    def test_load_reloads_after_external_file_change(self):
        conf_mgr = ConfigManager()
        config = conf_mgr.load_config()
        conf_mgr.save_config(config)

        with open(conf_mgr.config_file, encoding='utf-8') as f:
            raw = json.load(f)
        raw['window']['width'] = 321
        with open(conf_mgr.config_file, 'w', encoding='utf-8') as f:
            json.dump(raw, f, ensure_ascii=False, indent=4)

        prev_mtime = conf_mgr.config_file.stat().st_mtime
        future_mtime = prev_mtime + 5
        os.utime(conf_mgr.config_file, (future_mtime, future_mtime))
        reloaded = conf_mgr.load_config()
        self.assertEqual(reloaded['window']['width'], 321)

if __name__ == '__main__':
    unittest.main()
