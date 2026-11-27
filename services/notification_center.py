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
from services.config_service import ConfigManager
from services.config_store import persist_config

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
    deferred: bool = False
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
        config_manager: ConfigManager | None = None,
        state_getter: Callable[[], Any] | None = None,
    ) -> None:
        """
        Args:
            notify_callback: 通知回調 ``(event, *args)``
            max_items: 歷史上限，超過時丟棄最舊的
            clock: 取得現在時間的函數，測試時可注入
            config_manager: 智慧通知設定來源
            state_getter: 回傳目前 AppState snapshot 的函數
        """
        self.notify = notify_callback
        self._clock = clock
        self.config_manager = config_manager
        self._state_getter = state_getter
        self._was_quiet = self._is_quiet()
        self._items: deque[Notification] = deque(maxlen=max(1, max_items))
        self._ids = itertools.count(1)
        self._deferred_ids: set[int] = set()

    # ---- 查詢 ----

    def items(self, source: str | None = None) -> list[Notification]:
        """由新到舊回傳通知；可指定來源篩選。"""
        return [n for n in reversed(self._items) if source is None or n.source == source]

    def get_item(self, notification_id: int) -> Notification | None:
        """依識別碼取得通知；通知已清除或淘汰時回傳 None。"""
        return next((item for item in self._items if item.id == notification_id), None)

    def unread_count(self) -> int:
        return sum(1 for n in self._items if not n.read)

    # ---- 操作 ----

    def add(
        self,
        source: str,
        title: str,
        message: str,
        deferred: bool = False,
        **extra: Any,
    ) -> Notification:
        """新增通知並發出 ``NOTIFICATION_ADDED`` 與 ``NOTIFICATIONS_CHANGED``。"""
        item = Notification(
            next(self._ids),
            source,
            title,
            message,
            self._clock(),
            deferred=deferred,
            extra=extra,
        )
        self._items.append(item)
        if deferred:
            self._deferred_ids.add(item.id)
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
            self._deferred_ids.clear()
            self._changed()

    def _changed(self) -> None:
        self.notify(Events.NOTIFICATIONS_CHANGED, self.unread_count())

    # ---- Observer ----

    def update(self, event: str, *args: Any, **kwargs: Any) -> None:
        """把支援的事件轉成通知；其餘事件（含自己發出的）忽略。"""
        if event == Events.APP_STATE_CHANGED:
            is_quiet = self._snapshot_is_quiet(args[0] if args else None)
            if self._was_quiet and not is_quiet:
                self._release_deferred()
            self._was_quiet = is_quiet
            return
        built = self._build(event, args)
        if built is not None:
            self.add(*built, deferred=self.should_defer(event, *args))

    def get_settings(self) -> dict[str, bool]:
        """取得智慧通知設定，未注入設定管理器時使用安全預設。"""
        if self.config_manager is None:
            return {
                'queue_during_quiet': True,
                'allow_high_priority_todo': True,
                'allow_reminder_override': True,
            }
        config = self.config_manager.load_config(read_only=True).get(
            'notifications',
            {},
        )
        return {
            'queue_during_quiet': bool(config.get('queue_during_quiet', True)),
            'allow_high_priority_todo': bool(
                config.get('allow_high_priority_todo', True)
            ),
            'allow_reminder_override': bool(
                config.get('allow_reminder_override', True)
            ),
        }

    def update_settings(self, **changes: bool) -> dict[str, bool]:
        """更新智慧通知設定；忽略不支援的欄位。"""
        if self.config_manager is None:
            return self.get_settings()
        current = self.get_settings()
        for key in current:
            if key in changes:
                current[key] = bool(changes[key])
        config = self.config_manager.load_config()
        config['notifications'] = current
        persist_config(self.config_manager, config)
        return current

    def should_defer(self, event: str, *args: Any) -> bool:
        """判斷事件是否應只送入通知中心，留待離開安靜狀態後提示。"""
        settings = self.get_settings()
        if not settings['queue_during_quiet'] or not self._is_quiet():
            return False
        if event == Events.REMINDER_DUE:
            reminder = args[0] if args and isinstance(args[0], dict) else {}
            return not (
                settings['allow_reminder_override']
                and bool(reminder.get('allow_during_quiet', False))
            )
        if event == Events.TODO_DUE:
            items = args[0] if args and isinstance(args[0], list) else []
            has_high_priority = any(
                isinstance(item, dict) and item.get('priority') == 'high'
                for item in items
            )
            return not (
                settings['allow_high_priority_todo']
                and has_high_priority
            )
        return event in {
            Events.POMODORO_PHASE_COMPLETE,
            Events.COUNTDOWN_FINISHED,
            Events.CALENDAR_EVENT_UPCOMING,
            Events.CALENDAR_EVENT_STARTED,
        }

    def _release_deferred(self) -> None:
        """將延後通知依來源合併後發出單一摘要事件。"""
        if not self._deferred_ids:
            return
        grouped: dict[str, dict[str, Any]] = {}
        for item in self._items:
            if item.id not in self._deferred_ids:
                continue
            item.deferred = False
            summary = grouped.setdefault(
                item.source,
                {
                    'source': item.source,
                    'source_label': item.source_label,
                    'count': 0,
                },
            )
            summary['count'] += 1
        self._deferred_ids.clear()
        if grouped:
            self.notify(Events.NOTIFICATIONS_RELEASED, list(grouped.values()))

    def _is_quiet(self) -> bool:
        if self._state_getter is None:
            return False
        return self._snapshot_is_quiet(self._state_getter())

    @staticmethod
    def _snapshot_is_quiet(snapshot: Any) -> bool:
        return bool(getattr(snapshot, 'is_quiet', False))

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
