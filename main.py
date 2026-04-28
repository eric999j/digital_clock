import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.container import ServiceContainer
from services.config_service import ConfigManager
from ui.main_window import DigitalClock


def _configure_logging() -> None:
    """設定日誌：寫入 ~/.digital_clock/digital_clock.log，並啟用輪替。"""
    log_dir = Path.home() / '.digital_clock'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'digital_clock.log'

    formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # 移除預設 handler，避免重複輸出
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


if __name__ == '__main__':
    _configure_logging()

    container = ServiceContainer()
    config_manager = ConfigManager()
    container.register('config_manager', config_manager)

    clock = DigitalClock(container)
    clock.run()

