"""設定檔背景寫入器，將 fsync 與原子替換移出 Tk 主執行緒。"""
import copy
import logging
import queue
import threading
from dataclasses import dataclass
from typing import Any

from services.config_service import ConfigManager

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Flush:
    completed: threading.Event


class ConfigWriter:
    """以單一 worker 保持設定寫入順序。"""

    def __init__(self, config_manager: ConfigManager) -> None:
        """
        Args:
            config_manager: 實際負責原子寫入的設定管理器
        """
        self.config_manager = config_manager
        self._queue: queue.Queue[dict[str, Any] | _Flush | None] = queue.Queue()
        self._closed = False
        self._worker = threading.Thread(
            target=self._run,
            name="config-writer",
            daemon=True,
        )
        self._worker.start()

    def submit(self, config: dict[str, Any]) -> None:
        """排入一份設定快照；呼叫端之後修改原 dict 不會影響寫入。"""
        if self._closed:
            raise RuntimeError("ConfigWriter 已關閉")
        self._queue.put(copy.deepcopy(config))

    def flush(self, timeout: float | None = None) -> bool:
        """
        等待目前已排入的寫入完成。

        Args:
            timeout: 最長等待秒數；None 代表無限等待

        Returns:
            是否在期限內完成
        """
        if self._closed:
            self._worker.join(timeout)
            return not self._worker.is_alive()
        completed = threading.Event()
        self._queue.put(_Flush(completed))
        return completed.wait(timeout)

    def close(self) -> None:
        """排空所有工作後停止 writer。"""
        if self._closed:
            return
        self.flush()
        self._closed = True
        self._queue.put(None)
        self._worker.join()

    def _run(self) -> None:
        """依序處理設定快照。"""
        while True:
            item = self._queue.get()
            try:
                if item is None:
                    return
                if isinstance(item, _Flush):
                    item.completed.set()
                    continue
                self.config_manager.save_config(item)
            except Exception:
                logger.exception("背景設定儲存失敗")
            finally:
                self._queue.task_done()
