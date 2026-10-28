import tkinter as tk
from tkinter import Menu
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main_window import DigitalClock


class PomodoroMenu(Menu):
    """番茄鐘選單：進行中時提供暫停/繼續與取消，並可隨時（重新）開始專注。"""

    def __init__(self, parent_menu: Menu, ui: 'DigitalClock', **kwargs):
        super().__init__(parent_menu, tearoff=0, **kwargs)
        self.ui = ui
        self.logic = ui.logic
        self.update_menu()

    def update_menu(self) -> None:
        """依目前番茄鐘狀態重建選單內容。"""
        self.delete(0, tk.END)
        pomodoro = self.logic.pomodoro

        if pomodoro.phase != "IDLE":
            self.add_command(
                label="繼續" if pomodoro.is_paused else "暫停",
                command=pomodoro.toggle_pause,
            )
            self.add_command(label="取消番茄鐘", command=pomodoro.stop)
            self.add_separator()

        self.add_command(label="開始專注", command=pomodoro.start_focus)
