from datetime import datetime
from typing import Any

from .base import CheckStrategy


class HourlyWebReminderStrategy(CheckStrategy):
    """整點網頁提醒策略。"""

    def __init__(self) -> None:
        self.last_triggered_hour: int = -1
        self._last_triggered_hour_key: str = ""

    def check(self, config: dict[str, Any], now: datetime) -> list[str]:
        """
        檢查是否應觸發整點網頁提醒。

        Args:
            config: 整點網頁提醒設定
            now: 當前時間

        Returns:
            當下時段內所有命中的 URL 清單；不觸發時回傳空 list。
        """
        if config.get('paused', False):
            return []

        if config.get('work_days_only', True) and now.weekday() > 4:
            return []

        current_hour_key = now.strftime("%Y-%m-%d %H")
        if current_hour_key == self._last_triggered_hour_key:
            return []

        if now.minute > 1:
            return []

        matched: list[str] = []
        url_rules: list[dict[str, Any]] = config.get('url_rules', [])
        if url_rules:
            for rule in url_rules:
                start = rule.get('start_hour', 0)
                end = rule.get('end_hour', 23)
                if start <= now.hour <= end:
                    url = rule.get('url', '').strip()
                    if url and url not in matched:
                        matched.append(url)
        else:
            # 舊版單一 URL 路由
            url = config.get('url', '').strip()
            if url:
                start_hour = config.get('start_hour', 8)
                end_hour = config.get('end_hour', 17)
                if start_hour <= now.hour <= end_hour:
                    matched.append(url)

        if matched:
            self.last_triggered_hour = now.hour
            self._last_triggered_hour_key = current_hour_key
        return matched
