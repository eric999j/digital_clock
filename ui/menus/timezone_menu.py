import tkinter as tk
from tkinter import Menu
from typing import TYPE_CHECKING

from services.timezone_service import TimezoneService

if TYPE_CHECKING:
    from ..main_window import DigitalClock


class TimezoneMenu(Menu):
    """多時區選單：勾選要顯示在時鐘下方的時區（最多 3 個）。"""

    def __init__(self, parent_menu: Menu, ui: 'DigitalClock', **kwargs):
        super().__init__(parent_menu, tearoff=0, **kwargs)
        self.ui = ui
        self.logic = ui.logic
        # tkinter 變數若被回收，對應的勾選狀態會消失，因此需持有參考
        self._vars: list[tk.BooleanVar] = []
        self.update_menu()

    def update_menu(self) -> None:
        """依目前選擇狀態重建選單；已達上限時，未勾選項目會停用。"""
        self.delete(0, tk.END)
        self._vars.clear()
        available, selected = self.logic.get_timezone_choices()

        if not available:
            self.add_command(label="(無可用時區資料)", state="disabled")
            return

        self.add_command(label=f"最多顯示 {TimezoneService.MAX_ZONES} 個", state="disabled")
        self.add_separator()

        at_limit = len(selected) >= TimezoneService.MAX_ZONES
        for key, label in available.items():
            is_selected = key in selected
            var = tk.BooleanVar(value=is_selected)
            self._vars.append(var)
            self.add_checkbutton(
                label=label,
                variable=var,
                command=lambda k=key: self.logic.toggle_timezone(k),
                state="disabled" if at_limit and not is_selected else "normal",
            )
