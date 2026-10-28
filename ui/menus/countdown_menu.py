import tkinter as tk
from tkinter import Menu
from typing import TYPE_CHECKING

from services.countdown_service import CountdownService

if TYPE_CHECKING:
    from ..main_window import DigitalClock

# 快速倒數的預設分鐘數
QUICK_COUNTDOWN_MINUTES: tuple[int, ...] = (1, 3, 5, 10, 15, 30)


class CountdownMenu(Menu):
    """倒數計時選單：顯示狀態、暫停/取消，以及快速與自訂倒數。"""

    def __init__(self, parent_menu: Menu, ui: 'DigitalClock', **kwargs):
        super().__init__(parent_menu, tearoff=0, **kwargs)
        self.ui = ui
        self.logic = ui.logic
        self.update_menu()

    def update_menu(self) -> None:
        """依目前倒數狀態重建選單內容。"""
        self.delete(0, tk.END)
        snapshot = self.logic.countdown_service.snapshot()

        if snapshot["state"] != CountdownService.IDLE:
            resume = snapshot["state"] == CountdownService.PAUSED
            self.add_command(
                label="繼續" if resume else "暫停",
                command=self.logic.toggle_countdown_pause,
            )
            self.add_command(label="取消倒數", command=self.logic.cancel_countdown)
            self.add_separator()

        for minutes in QUICK_COUNTDOWN_MINUTES:
            self.add_command(
                label=f"{minutes} 分鐘",
                command=lambda m=minutes: self.logic.start_countdown(m * 60),
            )
        self.add_separator()
        self.add_command(label="自訂...", command=self.logic.open_countdown_window)
