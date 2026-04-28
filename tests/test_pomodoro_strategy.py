import unittest

from strategies.pomodoro_strategy import PomodoroStrategy


class TestPomodoroStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = PomodoroStrategy()
        self.config = {
            'cycles_before_long_break': 4,
        }

    # --- next_phase ---

    def test_focus_to_short_break(self):
        result = self.strategy.next_phase('FOCUS', current_cycle=0, config=self.config)
        self.assertEqual(result, 'SHORT_BREAK')

    def test_focus_to_long_break_at_cycle_boundary(self):
        result = self.strategy.next_phase('FOCUS', current_cycle=3, config=self.config)
        self.assertEqual(result, 'LONG_BREAK')

    def test_focus_to_long_break_at_multiple_of_cycles(self):
        result = self.strategy.next_phase('FOCUS', current_cycle=7, config=self.config)
        self.assertEqual(result, 'LONG_BREAK')

    def test_short_break_to_focus(self):
        result = self.strategy.next_phase('SHORT_BREAK', current_cycle=1, config=self.config)
        self.assertEqual(result, 'FOCUS')

    def test_long_break_to_focus(self):
        result = self.strategy.next_phase('LONG_BREAK', current_cycle=4, config=self.config)
        self.assertEqual(result, 'FOCUS')

    def test_custom_cycles_before_long_break(self):
        config = {'cycles_before_long_break': 2}
        result = self.strategy.next_phase('FOCUS', current_cycle=1, config=config)
        self.assertEqual(result, 'LONG_BREAK')

    def test_default_cycles_when_missing_from_config(self):
        result = self.strategy.next_phase('FOCUS', current_cycle=3, config={})
        self.assertEqual(result, 'LONG_BREAK')

    # --- 介面合規：PomodoroStrategy 為 PhaseStrategy，沒有 check 方法 ---

    def test_no_check_method(self):
        self.assertFalse(hasattr(self.strategy, 'check'))


if __name__ == '__main__':
    unittest.main()
