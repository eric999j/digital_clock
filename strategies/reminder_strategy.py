from datetime import datetime
from typing import Any

from .base import CheckStrategy


class ReminderStrategy(CheckStrategy):
    """提醒檢查策略。"""

    WEEKDAY_MAP = {
        "週一": 0, "週二": 1, "週三": 2, "週四": 3,
        "週五": 4, "週六": 5, "週日": 6
    }

    def __init__(self) -> None:
        # _datetime_cache 只做純字串解析，不含觸發狀態，屬性保留於此。
        self._datetime_cache: dict[str, datetime | None] = {}
        self._datetime_cache_limit = 1024

    def check(
        self,
        reminders: list[dict[str, Any]],
        now: datetime,
        time_format: str = "%H:%M",
        last_minute_key: str = "",
    ) -> tuple[list[dict[str, Any]], str]:
        """
        檢查並回傳需要觸發的提醒清單與更新後的週期去重鍵。

        Args:
            reminders: 提醒清單
            now: 當前時間
            time_format: 週期提醒比對用的時間格式（預設 "%H:%M"）
            last_minute_key: 上次週期提醒觸發的分鐘鍵，由呼叫端持有與傳入

        Returns:
            (triggered_reminders, updated_minute_key)
        """
        triggered: list[dict[str, Any]] = []
        minute_key = now.strftime("%Y-%m-%d %H:%M")
        current_weekday = now.weekday()
        current_time_str = now.strftime(time_format)
        weekly_already_fired = (minute_key == last_minute_key)

        for r in reminders:
            if r.get('weekdays'):
                if weekly_already_fired:
                    continue
                try:
                    reminder_weekdays = [self.WEEKDAY_MAP[day] for day in r['weekdays']]
                    if current_weekday in reminder_weekdays and r.get('time') == current_time_str:
                        triggered.append(r)
                except KeyError:
                    continue
            elif 'datetime' in r:
                reminder_datetime = self._parse_datetime(r['datetime'])
                if reminder_datetime is not None and reminder_datetime <= now:
                    triggered.append(r)

        # 有週期提醒觸發才更新鍵，避免時間未到時鎖死
        new_key = (
            minute_key
            if not weekly_already_fired and any(r.get('weekdays') for r in triggered)
            else last_minute_key
        )
        return triggered, new_key

    def _parse_datetime(self, value: Any) -> datetime | None:
        """
        解析單次提醒時間並快取結果，避免每秒重複解析相同字串。

        Args:
            value: 單次提醒時間字串

        Returns:
            datetime 物件；格式無效時回傳 None
        """
        if not isinstance(value, str):
            return None

        cached = self._datetime_cache.get(value)
        if cached is not None or value in self._datetime_cache:
            return cached

        try:
            parsed = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            parsed = None

        if len(self._datetime_cache) >= self._datetime_cache_limit:
            self._datetime_cache.clear()
        self._datetime_cache[value] = parsed
        return parsed
