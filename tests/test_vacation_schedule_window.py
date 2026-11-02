import tkinter as tk
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock

from ui.vacation_schedule_window import VacationScheduleWindow


class TestVacationScheduleWindowSingleDay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as e:
            raise unittest.SkipTest(f"無可用顯示器: {e}") from e
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def _open(self, **kwargs) -> VacationScheduleWindow:
        window = VacationScheduleWindow(self.root, MagicMock(), None, **kwargs)
        self.addCleanup(lambda: window.winfo_exists() and window.destroy())
        window._show_error = MagicMock()
        return window

    def _set_start(self, window: VacationScheduleWindow, day: date) -> None:
        window.start_year_var.set(str(day.year))
        window.start_month_var.set(f"{day.month:02d}")
        window.start_day_var.set(f"{day.day:02d}")

    def test_single_day_hides_end_date_and_submits_same_day(self):
        window = self._open()
        window.update_idletasks()
        self.assertTrue(window._end_frame.winfo_manager())

        target = date.today() + timedelta(days=3)
        self._set_start(window, target)
        window.single_day_var.set(True)
        window._on_single_day_toggled()
        self.assertFalse(window._end_frame.winfo_manager())

        window.note_entry.insert(0, '請假')
        window._on_submit()
        window.callback.assert_called_once_with(target.isoformat(), target.isoformat(), '請假')

    def test_unchecking_single_day_restores_end_date(self):
        window = self._open()
        window.single_day_var.set(True)
        window._on_single_day_toggled()
        window.single_day_var.set(False)
        window._on_single_day_toggled()
        self.assertTrue(window._end_frame.winfo_manager())

    def test_range_mode_still_validates_end_date(self):
        window = self._open()
        start = date.today() + timedelta(days=5)
        self._set_start(window, start)
        end = start - timedelta(days=1)
        window.end_year_var.set(str(end.year))
        window.end_month_var.set(f"{end.month:02d}")
        window.end_day_var.set(f"{end.day:02d}")
        window._on_submit()
        window.callback.assert_not_called()
        window._show_error.assert_called_once()

    def test_single_day_in_the_past_is_rejected(self):
        window = self._open()
        self._set_start(window, date.today() - timedelta(days=1))
        window.single_day_var.set(True)
        window._on_submit()
        window.callback.assert_not_called()
        self.assertIn('日期不可早於今天', window._show_error.call_args.args[0])

    def test_editing_same_day_schedule_defaults_to_single_day(self):
        day = (date.today() + timedelta(days=2)).isoformat()
        window = self._open(schedule_to_edit={'start': day, 'end': day, 'note': ''})
        self.assertTrue(window.single_day_var.get())
        other = self._open(schedule_to_edit={'start': day, 'end': (date.today() + timedelta(days=4)).isoformat()})
        self.assertFalse(other.single_day_var.get())


if __name__ == '__main__':
    unittest.main()
