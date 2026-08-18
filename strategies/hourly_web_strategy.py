from datetime import datetime
from typing import Any

from .base import CheckStrategy


class HourlyWebReminderStrategy(CheckStrategy):
    """整點網頁提醒策略。"""

    def __init__(self) -> None:
        self.last_triggered_hour: int = -1
        self._last_triggered_hour_key: str = ""

    def check(self, config: dict[str, Any], now: datetime) -> str | None:
        """
        檢查是否應觸發整點網頁提醒。

        Args:
            config: 整點網頁提醒設定
            now: 當前時間

        Returns:
            將要開啟的 URL，或 None 表示不觸發
        """
        if config.get('paused', False):
            return None

        if config.get('work_days_only', True) and now.weekday() > 4:
            return None

        current_hour_key = now.strftime("%Y-%m-%d %H")
        if current_hour_key == self._last_triggered_hour_key:
            return None

        if now.minute > 1:
            return None

        url_rules: list[dict[str, Any]] = config.get('url_rules', [])
        if url_rules:
            for rule in url_rules:
                start = rule.get('start_hour', 0)
                end = rule.get('end_hour', 23)
                if start <= now.hour <= end:
                    url = rule.get('url', '').strip()
                    if url:
                        self.last_triggered_hour = now.hour
                        self._last_triggered_hour_key = current_hour_key
                        return url
            return None

        # 舊版單一 URL 路由
        url = config.get('url', '').strip()
        if not url:
            return None
        start_hour = config.get('start_hour', 8)
        end_hour = config.get('end_hour', 17)
        if start_hour <= now.hour <= end_hour:
            self.last_triggered_hour = now.hour
            self._last_triggered_hour_key = current_hour_key
            return url
        return None
