"""ConfigManager 唯讀快取路徑測試。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.config_service import ConfigManager


class TestConfigSnapshot(unittest.TestCase):
    def setUp(self):
        ConfigManager._instance = None
        self.tmpdir = tempfile.mkdtemp()
        self.home_patch = patch('services.config_service.Path.home', return_value=Path(self.tmpdir))
        self.home_patch.start()
        self.cm = ConfigManager()

    def tearDown(self):
        self.home_patch.stop()
        ConfigManager._instance = None

    def test_read_only_returns_cache_reference(self):
        """read_only=True 應回傳相同物件參考（無 deepcopy）。"""
        snap1 = self.cm.load_config(read_only=True)
        snap2 = self.cm.load_config(read_only=True)
        self.assertIs(snap1, snap2)

    def test_default_load_returns_independent_copy(self):
        """預設 read_only=False 應回傳不同的深拷貝。"""
        copy1 = self.cm.load_config()
        copy2 = self.cm.load_config()
        self.assertIsNot(copy1, copy2)
        # 修改 copy1 不會影響 copy2
        copy1['appearance']['font_size'] = 999
        self.assertNotEqual(copy2['appearance']['font_size'], 999)

    def test_save_invalidates_cache_with_new_content(self):
        """儲存後 read_only 應反映新內容。"""
        self.cm.save_config({**self.cm.load_config(), 'window': {'width': 555}})
        snap = self.cm.load_config(read_only=True)
        self.assertEqual(snap['window']['width'], 555)


if __name__ == '__main__':
    unittest.main()
