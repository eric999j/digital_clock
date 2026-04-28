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
        # 記錄上次觸發週期提醒的完整分鐘鍵（格式："YYYY-MM-DD HH:MM"）。
        # 使用完整日期+時間，避免跨小時同分鐘誤判（如 1:30 與 2:30 的 minute 同為 30）。
        self._last_weekly_minute_key: str = ""

    def check(
        self,
        reminders: list[dict[str, Any]],
        now: datetime,
        time_format: str = "%H:%M"
    ) -> list[dict[str, Any]]:
        """
        檢查並回傳需要觸發的提醒清單。

        週期提醒：同一分鐘內只觸發一次（依完整 YYYY-MM-DD HH:MM 去重）。
        單次提醒：只要時間已到且尚未被 Service 層刪除即觸發。

        Args:
            reminders: 提醒清單
            now: 當前時間
            time_format: 週期提醒比對用的時間格式（預設 "%H:%M"）

        Returns:
            需要觸發的提醒清單
        """
        triggered: list[dict[str, Any]] = []
        minute_key = now.strftime("%Y-%m-%d %H:%M")
        current_weekday = now.weekday()
        current_time_str = now.strftime(time_format)
        weekly_already_fired = (minute_key == self._last_weekly_minute_key)

        for r in reminders:
            if r.get('weekdays'):
                # 週期提醒：本分鐘若已觸發則跳過
                if weekly_already_fired:
                    continue
                try:
                    reminder_weekdays = [self.WEEKDAY_MAP[day] for day in r['weekdays']]
                    if current_weekday in reminder_weekdays and r.get('time') == current_time_str:
                        triggered.append(r)
                except KeyError:
                    continue  # 忽略無效的星期字串
            elif 'datetime' in r:
                # 單次提醒：時間已到即觸發（Service 層負責刪除，不需在此去重）
                try:
                    if datetime.strptime(r['datetime'], '%Y-%m-%d %H:%M:%S') <= now:
                        triggered.append(r)
                except ValueError:
                    continue

        # 有週期提醒觸發才更新鍵，避免時間未到時鎖死
        if not weekly_already_fired and any(r.get('weekdays') for r in triggered):
            self._last_weekly_minute_key = minute_key

        return triggered
