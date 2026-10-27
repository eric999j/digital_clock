from datetime import datetime
from typing import Any

from core.launch_rules import RULE_URL, rule_key, rule_target
from .base import CheckStrategy


class HourlyWebReminderStrategy(CheckStrategy):
    """整點啟動策略：判斷此刻應啟動哪些網頁或程式規則。"""

    def __init__(self) -> None:
        self.last_triggered_hour: int = -1
        self._last_triggered_hour_key: str = ""

    def check(self, config: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
        """
        檢查是否應觸發整點啟動。

        規則若有 ``weekdays``（0=週一）則以其為準；否則沿用全域 ``work_days_only``。

        Args:
            config: 整點啟動設定
            now: 當前時間

        Returns:
            此刻命中的規則清單（同一目標只保留一筆）；不觸發時回傳空 list。
        """
        if config.get('paused', False):
            return []

        current_hour_key = now.strftime("%Y-%m-%d %H")
        if current_hour_key == self._last_triggered_hour_key:
            return []

        if now.minute > 1:
            return []

        work_days_only = config.get('work_days_only', True)
        rules: list[dict[str, Any]] = config.get('url_rules', [])
        if not rules:
            # 舊版單一 URL 設定
            rules = [{
                'type': RULE_URL,
                'url': config.get('url', ''),
                'start_hour': config.get('start_hour', 8),
                'end_hour': config.get('end_hour', 17),
            }]

        matched: list[dict[str, Any]] = []
        seen: set[tuple[str, ...]] = set()
        for rule in rules:
            if not rule_target(rule):
                continue
            if not rule.get('start_hour', 0) <= now.hour <= rule.get('end_hour', 23):
                continue
            weekdays = rule.get('weekdays')
            if weekdays:
                if now.weekday() not in weekdays:
                    continue
            elif work_days_only and now.weekday() > 4:
                continue
            key = rule_key(rule)
            if key not in seen:
                seen.add(key)
                matched.append(rule)

        if matched:
            self.last_triggered_hour = now.hour
            self._last_triggered_hour_key = current_hour_key
        return matched
