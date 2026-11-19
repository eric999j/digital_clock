"""型別化 Observer 事件：保留既有字串事件相容介面。"""
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, ClassVar

from core.events import Events


@dataclass(frozen=True)
class TypedEvent:
    """Observer 可解碼的事件封包。"""

    name: str
    args: tuple[Any, ...] = ()
    kwargs: Mapping[str, Any] = MappingProxyType({})

    def legacy(self) -> tuple[str, tuple[Any, ...], dict[str, Any]]:
        """轉成既有 Observer 與 handler 的呼叫形式。"""
        return self.name, self.args, dict(self.kwargs)


@dataclass(frozen=True)
class PhaseChanged(TypedEvent):
    """番茄鐘階段改變。"""

    name: str = Events.POMODORO_PHASE_CHANGE


@dataclass(frozen=True)
class PhaseTick(TypedEvent):
    """番茄鐘每秒更新。"""

    name: str = Events.POMODORO_TICK


@dataclass(frozen=True)
class CountdownUpdated(TypedEvent):
    """倒數狀態或剩餘時間更新。"""

    name: str = Events.COUNTDOWN_TICK


EVENT_ARGUMENT_COUNTS: Mapping[str, tuple[int, int]] = MappingProxyType({
    Events.POMODORO_PHASE_CHANGE: (1, 1),
    Events.POMODORO_TICK: (2, 2),
    Events.POMODORO_PHASE_COMPLETE: (1, 1),
    Events.POMODORO_PAUSE_TOGGLED: (1, 1),
    Events.REMINDER_DUE: (1, 1),
    Events.REMINDER_SNOOZED: (2, 2),
    Events.COUNTDOWN_STARTED: (2, 2),
    Events.COUNTDOWN_TICK: (2, 2),
    Events.COUNTDOWN_PAUSE_TOGGLED: (3, 3),
    Events.COUNTDOWN_FINISHED: (2, 2),
    Events.COUNTDOWN_CANCELLED: (1, 1),
    Events.TODO_UPDATED: (1, 1),
    Events.TODO_DUE: (1, 1),
    Events.TODO_REMIND_TOGGLED: (1, 1),
    Events.VACATION_TOGGLED: (1, 1),
    Events.CALENDAR_EVENT_UPCOMING: (2, 2),
    Events.CALENDAR_EVENT_STARTED: (1, 1),
    Events.SCREENSHOT_TRIGGERED: (0, 0),
})


def as_typed_event(
    event: str | TypedEvent,
    *args: Any,
    **kwargs: Any,
) -> TypedEvent:
    """
    將既有事件呼叫包裝為型別封包並檢查已知 payload 長度。

    Args:
        event: 事件名稱或既有封包
        *args: 既有位置參數
        **kwargs: 既有關鍵字參數

    Returns:
        不可變事件封包

    Raises:
        ValueError: 已註冊事件的 payload 長度不符
    """
    if isinstance(event, TypedEvent):
        if args or kwargs:
            raise ValueError("TypedEvent 不可再附加額外 payload")
        wrapped = event
    else:
        wrapped = TypedEvent(event, tuple(args), MappingProxyType(dict(kwargs)))

    expected = EVENT_ARGUMENT_COUNTS.get(wrapped.name)
    payload_count = len(wrapped.args) + len(wrapped.kwargs)
    if expected is not None and not expected[0] <= payload_count <= expected[1]:
        raise ValueError(
            f"事件 {wrapped.name!r} 預期 {expected[0]}..{expected[1]} "
            f"個 payload 欄位，實際為 {payload_count}"
        )
    return wrapped


class EventPublisher:
    """建立型別封包的集中入口，供新服務逐步採用。"""

    EVENT_TYPE: ClassVar[type[TypedEvent]] = TypedEvent

    @classmethod
    def publish(cls, name: str, *args: Any, **kwargs: Any) -> TypedEvent:
        """建立已驗證事件封包。"""
        return as_typed_event(name, *args, **kwargs)
