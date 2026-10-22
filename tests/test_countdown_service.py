import unittest
from unittest.mock import MagicMock

from core.events import Events
from services.countdown_service import CountdownService


class FakeClock:
    """可手動推進的單調時鐘。"""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestCountdownService(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.notify = MagicMock()
        self.service = CountdownService(self.notify, clock=self.clock)

    def _events(self):
        return [call.args[0] for call in self.notify.call_args_list]

    def test_start_sets_running_state_and_notifies(self):
        self.service.start(90, "  泡麵  ")

        self.assertTrue(self.service.is_active)
        self.assertEqual(self.service.state, CountdownService.RUNNING)
        self.assertEqual(self.service.label, "泡麵")
        self.assertEqual(self.service.remaining_seconds(), 90)
        self.notify.assert_called_once_with(Events.COUNTDOWN_STARTED, 90, "泡麵")

    def test_start_rejects_invalid_seconds(self):
        for bad in (0, -5, CountdownService.MAX_SECONDS + 1, 1.5, "10", True):
            with self.subTest(seconds=bad), self.assertRaises(ValueError):
                self.service.start(bad)
        self.assertFalse(self.service.is_active)
        self.notify.assert_not_called()

    def test_label_is_truncated(self):
        self.service.start(10, "x" * 100)
        self.assertEqual(len(self.service.label), CountdownService.MAX_LABEL_LENGTH)

    def test_tick_reports_only_when_second_changes(self):
        self.service.start(10)
        self.notify.reset_mock()

        self.service.tick()
        self.notify.assert_not_called()

        self.clock.advance(1)
        self.service.tick()
        self.service.tick()
        self.notify.assert_called_once_with(Events.COUNTDOWN_TICK, 9, "")

    def test_remaining_uses_ceiling_so_zero_means_finished(self):
        self.service.start(5)
        self.clock.advance(4.2)
        self.assertEqual(self.service.remaining_seconds(), 1)

    def test_finish_emits_event_and_returns_to_idle(self):
        self.service.start(3, "泡麵")
        self.notify.reset_mock()

        self.clock.advance(3)
        self.service.tick()

        self.notify.assert_called_once_with(Events.COUNTDOWN_FINISHED, "泡麵", 3)
        self.assertFalse(self.service.is_active)
        self.assertEqual(self.service.remaining_seconds(), 0)

        # 結束後再 tick 不應重複通知
        self.service.tick()
        self.assertEqual(self.notify.call_count, 1)

    def test_late_tick_still_finishes_once(self):
        self.service.start(3)
        self.notify.reset_mock()
        self.clock.advance(30)
        self.service.tick()
        self.assertEqual(self._events(), [Events.COUNTDOWN_FINISHED])

    def test_pause_freezes_remaining_time(self):
        self.service.start(60)
        self.clock.advance(10)
        self.service.pause()

        self.assertTrue(self.service.is_paused)
        self.clock.advance(500)
        self.assertEqual(self.service.remaining_seconds(), 50)

        self.service.tick()  # 暫停中不會觸發結束或 TICK
        self.assertNotIn(Events.COUNTDOWN_FINISHED, self._events())

    def test_resume_continues_from_paused_remaining(self):
        self.service.start(60)
        self.clock.advance(10)
        self.service.pause()
        self.clock.advance(500)
        self.service.resume()

        self.assertEqual(self.service.state, CountdownService.RUNNING)
        self.clock.advance(20)
        self.assertEqual(self.service.remaining_seconds(), 30)

    def test_toggle_pause_switches_between_states(self):
        self.service.start(60)
        self.service.toggle_pause()
        self.assertTrue(self.service.is_paused)
        self.service.toggle_pause()
        self.assertEqual(self.service.state, CountdownService.RUNNING)

        paused_events = [c for c in self.notify.call_args_list if c.args[0] == Events.COUNTDOWN_PAUSE_TOGGLED]
        self.assertEqual([c.args[1] for c in paused_events], [True, False])

    def test_pause_resume_are_noops_in_wrong_state(self):
        self.service.pause()
        self.service.resume()
        self.notify.assert_not_called()

        self.service.start(10)
        self.notify.reset_mock()
        self.service.resume()  # 執行中不能 resume
        self.notify.assert_not_called()

    def test_cancel_resets_and_notifies_once(self):
        self.service.start(60, "測試")
        self.notify.reset_mock()

        self.service.cancel()
        self.service.cancel()

        self.notify.assert_called_once_with(Events.COUNTDOWN_CANCELLED, "測試")
        self.assertFalse(self.service.is_active)
        self.assertEqual(self.service.label, "")

    def test_cancel_works_while_paused(self):
        self.service.start(60)
        self.service.pause()
        self.service.cancel()
        self.assertFalse(self.service.is_active)

    def test_start_replaces_running_countdown(self):
        self.service.start(60, "A")
        self.clock.advance(30)
        self.service.start(10, "B")

        self.assertEqual(self.service.label, "B")
        self.assertEqual(self.service.remaining_seconds(), 10)

    def test_format_remaining(self):
        fmt = CountdownService.format_remaining
        self.assertEqual(fmt(0), "00:00")
        self.assertEqual(fmt(65), "01:05")
        self.assertEqual(fmt(3600), "1:00:00")
        self.assertEqual(fmt(3725), "1:02:05")
        self.assertEqual(fmt(-4), "00:00")

    def test_snapshot(self):
        self.service.start(120, "X")
        self.clock.advance(20)
        self.assertEqual(
            self.service.snapshot(),
            {"state": CountdownService.RUNNING, "label": "X", "remaining": 100, "total": 120},
        )


if __name__ == "__main__":
    unittest.main()
