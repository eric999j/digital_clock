"""番茄鐘服務，獨立的番茄鐘引擎。"""
from collections.abc import Callable
from typing import Any


class PomodoroService:
    """獨立番茄鐘引擎，不依賴 tkinter。"""

    def __init__(self, config: dict[str, Any], callbacks: dict[str, Callable] | None = None) -> None:
        """
        初始化番茄鐘服務。

        Args:
            config: 番茄鐘設定
            callbacks: 回調函數字典
        """
        self.config = config
        self.callbacks = callbacks or {}
        self.phase: str = "IDLE"
        self.remaining_seconds: int = 0
        self.current_cycle: int = 0

    def start_focus(self) -> None:
        """開始專注階段。"""
        self.phase = "FOCUS"
        self.remaining_seconds = self.config["focus_minutes"] * 60
        self._emit("on_phase_change", self.phase)

    def start_break(self) -> None:
        """開始休息階段（短休息或長休息）。"""
        if self.current_cycle % self.config["cycles_before_long_break"] == 0:
            self.phase = "LONG_BREAK"
            self.remaining_seconds = self.config["long_break"] * 60
        else:
            self.phase = "SHORT_BREAK"
            self.remaining_seconds = self.config["short_break"] * 60
        self._emit("on_phase_change", self.phase)

    def tick(self) -> None:
        """
        每秒倒數計時。
        在主程式的 update_time 中被調用。
        """
        if self.phase == "IDLE":
            return

        self.remaining_seconds -= 1
        self._emit("on_tick", self.phase, self.remaining_seconds)

        if self.remaining_seconds <= 0:
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
