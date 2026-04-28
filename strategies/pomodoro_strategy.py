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
            if (current_cycle + 1) % config.get("cycles_before_long_break", 4) == 0:
                return "LONG_BREAK"
            else:
                return "SHORT_BREAK"
        else:
            return "FOCUS"

