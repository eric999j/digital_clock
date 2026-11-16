import logging
import tempfile
import unittest
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from unittest.mock import patch

from services.config_service import ConfigManager
from services.log_service import LogService


class TestLogService(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home_patcher = patch('pathlib.Path.home', return_value=Path(self.temp_dir.name))
        self.home_patcher.start()
        self.config_manager = ConfigManager()
        self.log_service = LogService(self.config_manager)

    def tearDown(self) -> None:
        self.home_patcher.stop()
        self.temp_dir.cleanup()

    def test_first_run_records_start_without_clearing(self) -> None:
        self.log_service.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_service.log_file.write_text('keep this', encoding='utf-8')
        now = datetime(2026, 1, 1, 12)

        self.assertFalse(self.log_service.clear_if_due(now))

        self.assertEqual(self.log_service.log_file.read_text(encoding='utf-8'), 'keep this')
        self.assertEqual(
            self.config_manager.load_config()['system']['log_last_cleared_at'],
            now.isoformat(timespec='seconds'),
        )

    def test_clears_after_thirty_days_and_updates_timestamp(self) -> None:
        config = self.config_manager.load_config()
        config['system']['log_last_cleared_at'] = datetime(2026, 1, 1).isoformat()
        self.config_manager.save_config(config)
        self.log_service.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_service.log_file.write_text('old log', encoding='utf-8')

        self.assertTrue(self.log_service.clear_if_due(datetime(2026, 1, 31)))

        self.assertEqual(self.log_service.log_file.read_text(encoding='utf-8'), '')
        self.assertEqual(
            self.config_manager.load_config()['system']['log_last_cleared_at'],
            datetime(2026, 1, 31).isoformat(timespec='seconds'),
        )

    def test_does_not_clear_before_due_or_when_disabled(self) -> None:
        config = self.config_manager.load_config()
        config['system']['log_last_cleared_at'] = datetime(2026, 1, 1).isoformat()
        config['system']['log_auto_clear_enabled'] = False
        self.config_manager.save_config(config)
        self.log_service.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_service.log_file.write_text('keep this', encoding='utf-8')

        self.assertFalse(self.log_service.clear_if_due(datetime(2026, 2, 1)))

        config['system']['log_auto_clear_enabled'] = True
        self.config_manager.save_config(config)
        self.assertFalse(self.log_service.clear_if_due(datetime(2026, 1, 30)))
        self.assertEqual(self.log_service.log_file.read_text(encoding='utf-8'), 'keep this')

    def test_manual_clear_keeps_active_file_handler_writable(self) -> None:
        self.log_service.log_file.parent.mkdir(parents=True)
        handler = RotatingFileHandler(
            self.log_service.log_file, maxBytes=1024, backupCount=1, encoding='utf-8',
        )
        logger = logging.getLogger()
        logger.addHandler(handler)
        try:
            logger.warning('existing log')
            self.log_service.clear_log()
            handler.flush()
            self.assertEqual(self.log_service.log_file.read_text(encoding='utf-8'), '')

            logger.warning('new log')
            handler.flush()
            self.assertIn('new log', self.log_service.log_file.read_text(encoding='utf-8'))
        finally:
            logger.removeHandler(handler)
            handler.close()


if __name__ == '__main__':
    unittest.main()
