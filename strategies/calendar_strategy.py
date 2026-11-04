"""行事曆休假策略：依事件時間區間判斷目前是否應處於休假。"""
from datetime import datetime, timedelta
from typing import Any, TypedDict

from strategies.base import CheckStrategy


class CalendarInterval(TypedDict):
    """合併後的事件區間（皆為本地無時區時間）。"""

    start: datetime
    end: datetime
    summary: str


class CalendarCheckResult(TypedDict):
    """策略判斷結果。"""

    active: bool
    current: CalendarInterval | None
    upcoming: CalendarInterval | None


class CalendarVacationStrategy(CheckStrategy):
    """判斷行事曆事件是否進行中或即將開始。

    重疊或首尾相接的事件會先合併，避免連續會議之間短暫跳出休假。
    """

    def check(
        self,
        events: list[dict[str, Any]],
        now: datetime,
        lead_minutes: int = 0,
    ) -> CalendarCheckResult:
        """
        檢查目前時間與事件的關係。

        Args:
            events: 事件清單，每筆含 `start`/`end`（本地 naive datetime）與 `summary`
            now: 目前時間（本地 naive datetime）
            lead_minutes: 事件開始前幾分鐘視為「即將開始」；0 表示不預告

        Returns:
            `active`: 是否有事件進行中；`current`: 進行中的合併區間；
            `upcoming`: 預告時間窗內最近一個尚未開始的合併區間。
        """
        current: CalendarInterval | None = None
        upcoming: CalendarInterval | None = None
        lead = timedelta(minutes=max(0, lead_minutes))

        for interval in self._merge(events):
            if interval['start'] <= now < interval['end']:
                current = interval
            elif lead and now < interval['start'] <= now + lead and upcoming is None:
                upcoming = interval

        return {'active': current is not None, 'current': current, 'upcoming': upcoming}

    @staticmethod
    def _merge(events: list[dict[str, Any]]) -> list[CalendarInterval]:
        """排序並合併重疊／相接的事件，忽略無效區間。"""
        valid = [
            e for e in events
            if isinstance(e.get('start'), datetime)
            and isinstance(e.get('end'), datetime)
            and e['end'] > e['start']
        ]
        valid.sort(key=lambda e: e['start'])

        merged: list[CalendarInterval] = []
        for event in valid:
            if merged and event['start'] <= merged[-1]['end']:
                if event['end'] > merged[-1]['end']:
                    merged[-1]['end'] = event['end']
                continue
            merged.append({
                'start': event['start'],
                'end': event['end'],
                'summary': str(event.get('summary') or ''),
            })
        return merged
