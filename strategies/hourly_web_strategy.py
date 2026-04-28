from datetime import datetime
from typing import Any

from .base import CheckStrategy


class HourlyWebReminderStrategy(CheckStrategy):
    """整點網頁提醒策略。"""

    def __init__(self):
        self.last_triggered_hour: int = -1

    def check(self, config: dict[str, Any], now: datetime) -> bool:
        """
        檢查是否應觸發整點網頁提醒。

        Args:
            config: 整點網頁提醒設定 (包含 url, start_hour, end_hour, paused)
            now: 當前時間

        Returns:
            是否應觸發
        """
        # 檢查是否暫停 (注意：這裡的暫停是在 config 內的，如果 Service 有額外暫停旗標需在 Service 處理或傳入)
        # 原始代碼直接檢查 config.get('paused')
        if config.get('paused', False):
            return False

        url = config.get('url', '').strip()
        if not url:
            return False

        # 根據設定決定是否限制上班日（預設 True，可在設定中關閉）
        if config.get('work_days_only', True) and now.weekday() > 4:
            return False

        current_hour = now.hour
        start_hour = config.get('start_hour', 8)
        end_hour = config.get('end_hour', 17)

        # 避免同一小時內重複觸發
        if current_hour == self.last_triggered_hour:
            return False

        # 檢查是否在指定時段 (Start <= Current <= End)
        in_time_range = start_hour <= current_hour <= end_hour

        # 檢查是否在整點的前2分鐘內觸發（確保不錯過，原始邏輯為 <= 1）
        if now.minute <= 1 and in_time_range:
            self.last_triggered_hour = current_hour
            return True

        return False
