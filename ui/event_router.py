"""數位時鐘 UI 事件路由。"""
from collections.abc import Callable
from typing import Any

from core.events import Events

EventHandler = Callable[..., None]


def build_event_handlers(ui: Any) -> dict[str, EventHandler]:
    """建立既有事件名稱與 UI handler 的相容路由表。"""
    return {
        Events.POMODORO_PHASE_CHANGE: ui._on_pomodoro_phase_change,
        Events.POMODORO_TICK: ui._on_pomodoro_tick,
        Events.POMODORO_PHASE_COMPLETE: ui._on_pomodoro_phase_complete,
        Events.POMODORO_PAUSE_TOGGLED: ui._on_pomodoro_pause_toggled,
        Events.REMINDER_DUE: ui._on_reminder_due,
        Events.REMINDER_SNOOZED: ui._on_reminder_snoozed,
        Events.COUNTDOWN_STARTED: ui._on_countdown_changed,
        Events.COUNTDOWN_TICK: ui._on_countdown_changed,
        Events.COUNTDOWN_PAUSE_TOGGLED: ui._on_countdown_changed,
        Events.COUNTDOWN_CANCELLED: ui._on_countdown_changed,
        Events.COUNTDOWN_FINISHED: ui._on_countdown_finished,
        Events.TIMEZONES_UPDATED: ui._on_timezones_updated,
        Events.OPEN_COUNTDOWN_WINDOW: ui._on_open_countdown_window,
        Events.REMINDER_ADDED: ui._on_reminder_added,
        Events.REMINDER_UPDATED: ui._on_reminder_updated,
        Events.REMINDER_DELETED: ui._on_reminder_deleted,
        Events.HOURLY_WEB_UPDATED: ui._on_hourly_web_updated,
        Events.HOURLY_WEB_PAUSE_TOGGLED: ui._on_hourly_web_pause_toggled,
        Events.REMINDER_PAUSE_TOGGLED: ui._on_reminder_pause_toggled,
        Events.VACATION_TOGGLED: ui._on_vacation_toggled,
        Events.VACATION_SCHEDULE_ADDED: ui._on_vacation_schedule_added,
        Events.VACATION_SCHEDULE_DELETED: ui._on_vacation_schedule_deleted,
        Events.VACATION_SCHEDULE_UPDATED: ui._on_vacation_schedule_updated,
        Events.OPEN_REMINDER_WINDOW: ui._on_open_reminder_window,
        Events.OPEN_HOURLY_WEB_WINDOW: ui._on_open_hourly_web_window,
        Events.OPEN_VACATION_SCHEDULE_WINDOW: ui._on_open_vacation_schedule_window,
        Events.OPEN_CALENDAR_SYNC_WINDOW: ui._on_open_calendar_sync_window,
        Events.OPEN_TODO_WINDOW: ui._on_open_todo_window,
        Events.OPEN_NOTIFICATION_CENTER: ui._on_open_notification_center,
        Events.NOTIFICATIONS_CHANGED: ui._on_notifications_changed,
        Events.NOTIFICATIONS_RELEASED: ui._on_notifications_released,
        Events.TODO_UPDATED: ui._on_todo_updated,
        Events.TODO_DUE: ui._on_todo_due,
        Events.TODO_REMIND_TOGGLED: ui._on_todo_remind_toggled,
        Events.CALENDAR_EVENT_UPCOMING: ui._on_calendar_event_upcoming,
        Events.CALENDAR_EVENT_STARTED: ui._on_calendar_event_started,
        Events.CALENDAR_EVENT_ENDED: ui._on_calendar_event_ended,
        Events.SCREENSHOT_TRIGGERED: ui._on_screenshot_triggered,
    }
