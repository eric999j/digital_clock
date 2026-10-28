"""番茄鐘服務，獨立的番茄鐘引擎。"""
import math
import time
from collections.abc import Callable
from typing import Any


class PomodoroService:
    """獨立番茄鐘引擎，不依賴 tkinter。

    以 deadline（單調時鐘）計算剩餘時間而非逐秒遞減，主迴圈延遲或漏 tick
    都不會造成累積誤差。
    """

    def __init__(
        self,
        config_getter: Callable[[], dict[str, Any]],
        callbacks: dict[str, Callable] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """
        初始化番茄鐘服務。

        Args:
            config_getter: 回傳最新番茄鐘設定的 callable，每次 start 時呼叫以取得最新值
            callbacks: 回調函數字典
            clock: 單調時鐘函數，測試時可注入假時鐘
        """
        self._get_config = config_getter
        self.callbacks = callbacks or {}
        self._clock = clock
        self._deadline: float = 0.0
        self.phase: str = "IDLE"
        self.current_cycle: int = 0

    @property
    def remaining_seconds(self) -> int:
        """目前階段剩餘整數秒（閒置時為 0）。"""
        if self.phase == "IDLE":
            return 0
        # 扣除極小值，避免浮點誤差讓剛開始的階段多算 1 秒
        return max(0, math.ceil(self._deadline - self._clock() - 1e-6))

    @remaining_seconds.setter
    def remaining_seconds(self, seconds: int) -> None:
        self._deadline = self._clock() + seconds

    def start_focus(self) -> None:
        """開始專注階段。"""
        cfg = self._get_config()
        self.phase = "FOCUS"
        self.remaining_seconds = cfg["focus_minutes"] * 60
        self._emit("on_phase_change", self.phase)

    def start_break(self) -> None:
        """開始休息階段（短休息或長休息）。"""
        cfg = self._get_config()
        if self.current_cycle % cfg["cycles_before_long_break"] == 0:
            self.phase = "LONG_BREAK"
            self.remaining_seconds = cfg["long_break"] * 60
        else:
            self.phase = "SHORT_BREAK"
            self.remaining_seconds = cfg["short_break"] * 60
        self._emit("on_phase_change", self.phase)

    def tick(self) -> None:
        """
        由主迴圈每秒呼叫：通知 UI 目前剩餘秒數，時間到即進入下一階段。

        剩餘時間依穿越時間計算，因此漏 tick 或長時間停滽後仍能追上；
        一次 tick 最多推進一個階段，不會連續跳過多個階段。
        """
        if self.phase == "IDLE":
            return

        remaining = self.remaining_seconds
        self._emit("on_tick", self.phase, remaining)

        if remaining <= 0:
            self._complete_phase()

    def _complete_phase(self) -> None:
        """完成當前階段，進入下一階段。"""
        if self.phase == "FOCUS":
            self.current_cycle += 1
            self.start_break()
        else:
            self.start_focus()
        self._emit("on_complete", self.phase)

    def stop(self) -> None:
        """停止番茄鐘。"""
        self.phase = "IDLE"
        self.remaining_seconds = 0
        self._emit("on_phase_change", self.phase)

    def _emit(self, event: str, *args: Any) -> None:
        """
        觸發回調函數。

        Args:
            event: 事件名稱
            *args: 位置參數
        """
        if event in self.callbacks:
            self.callbacks[event](*args)
