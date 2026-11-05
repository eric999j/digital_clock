"""待辦事項篩選與搜尋（保留階層，僅回傳命中節點及其祖先）。"""
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from core.todo_task import PRIORITY_HIGH, TodoTask

FILTER_ALL = "all"
FILTER_INCOMPLETE = "incomplete"
FILTER_HIGH = "high"
FILTER_COMPLETED = "completed"
FILTER_OVERDUE = "overdue"
FILTER_DUE_TODAY = "due_today"
FILTER_DUE_WEEK = "due_week"
FILTER_NO_DUE = "no_due"

# (模式, 顯示名稱)，供篩選下拉選單使用
FILTER_MODES: tuple[tuple[str, str], ...] = (
    (FILTER_ALL, "全部"),
    (FILTER_INCOMPLETE, "未完成"),
    (FILTER_HIGH, "高優先"),
    (FILTER_COMPLETED, "已完成"),
    (FILTER_OVERDUE, "逾期"),
    (FILTER_DUE_TODAY, "今日到期"),
    (FILTER_DUE_WEEK, "本週到期"),
    (FILTER_NO_DUE, "未排截止日"),
)


@dataclass(slots=True)
class TodoNode:
    """篩選結果節點：保留階層但只含命中的後代。"""

    task: TodoTask
    children: list["TodoNode"] = field(default_factory=list)


class TodoFilter:
    """待辦事項篩選器。"""

    @staticmethod
    def _prune(tasks: Sequence[TodoTask], predicate: Callable[[TodoTask], bool]) -> list[TodoNode]:
        result: list[TodoNode] = []
        for task in tasks:
            children = TodoFilter._prune(task.children, predicate)
            if predicate(task) or children:
                result.append(TodoNode(task, children))
        return result

    @staticmethod
    def wrap_all(tasks: Sequence[TodoTask]) -> list[TodoNode]:
        """不篩選，完整包成節點樹。"""
        return [TodoNode(task, TodoFilter.wrap_all(task.children)) for task in tasks]

    @staticmethod
    def _predicate(mode: str, today: date) -> Callable[[TodoTask], bool]:
        week_end = today + timedelta(days=7)
        predicates: dict[str, Callable[[TodoTask], bool]] = {
            FILTER_INCOMPLETE: lambda t: not t.is_done,
            FILTER_HIGH: lambda t: t.priority == PRIORITY_HIGH,
            FILTER_COMPLETED: lambda t: t.is_done,
            FILTER_OVERDUE: lambda t: not t.is_done and t.due_date is not None and t.due_date < today,
            FILTER_DUE_TODAY: lambda t: not t.is_done and t.due_date == today,
            FILTER_DUE_WEEK: lambda t: (
                not t.is_done and t.due_date is not None and today < t.due_date <= week_end
            ),
            FILTER_NO_DUE: lambda t: t.due_date is None,
        }
        return predicates[mode]

    @staticmethod
    def filter_tasks(tasks: Sequence[TodoTask], mode: str, today: date | None = None) -> list[TodoNode]:
        """
        依模式篩選。

        Args:
            tasks: 頂層任務清單
            mode: ``FILTER_*`` 常數；未知模式視為全部
            today: 基準日；缺省為今天

        Returns:
            保留階層的節點樹
        """
        if mode == FILTER_ALL or mode not in dict(FILTER_MODES):
            return TodoFilter.wrap_all(tasks)
        return TodoFilter._prune(tasks, TodoFilter._predicate(mode, today or date.today()))

    @staticmethod
    def search_nodes(nodes: Sequence[TodoNode], query: str) -> list[TodoNode]:
        """在節點樹中以關鍵字（不分大小寫，比對內容與專案）搜尋，保留命中者的祖先。"""
        needle = query.strip().lower()
        if not needle:
            return list(nodes)
        result: list[TodoNode] = []
        for node in nodes:
            children = TodoFilter.search_nodes(node.children, query)
            task = node.task
            hit = needle in task.text.lower() or needle in (task.project or "").lower()
            if hit or children:
                result.append(TodoNode(task, children))
        return result

    @staticmethod
    def apply(
        tasks: Sequence[TodoTask], mode: str = FILTER_ALL, query: str = "", today: date | None = None,
    ) -> list[TodoNode]:
        """先依模式篩選再套用關鍵字搜尋。"""
        return TodoFilter.search_nodes(TodoFilter.filter_tasks(tasks, mode, today), query)

    @staticmethod
    def count_tasks(tasks: Sequence[TodoTask]) -> tuple[int, int, int]:
        """
        統計任務數（以葉節點為單位；已完成父項視為一項完成，其子孫不再重複計算）。

        Returns:
            (總數, 待辦數, 完成數)
        """
        pending = done = 0
        for task in tasks:
            if task.is_done:
                done += 1
            elif task.children:
                _, child_pending, child_done = TodoFilter.count_tasks(task.children)
                pending += child_pending
                done += child_done
            else:
                pending += 1
        return pending + done, pending, done
