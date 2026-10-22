"""倒數計時服務，獨立的倒數引擎（不依賴 tkinter）。"""
import logging
import math
import time
from collections.abc import Callable
from typing import Any

from core.events import Events

logger = logging.getLogger(__name__)


class CountdownService:
    """單一倒數計時器：支援開始、暫停/繼續、取消，並以單調時鐘計算剩餘時間。

    以 deadline（``time.monotonic``）計算而非逐秒遞減，因此 UI 迴圈延遲或系統時間
    被調整都不會造成累積誤差。
    """

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"

    MAX_SECONDS: int = 24 * 60 * 60
    MAX_LABEL_LENGTH: int = 40

    def __init__(
        self,
        notify_callback: Callable[..., None],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """
        初始化倒數計時服務。

        Args:
            notify_callback: 通知回調函數 (event, *args)
            clock: 單調時鐘函數，測試時可注入假時鐘
        """
        self.notify = notify_callback
        self._clock = clock
        self.state: str = self.IDLE
        self.label: str = ""
        self.total_seconds: int = 0
        self._deadline: float = 0.0
        self._paused_remaining: float = 0.0
        self._last_reported: int | None = None

    @property
    def is_active(self) -> bool:
        """是否有進行中（執行或暫停）的倒數。"""
        return self.state != self.IDLE

    @property
    def is_paused(self) -> bool:
        """倒數是否處於暫停狀態。"""
        return self.state == self.PAUSED

    def remaining_seconds(self) -> int:
        """回傳剩餘整數秒（無倒數時為 0）。"""
        if self.state == self.RUNNING:
            return max(0, math.ceil(self._deadline - self._clock()))
        if self.state == self.PAUSED:
            return max(0, math.ceil(self._paused_remaining))
        return 0

    def start(self, seconds: int, label: str = "") -> None:
        """
        開始倒數；若已有倒數進行中則直接取代。

        Args:
            seconds: 倒數秒數，需介於 1 與 ``MAX_SECONDS``
            label: 倒數名稱（可空白）

        Raises:
            ValueError: 秒數不是範圍內的整數
        """
        if not isinstance(seconds, int) or isinstance(seconds, bool) or not 1 <= seconds <= self.MAX_SECONDS:
            raise ValueError(f"倒數秒數必須介於 1 到 {self.MAX_SECONDS}")

        self.label = (label or "").strip()[:self.MAX_LABEL_LENGTH]
        self.total_seconds = seconds
        self._deadline = self._clock() + seconds
        self.state = self.RUNNING
        self._last_reported = seconds
        self.notify(Events.COUNTDOWN_STARTED, seconds, self.label)

    def pause(self) -> None:
        """暫停倒數；非執行中時不做事。"""
        if self.state != self.RUNNING:
            return
        self._paused_remaining = max(0.0, self._deadline - self._clock())
        self.state = self.PAUSED
        self.notify(Events.COUNTDOWN_PAUSE_TOGGLED, True, self.remaining_seconds(), self.label)

    def resume(self) -> None:
        """繼續倒數；非暫停中時不做事。"""
        if self.state != self.PAUSED:
            return
        self._deadline = self._clock() + self._paused_remaining
        self.state = self.RUNNING
        self.notify(Events.COUNTDOWN_PAUSE_TOGGLED, False, self.remaining_seconds(), self.label)

    def toggle_pause(self) -> None:
        """在暫停與繼續之間切換。"""
        if self.state == self.RUNNING:
            self.pause()
        elif self.state == self.PAUSED:
            self.resume()

    def cancel(self) -> None:
        """取消倒數；無倒數時不做事。"""
        if self.state == self.IDLE:
            return
        label = self.label
        self._reset()
        self.notify(Events.COUNTDOWN_CANCELLED, label)

    def tick(self) -> None:
        """
        每秒由主迴圈呼叫：剩餘秒數改變時發出 TICK，歸零時發出 FINISHED 並回到閒置。
        """
        if self.state != self.RUNNING:
            return

        remaining = self.remaining_seconds()
        if remaining <= 0:
            label, total = self.label, self.total_seconds
            self._reset()
            self.notify(Events.COUNTDOWN_FINISHED, label, total)
            return

        if remaining != self._last_reported:
            self._last_reported = remaining
            self.notify(Events.COUNTDOWN_TICK, remaining, self.label)

    def _reset(self) -> None:
        """回到閒置狀態並清除計時資料。"""
        self.state = self.IDLE
        self.label = ""
        self.total_seconds = 0
        self._deadline = 0.0
        self._paused_remaining = 0.0
        self._last_reported = None

    @staticmethod
    def format_remaining(seconds: int) -> str:
        """將秒數格式化為 ``MM:SS``；滿一小時則為 ``H:MM:SS``。"""
        seconds = max(0, int(seconds))
        hours, rest = divmod(seconds, 3600)
        minutes, secs = divmod(rest, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def snapshot(self) -> dict[str, Any]:
        """回傳目前狀態快照，供 UI 刷新選單與顯示使用。"""
        return {
            "state": self.state,
            "label": self.label,
            "remaining": self.remaining_seconds(),
            "total": self.total_seconds,
        }
