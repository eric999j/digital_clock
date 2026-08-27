"""休假模式 cascade 選單：立即切換 + 排程管理。"""
import tkinter as tk
from datetime import date
from tkinter import Menu
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..main_window import DigitalClock


_MENU_LABEL_MAX_CHARS = 42


def _truncate(text: str, limit: int = _MENU_LABEL_MAX_CHARS) -> str:
    weight = 0
    out: list[str] = []
    for ch in text:
        step = 2 if ord(ch) > 127 else 1
        if weight + step > limit:
            out.append('…')
            return ''.join(out)
        out.append(ch)
        weight += step
    return ''.join(out)


class VacationMenu(Menu):
    """休假模式選單：包含立即切換、新增排程、既有排程列表。"""

    def __init__(self, parent_menu: Menu, ui: 'DigitalClock', **kwargs):
        super().__init__(parent_menu, tearoff=0, **kwargs)
        self.ui = ui
        self.logic = ui.logic
        self.update_menu()

    def update_menu(self) -> None:
        """重建選單內容以反映目前狀態。"""
        self.delete(0, tk.END)

        toggle_label = "結束休假" if self.logic.is_on_vacation() else "立即開始休假"
        self.add_command(label=toggle_label, command=self.logic.toggle_vacation)

        self.add_separator()
        self.add_command(label="新增休假排程...", command=self.logic.open_vacation_schedule_window)
        self.add_separator()

        schedules = self.logic.list_vacation_schedules()

        # 過濾出仍有效的排程（end >= today），比照週期提醒的顯示策略
        today = date.today()
        upcoming: list[dict[str, Any]] = []
        for schedule in schedules:
            end_str = schedule.get('end')
            try:
                end_date = date.fromisoformat(str(end_str))
            except (TypeError, ValueError):
                continue
            if end_date >= today:
                upcoming.append(schedule)

        upcoming.sort(key=lambda s: (s.get('start', ''), s.get('end', '')))

        if not upcoming:
            self.add_command(label="(無排程休假)", state="disabled")
            return

        for schedule in upcoming:
            self.add_cascade(label=_truncate(self._format_label(schedule)), menu=self._build_item_menu(schedule))

    def _build_item_menu(self, schedule: dict[str, Any]) -> Menu:
        """建立單筆排程的子選單（刪除操作）。"""
        item_menu = Menu(self, tearoff=0)
        self.ui._update_menu_colors(item_menu)
        item_menu.add_command(
            label="刪除",
            command=lambda s=schedule: self.ui._confirm_delete_vacation_schedule(s),
        )
        return item_menu

    @staticmethod
    def _format_label(schedule: dict[str, Any]) -> str:
        """格式化排程顯示文字：`[MM-DD ~ MM-DD] 備註`。"""
        start = str(schedule.get('start', ''))
        end = str(schedule.get('end', ''))
        # 去掉年份保持簡潔，若解析失敗則回退為原字串
        start_short = start[5:] if len(start) >= 10 else start
        end_short = end[5:] if len(end) >= 10 else end
        note = str(schedule.get('note', '')).strip()
        base = f"[{start_short} ~ {end_short}]"
        return f"{base} {note}" if note else base
