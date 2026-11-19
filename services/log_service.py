"""應用程式日誌清理。"""
import logging
from datetime import datetime, timedelta
from logging import FileHandler
from pathlib import Path
from typing import Any

from services.config_service import ConfigManager
from services.config_store import persist_config

logger = logging.getLogger(__name__)

LOG_CLEAR_INTERVAL = timedelta(days=30)


class LogService:
    """管理應用程式日誌檔的清空與定期清理。"""

    def __init__(self, config_manager: ConfigManager) -> None:
        self.config_manager = config_manager
        self.log_file = config_manager.config_dir / 'digital_clock.log'

    def clear_log(self) -> None:
        """清空日誌檔；若檔案正由日誌 handler 開啟，保留 handler 可繼續寫入。"""
        target = self.log_file.resolve()
        active_handlers = [
            handler for handler in logging.getLogger().handlers
            if isinstance(handler, FileHandler)
            and Path(handler.baseFilename).resolve() == target
        ]
        if not active_handlers:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with self.log_file.open('w', encoding='utf-8'):
                pass
            return

        for handler in active_handlers:
            handler.acquire()
            try:
                handler.flush()
                if handler.stream is None:
                    handler.stream = handler._open()
                handler.stream.seek(0)
                handler.stream.truncate()
                handler.flush()
            finally:
                handler.release()

    def clear_if_due(self, now: datetime | None = None) -> bool:
        """到達預設週期時清空日誌；首次啟用時只記錄起算時間。"""
        config: dict[str, Any] = self.config_manager.load_config()
        system_config = config.setdefault('system', {})
        if not system_config.get('log_auto_clear_enabled', True):
            return False

        current_time = now or datetime.now()
        last_cleared_value = system_config.get('log_last_cleared_at')
        if last_cleared_value is None:
            self._save_last_cleared_at(config, current_time)
            return False

        try:
            last_cleared_at = datetime.fromisoformat(last_cleared_value)
            elapsed = current_time - last_cleared_at
        except (TypeError, ValueError):
            logger.warning("Invalid log cleanup timestamp; restarting cleanup interval")
            self._save_last_cleared_at(config, current_time)
            return False

        if elapsed < LOG_CLEAR_INTERVAL:
            return False

        self.clear_log()
        self._save_last_cleared_at(config, current_time)
        return True

    def _save_last_cleared_at(self, config: dict[str, Any], when: datetime) -> None:
        """儲存自動清理週期的起算時間。"""
        config['system']['log_last_cleared_at'] = when.isoformat(timespec='seconds')
        persist_config(self.config_manager, config)
