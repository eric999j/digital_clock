import unittest

from services.pomodoro_service import PomodoroService


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestPomodoroService(unittest.TestCase):
    def setUp(self):
        self.config = {
            "focus_minutes": 25,
            "short_break": 5,
            "long_break": 15,
            "cycles_before_long_break": 4
        }
        self.callbacks = {} # Mock callbacks if needed
        self.clock = FakeClock()
        self.service = PomodoroService(lambda: self.config, self.callbacks, clock=self.clock)

    def test_initial_state(self):
        self.assertEqual(self.service.phase, "IDLE")
        self.assertEqual(self.service.remaining_seconds, 0)

    def test_start_focus(self):
        self.service.start_focus()
        self.assertEqual(self.service.phase, "FOCUS")
        self.assertEqual(self.service.remaining_seconds, 25 * 60)

    def test_tick(self):
        self.service.start_focus()
        initial_seconds = self.service.remaining_seconds

        self.clock.advance(1)
        self.service.tick()
        self.assertEqual(self.service.remaining_seconds, initial_seconds - 1)

    def test_tick_does_not_emit_negative_remaining_seconds(self):
        ticks = []
        self.service.callbacks = {'on_tick': lambda phase, remaining: ticks.append(remaining)}
        self.service.start_focus()
        self.clock.advance(25 * 60 + 30)  # 超過截止時間

        self.service.tick()

        self.assertEqual(ticks, [0])
        self.assertGreaterEqual(self.service.remaining_seconds, 0)

    def test_skipped_ticks_do_not_cause_drift(self):
        self.service.start_focus()
        self.clock.advance(30)  # 主迴圈卡住 30 秒，期間沒有任何 tick
        self.service.tick()
        self.assertEqual(self.service.remaining_seconds, 25 * 60 - 30)

    def test_long_suspend_advances_only_one_phase(self):
        phases = []
        self.service.callbacks = {'on_phase_change': phases.append}
        self.service.start_focus()
        self.clock.advance(3 * 3600)  # 睡眠後喚醒
        self.service.tick()

        self.assertEqual(phases, ["FOCUS", "SHORT_BREAK"])
        self.assertEqual(self.service.remaining_seconds, 5 * 60)

    def test_phase_completion_cycle(self):
        completed = []
        self.service.callbacks = {'on_complete': completed.append}
        self.service.start_focus()
        self.clock.advance(25 * 60)
        self.service.tick()

        self.assertEqual(self.service.current_cycle, 1)
        self.assertEqual(self.service.phase, "SHORT_BREAK")
        self.assertEqual(completed, ["SHORT_BREAK"])

    def test_pause_freezes_remaining_and_resume_continues(self):
        toggles = []
        self.service.callbacks = {'on_pause_toggle': toggles.append}
        self.service.start_focus()
        self.clock.advance(60)
        self.service.pause()

        self.clock.advance(600)  # 暫停期間的時間不計
        self.service.tick()
        self.assertTrue(self.service.is_paused)
        self.assertEqual(self.service.remaining_seconds, 24 * 60)
        self.assertEqual(self.service.phase, "FOCUS")

        self.service.resume()
        self.clock.advance(30)
        self.assertEqual(self.service.remaining_seconds, 24 * 60 - 30)
        self.assertEqual(toggles, [True, False])

    def test_pause_does_nothing_when_idle_or_already_paused(self):
        toggles = []
        self.service.callbacks = {'on_pause_toggle': toggles.append}
        self.service.pause()
        self.service.resume()
        self.service.start_focus()
        self.service.pause()
        self.service.pause()
        self.assertEqual(toggles, [True])

    def test_stop_and_restart_clear_pause(self):
        self.service.start_focus()
        self.service.pause()
        self.service.start_focus()
        self.assertFalse(self.service.is_paused)

        self.service.pause()
        self.service.stop()
        self.assertFalse(self.service.is_paused)
        self.assertEqual(self.service.remaining_seconds, 0)

    def test_stop_resets_to_idle(self):
        self.service.start_focus()
        self.service.stop()
        self.assertEqual((self.service.phase, self.service.remaining_seconds), ("IDLE", 0))
        self.clock.advance(10)
        self.service.tick()  # 閒置時 tick 不做事
        self.assertEqual(self.service.phase, "IDLE")

    def test_start_break_short(self):
        self.service.current_cycle = 1
        self.service.start_break()
        self.assertEqual(self.service.phase, "SHORT_BREAK")
        self.assertEqual(self.service.remaining_seconds, 5 * 60)

    def test_start_break_long(self):
        self.service.current_cycle = 4 # cycles_before_long_break
        self.service.start_break()
        self.assertEqual(self.service.phase, "LONG_BREAK")
        self.assertEqual(self.service.remaining_seconds, 15 * 60)

if __name__ == '__main__':
    unittest.main()
