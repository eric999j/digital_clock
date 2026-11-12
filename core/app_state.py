"""跨模組應用程式狀態：由事件彙整番茄鐘、倒數、勿擾、暫停、待辦與行事曆的即時狀態。"""
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from core.events import Events
from core.observer import Observer

logger = logging.getLogger(__name__)

POMODORO_IDLE = "IDLE"


@dataclass(frozen=True)
class AppStateSnapshot:
    """某一時刻的跨模組狀態（不可變，可直接比較是否改變）。"""

    pomodoro_phase: str = POMODORO_IDLE
    pomodoro_paused: bool = False
    countdown_active: bool = False
    countdown_paused: bool = False
    on_vacation: bool = False
    reminders_paused: bool = False
    hourly_web_paused: bool = False
    todo_pending: int = 0
    in_meeting: bool = False

    @property
    def is_focusing(self) -> bool:
        """是否正在專注（番茄鐘專注階段且未暫停）。"""
        return self.pomodoro_phase == "FOCUS" and not self.pomodoro_paused

    @property
    def is_quiet(self) -> bool:
        """使用者是否不宜被打擾：勿擾、會議中或專注中。"""
        return self.on_vacation or self.in_meeting or self.is_focusing


class AppState(Observer):
    """單一狀態來源：訂閱事件更新快照，快照改變時才發出 ``APP_STATE_CHANGED``。

    倒數／番茄鐘的 tick 不會改變快照，因此不會造成事件洪水。
    """

    def __init__(self, notify_callback: Callable[..., None]) -> None:
        """
        Args:
            notify_callback: 通知回調 ``(event, *args)``，通常為 ``ClockLogic.notify_observers``
        """
        self.notify = notify_callback
        self._snapshot = AppStateSnapshot()

    @property
    def snapshot(self) -> AppStateSnapshot:
        return self._snapshot

    def sync(self, **fields: Any) -> None:
        """以權威來源直接設定欄位（啟動時用既有設定初始化）。"""
        self._apply(**fields)

    def update(self, event: str, *args: Any, **kwargs: Any) -> None:
        """依事件更新狀態；不認得的事件（含自己發出的）一律忽略。"""
        changes = self._changes_for(event, args)
        if changes:
            self._apply(**changes)

    @staticmethod
    def _changes_for(event: str, args: tuple[Any, ...]) -> dict[str, Any]:
        first = args[0] if args else None
        if event == Events.POMODORO_PHASE_CHANGE:
            return {'pomodoro_phase': str(first or POMODORO_IDLE),
                    'pomodoro_paused': False}
        if event == Events.POMODORO_PAUSE_TOGGLED:
            return {'pomodoro_paused': bool(first)}
        if event == Events.COUNTDOWN_STARTED:
            return {'countdown_active': True, 'countdown_paused': False}
        if event == Events.COUNTDOWN_PAUSE_TOGGLED:
            return {'countdown_active': True, 'countdown_paused': bool(first)}
        if event in (Events.COUNTDOWN_CANCELLED, Events.COUNTDOWN_FINISHED):
            return {'countdown_active': False, 'countdown_paused': False}
        if event == Events.VACATION_TOGGLED:
            return {'on_vacation': bool(first)}
        if event == Events.REMINDER_PAUSE_TOGGLED:
            return {'reminders_paused': bool(first)}
        if event == Events.HOURLY_WEB_PAUSE_TOGGLED:
            return {'hourly_web_paused': bool(first)}
        if event == Events.TODO_UPDATED and isinstance(first, int) and not isinstance(first, bool):
            return {'todo_pending': max(first, 0)}
        if event == Events.CALENDAR_EVENT_STARTED:
            return {'in_meeting': True}
        if event == Events.CALENDAR_EVENT_ENDED:
            return {'in_meeting': False}
        return {}

    def _apply(self, **fields: Any) -> None:
        updated = replace(self._snapshot, **fields)
        if updated == self._snapshot:
            return
        self._snapshot = updated
        self.notify(Events.APP_STATE_CHANGED, updated)
