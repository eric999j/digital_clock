from collections.abc import Iterator, Sequence
from datetime import datetime
from typing import Any

from core.todo_task import TodoTask

from .base import CheckStrategy


class TodoDueStrategy(CheckStrategy):
    """整點待辦提醒策略：判斷此刻是否該提醒今日到期或逾期的待辦。"""

    def __init__(self) -> None:
        self._last_triggered_hour_key: str = ""

    def check(
        self, config: dict[str, Any], tasks: Sequence[TodoTask], now: datetime,
    ) -> list[dict[str, Any]]:
        """
        檢查是否應提醒到期待辦。

        Args:
            config: ``todo`` 設定（remind_enabled / start_hour / end_hour / work_days_only）
            tasks: 頂層任務清單
            now: 當前時間

        Returns:
            依截止日排序的待辦摘要（逾期在前）；不觸發時回傳空 list。
        """
        if not config.get('remind_enabled', True):
            return []

        hour_key = now.strftime("%Y-%m-%d %H")
        if hour_key == self._last_triggered_hour_key or now.minute > 1:
            return []

        if not config.get('start_hour', 9) <= now.hour <= config.get('end_hour', 17):
            return []
        if config.get('work_days_only', True) and now.weekday() > 4:
            return []

        today = now.date()
        due: list[TodoTask] = [
            task for task in self._walk(tasks)
            if not task.is_done
            and task.due_date is not None
            and task.due_date <= today
            and (task.start_date is None or task.start_date <= today)
        ]
        if not due:
            return []

        self._last_triggered_hour_key = hour_key
        due.sort(key=lambda t: t.due_date or today)
        return [
            {
                'id': task.id,
                'text': task.text,
                'due_date': task.due_date.isoformat() if task.due_date else '',
                'status': 'overdue' if task.due_date and task.due_date < today else 'today',
                'link': task.link,
                'project': task.project,
            }
            for task in due
        ]

    @staticmethod
    def _walk(tasks: Sequence[TodoTask]) -> Iterator[TodoTask]:
        for task in tasks:
            yield task
            yield from TodoDueStrategy._walk(task.children)
