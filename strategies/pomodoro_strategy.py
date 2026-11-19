from typing import Any

from .base import PhaseStrategy


class PomodoroStrategy(PhaseStrategy):
    """番茄鐘階段切換策略。"""

    def next_phase(self, phase: str, current_cycle: int, config: dict[str, Any]) -> str:
        """
        根據目前階段決定下一個階段。

        Args:
            phase: 目前階段（FOCUS/SHORT_BREAK/LONG_BREAK）
            current_cycle: 當前循環次數
            config: 番茄鐘設定

        Returns:
            下一個階段名稱
        """
        if phase == "FOCUS":
            cycle_limit = max(1, int(config.get("cycles_before_long_break", 4)))
            if (current_cycle + 1) % cycle_limit == 0:
                return "LONG_BREAK"
            return "SHORT_BREAK"
        return "FOCUS"

