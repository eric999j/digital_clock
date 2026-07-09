"""休假排程策略：依日期分類排定的休假。"""
from datetime import date
from typing import Any, TypedDict

from .base import CheckStrategy


class VacationScheduleClassification(TypedDict):
    """依當前日期分類的休假排程結果。"""

    expired: list[dict[str, Any]]
    active: list[dict[str, Any]]
    future: list[dict[str, Any]]
    invalid: list[dict[str, Any]]


class VacationScheduleStrategy(CheckStrategy):
    """依當前日期將休假排程分類為 expired / active / future / invalid。

    - expired：`end < today`
    - active：`start <= today <= end`
    - future：`today < start`
    - invalid：欄位缺失、日期無法解析，或 `end < start`
    """

    def check(
        self,
        schedules: list[dict[str, Any]],
        today: date,
    ) -> VacationScheduleClassification:
        """
        依當前日期分類排程。

        Args:
            schedules: 排程清單，每筆需含 `start` 與 `end`（ISO 日期字串）。
            today: 用來比對的當前日期。

        Returns:
            以清單分類的排程結果。
        """
        expired: list[dict[str, Any]] = []
        active: list[dict[str, Any]] = []
        future: list[dict[str, Any]] = []
        invalid: list[dict[str, Any]] = []

        for schedule in schedules:
            start, end = self._parse_dates(schedule)
            if start is None or end is None or end < start:
                invalid.append(schedule)
                continue
            if end < today:
                expired.append(schedule)
            elif start <= today <= end:
                active.append(schedule)
            else:
                future.append(schedule)

        return {
            'expired': expired,
            'active': active,
            'future': future,
            'invalid': invalid,
        }

    @staticmethod
    def _parse_dates(schedule: dict[str, Any]) -> tuple[date | None, date | None]:
        """解析排程的 start/end 為 date；失敗則回傳 (None, None)。"""
        try:
            start = date.fromisoformat(str(schedule['start']))
            end = date.fromisoformat(str(schedule['end']))
            return start, end
        except (KeyError, TypeError, ValueError):
            return None, None
