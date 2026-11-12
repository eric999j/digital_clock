"""AppState 跨模組狀態與 NotificationCenter 統一通知中心測試，並驗證兩者在 ClockLogic 派發下協同運作。"""
import unittest
from datetime import datetime
from unittest.mock import MagicMock

from core.app_state import AppState, AppStateSnapshot
from core.clock_logic import ClockLogic
from core.events import Events
from core.observer import Observer
from services.notification_center import (
    SOURCE_CALENDAR,
    SOURCE_COUNTDOWN,
    SOURCE_POMODORO,
    SOURCE_REMINDER,
    SOURCE_TODO,
    NotificationCenter,
)


class TestAppState(unittest.TestCase):
    def setUp(self) -> None:
        self.notify = MagicMock()
        self.state = AppState(self.notify)

    def test_defaults_are_idle(self) -> None:
        self.assertEqual(self.state.snapshot, AppStateSnapshot())
        self.assertFalse(self.state.snapshot.is_quiet)

    def test_pomodoro_focus_is_quiet_until_paused_or_stopped(self) -> None:
        self.state.update(Events.POMODORO_PHASE_CHANGE, "FOCUS")
        self.assertTrue(self.state.snapshot.is_focusing)
        self.assertTrue(self.state.snapshot.is_quiet)
        self.state.update(Events.POMODORO_PAUSE_TOGGLED, True)
        self.assertFalse(self.state.snapshot.is_quiet)
        self.state.update(Events.POMODORO_PAUSE_TOGGLED, False)
        self.state.update(Events.POMODORO_PHASE_CHANGE, "IDLE")
        self.assertFalse(self.state.snapshot.is_quiet)

    def test_countdown_lifecycle(self) -> None:
        self.state.update(Events.COUNTDOWN_STARTED, 60, "x")
        self.assertTrue(self.state.snapshot.countdown_active)
        self.state.update(Events.COUNTDOWN_PAUSE_TOGGLED, True, 30, "x")
        self.assertTrue(self.state.snapshot.countdown_paused)
        self.state.update(Events.COUNTDOWN_FINISHED, "x", 60)
        self.assertEqual((self.state.snapshot.countdown_active, self.state.snapshot.countdown_paused),
                         (False, False))

    def test_vacation_pause_todo_and_meeting(self) -> None:
        self.state.update(Events.VACATION_TOGGLED, True)
        self.state.update(Events.REMINDER_PAUSE_TOGGLED, True)
        self.state.update(Events.HOURLY_WEB_PAUSE_TOGGLED, True)
        self.state.update(Events.TODO_UPDATED, 4)
        self.state.update(Events.CALENDAR_EVENT_STARTED, "會議")
        snap = self.state.snapshot
        self.assertEqual((snap.on_vacation, snap.reminders_paused, snap.hourly_web_paused, snap.todo_pending,
                          snap.in_meeting), (True, True, True, 4, True))
        self.state.update(Events.CALENDAR_EVENT_ENDED)
        self.assertFalse(self.state.snapshot.in_meeting)

    def test_notifies_only_when_snapshot_changes(self) -> None:
        self.state.update(Events.TODO_UPDATED, 2)
        self.state.update(Events.TODO_UPDATED, 2)
        self.state.update(Events.POMODORO_TICK, "FOCUS", 10)
        self.state.update(Events.APP_STATE_CHANGED, self.state.snapshot)
        self.notify.assert_called_once()
        self.assertEqual(self.notify.call_args.args[0], Events.APP_STATE_CHANGED)
        self.assertEqual(self.notify.call_args.args[1].todo_pending, 2)

    def test_ignores_bad_todo_payload(self) -> None:
        self.state.update(Events.TODO_UPDATED, True)
        self.state.update(Events.TODO_UPDATED)
        self.assertEqual(self.state.snapshot.todo_pending, 0)

    def test_sync_seeds_initial_state(self) -> None:
        self.state.sync(on_vacation=True, todo_pending=3)
        self.assertTrue(self.state.snapshot.on_vacation)
        self.assertEqual(self.state.snapshot.todo_pending, 3)


class TestNotificationCenter(unittest.TestCase):
    def setUp(self) -> None:
        self.notify = MagicMock()
        self.now = datetime(2026, 11, 12, 9, 0, 0)
        self.center = NotificationCenter(self.notify, max_items=3, clock=lambda: self.now)

    def test_collects_all_four_module_sources(self) -> None:
        self.center.update(Events.POMODORO_PHASE_COMPLETE, "SHORT_BREAK")
        self.center.update(Events.REMINDER_DUE, {'title': '喝水', 'message': ''})
        self.center.update(Events.TODO_DUE, [{'status': 'overdue', 'text': '秘密'}, {'status': 'today'}])
        self.center.update(Events.CALENDAR_EVENT_UPCOMING, "週會", 5)
        items = self.center.items()
        self.assertEqual([i.source for i in items], [SOURCE_CALENDAR, SOURCE_TODO, SOURCE_REMINDER, SOURCE_POMODORO]
                         [:3])  # max_items=3 丟棄最舊
        self.assertIn("5 分鐘", items[0].message)
        self.assertEqual(items[1].message, "逾期 1 項、今日到期 1 項")
        self.assertNotIn("秘密", items[1].message)  # 待辦文字不進通知中心

    def test_countdown_and_pomodoro_text(self) -> None:
        self.center.update(Events.POMODORO_PHASE_COMPLETE, "FOCUS")
        self.center.update(Events.COUNTDOWN_FINISHED, "泡麵", 180)
        countdown, pomodoro = self.center.items()
        self.assertEqual(countdown.source, SOURCE_COUNTDOWN)
        self.assertIn("泡麵", countdown.message)
        self.assertEqual(pomodoro.source, SOURCE_POMODORO)
        self.assertIn("專注", pomodoro.message)

    def test_unread_and_mark_read_and_clear(self) -> None:
        self.center.update(Events.REMINDER_DUE, {'title': 'a'})
        self.center.update(Events.REMINDER_DUE, {'title': 'b'})
        self.assertEqual(self.center.unread_count(), 2)
        self.notify.reset_mock()
        self.center.mark_all_read()
        self.notify.assert_called_once_with(Events.NOTIFICATIONS_CHANGED, 0)
        self.notify.reset_mock()
        self.center.mark_all_read()  # 已全讀：不重複通知
        self.notify.assert_not_called()
        self.center.clear()
        self.assertEqual(self.center.items(), [])

    def test_emits_added_and_changed_and_ignores_other_events(self) -> None:
        self.center.update(Events.TODO_UPDATED, 5)
        self.center.update(Events.NOTIFICATION_ADDED, object())
        self.notify.assert_not_called()
        self.center.update(Events.COUNTDOWN_FINISHED, "", 10)
        events = [c.args[0] for c in self.notify.call_args_list]
        self.assertEqual(events, [Events.NOTIFICATION_ADDED, Events.NOTIFICATIONS_CHANGED])

    def test_source_filter_and_history_cap(self) -> None:
        for i in range(5):
            self.center.update(Events.REMINDER_DUE, {'title': str(i)})
        self.assertEqual([i.title for i in self.center.items(SOURCE_REMINDER)], ["4", "3", "2"])
        self.assertEqual(self.center.items(SOURCE_TODO), [])


class _Recorder(Observer):
    def __init__(self) -> None:
        self.events: list[str] = []

    def update(self, event, *args, **kwargs) -> None:
        self.events.append(event)


class TestClockLogicIntegration(unittest.TestCase):
    def _logic(self) -> ClockLogic:
        logic = ClockLogic.__new__(ClockLogic)
        logic._observers = []
        logic.app_state = AppState(logic.notify_observers)
        logic.notification_center = NotificationCenter(logic.notify_observers)
        logic.add_observer(logic.app_state)
        logic.add_observer(logic.notification_center)
        return logic

    def test_one_event_updates_state_and_center_without_loops(self) -> None:
        logic = self._logic()
        recorder = _Recorder()
        logic.add_observer(recorder)

        logic.notify_observers(Events.CALENDAR_EVENT_STARTED, "週會")

        self.assertTrue(logic.app_state.snapshot.in_meeting)
        self.assertEqual(logic.notification_center.items()[0].source, SOURCE_CALENDAR)
        self.assertEqual(recorder.events.count(Events.APP_STATE_CHANGED), 1)
        self.assertEqual(recorder.events.count(Events.NOTIFICATION_ADDED), 1)
        self.assertEqual(recorder.events.count(Events.NOTIFICATIONS_CHANGED), 1)

    def test_open_notification_center_dispatches_event(self) -> None:
        logic = self._logic()
        recorder = _Recorder()
        logic.add_observer(recorder)
        logic.open_notification_center()
        self.assertEqual(recorder.events, [Events.OPEN_NOTIFICATION_CENTER])


if __name__ == '__main__':
    unittest.main()
