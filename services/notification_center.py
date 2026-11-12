"""統一通知中心：彙整番茄鐘、提醒、倒數、待辦與行事曆的通知歷史（僅存記憶體）。"""
import itertools
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.events import Events
from core.observer import Observer

logger = logging.getLogger(__name__)

SOURCE_POMODORO = "pomodoro"
SOURCE_REMINDER = "reminder"
SOURCE_COUNTDOWN = "countdown"
SOURCE_TODO = "todo"
SOURCE_CALENDAR = "calendar"

SOURCE_LABELS = {
    SOURCE_POMODORO: "番茄鐘",
    SOURCE_REMINDER: "提醒",
    SOURCE_COUNTDOWN: "倒數",
    SOURCE_TODO: "待辦",
    SOURCE_CALENDAR: "行事曆",
}

_PHASE_TEXT = {"FOCUS": "專注", "SHORT_BREAK": "短休息", "LONG_BREAK": "長休息", "IDLE": "就緒"}
DEFAULT_MAX_ITEMS = 200


@dataclass
class Notification:
    """一則通知。"""

    id: int
    source: str
    title: str
    message: str
    timestamp: datetime
    read: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def source_label(self) -> str:
        return SOURCE_LABELS.get(self.source, self.source)


class NotificationCenter(Observer):
    """訂閱各模組事件並轉成統一格式；保留最近 ``max_items`` 則。

    待辦通知只記錄件數，不保存任務文字，避免待辦內容散落到其他位置。
    """

    def __init__(
        self,
        notify_callback: Callable[..., None],
        max_items: int = DEFAULT_MAX_ITEMS,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        """
        Args:
            notify_callback: 通知回調 ``(event, *args)``
            max_items: 歷史上限，超過時丟棄最舊的
            clock: 取得現在時間的函數，測試時可注入
        """
        self.notify = notify_callback
        self._clock = clock
        self._items: deque[Notification] = deque(maxlen=max(1, max_items))
        self._ids = itertools.count(1)

    # ---- 查詢 ----

    def items(self, source: str | None = None) -> list[Notification]:
        """由新到舊回傳通知；可指定來源篩選。"""
        return [n for n in reversed(self._items) if source is None or n.source == source]

    def unread_count(self) -> int:
        return sum(1 for n in self._items if not n.read)

    # ---- 操作 ----

    def add(self, source: str, title: str, message: str, **extra: Any) -> Notification:
        """新增通知並發出 ``NOTIFICATION_ADDED`` 與 ``NOTIFICATIONS_CHANGED``。"""
        item = Notification(next(self._ids), source, title, message, self._clock(), extra=extra)
        self._items.append(item)
        self.notify(Events.NOTIFICATION_ADDED, item)
        self._changed()
        return item

    def mark_all_read(self) -> None:
        unread = [n for n in self._items if not n.read]
        for item in unread:
            item.read = True
        if unread:
            self._changed()

    def clear(self) -> None:
        if self._items:
            self._items.clear()
            self._changed()

    def _changed(self) -> None:
        self.notify(Events.NOTIFICATIONS_CHANGED, self.unread_count())

    # ---- Observer ----

    def update(self, event: str, *args: Any, **kwargs: Any) -> None:
        """把支援的事件轉成通知；其餘事件（含自己發出的）忽略。"""
        built = self._build(event, args)
        if built is not None:
            self.add(*built)

    @staticmethod
    def _build(event: str, args: tuple[Any, ...]) -> tuple[str, str, str] | None:
        first = args[0] if args else None
        if event == Events.POMODORO_PHASE_COMPLETE:
            return SOURCE_POMODORO, "番茄鐘", f"階段結束，進入 {_PHASE_TEXT.get(first, first)}"
        if event == Events.REMINDER_DUE and isinstance(first, dict):
            title = first.get('title') or '提醒'
            return SOURCE_REMINDER, title, first.get('message') or first.get('title') or '提醒時間到了'
        if event == Events.COUNTDOWN_FINISHED:
            name = f"「{first}」" if first else ""
            return SOURCE_COUNTDOWN, "倒數計時", f"{name}倒數結束了"
        if event == Events.TODO_DUE and isinstance(first, list):
            overdue = sum(1 for i in first if isinstance(i, dict) and i.get('status') == 'overdue')
            today = len(first) - overdue
            return SOURCE_TODO, "待辦提醒", f"逾期 {overdue} 項、今日到期 {today} 項"
        if event == Events.CALENDAR_EVENT_UPCOMING:
            minutes = args[1] if len(args) > 1 else 0
            name = f"「{first}」" if first else "行事曆事件"
            return SOURCE_CALENDAR, "行事曆預告", f"{name}約 {minutes} 分鐘後開始"
        if event == Events.CALENDAR_EVENT_STARTED:
            name = f"「{first}」" if first else "行事曆事件"
            return SOURCE_CALENDAR, "行事曆", f"{name}開始，會議中"
        return None
