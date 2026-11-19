"""暫停來源政策測試。"""
import unittest

from core.pause_policy import PausePolicy, PauseState


class TestPausePolicy(unittest.TestCase):
    def test_manual_pause_survives_vacation_release(self) -> None:
        state = PauseState(
            pause_sources={'reminder': {'manual', 'vacation'}, 'hourly_web': {'vacation'}},
            vacation_sources={'calendar'},
        )

        state.set_vacation_source('calendar', False)

        self.assertEqual(state.pause_sources['reminder'], {'manual'})
        self.assertEqual(state.pause_sources['hourly_web'], set())
        self.assertEqual(state.vacation_sources, set())

    def test_legacy_config_derives_manual_and_vacation_sources(self) -> None:
        state = PausePolicy.from_config({
            'reminder_paused': True,
            'hourly_web_reminder': {'paused': False},
            'on_vacation': True,
            'on_vacation_source': 'schedule',
            'vacation_previous_state': {'reminder_paused': True},
        })

        self.assertEqual(state.pause_sources['reminder'], {'manual', 'vacation'})
        self.assertEqual(state.pause_sources['hourly_web'], {'vacation'})
        self.assertEqual(state.vacation_sources, {'schedule'})


if __name__ == '__main__':
    unittest.main()
