import tkinter as tk
from datetime import datetime
from tkinter import Menu
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main_window import DigitalClock


_MENU_LABEL_MAX_CHARS = 42


def _truncate(text: str, limit: int = _MENU_LABEL_MAX_CHARS) -> str:
    """依中英文字寬粗略截斷選單標籤（中文字算 2 單位）避免撐爆選單。"""
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


class ReminderMenu(Menu):
    """提醒選單。"""

    def __init__(self, parent_menu: Menu, ui: 'DigitalClock', **kwargs):
        super().__init__(parent_menu, tearoff=0, **kwargs)
        self.ui = ui
        self.logic = ui.logic
        self.update_menu()

    def update_menu(self) -> None:
        """更新提醒選單內容。"""
        self.delete(0, tk.END)
        self.add_command(label="新增提醒...", command=self.logic.open_reminder_window)

        # 加入暫停/啟動按鈕
        pause_label = "啟動" if self.logic.is_reminder_paused() else "暫停"
        self.add_command(label=pause_label, command=self.logic.toggle_reminder_pause)

        self.add_separator()

        # 重新載入設定以確保獲取最新的提醒清單
        _fresh = self.ui.logic.get_config()
        now = datetime.now()
        reminders = _fresh.get('reminders', [])

        # 過濾掉過期的單次提醒
        active_reminders = []
        for r in reminders:
            if r.get('weekdays'):
                active_reminders.append(r)
            elif 'datetime' in r:
                try:
                    if datetime.strptime(r['datetime'], '%Y-%m-%d %H:%M:%S') > now:
                        active_reminders.append(r)
                except ValueError:
                    continue

        if not active_reminders:
            self.add_command(label="(無待辦提醒)", state="disabled")
        else:
            # 排序：單次提醒在前，週期提醒在後
            sorted_reminders = sorted(
                active_reminders,
                key=lambda r: (
                    0 if 'datetime' in r else 1,
                    r.get('datetime', 'z'),
                    r.get('time', 'z')
                )
            )

            for r in sorted_reminders:
                # 優先使用標題，若無標題才使用內容
                display_text = r.get('title', '').strip() or r.get('message', '') or '(未命名提醒)'

                if r.get('weekdays'):
                    weekdays_str = "".join([d.replace('週', '') for d in r['weekdays']])
                    label = f"[每週{weekdays_str}] {r['time']} {display_text}"
                else:
                    dt_str = r['datetime'][5:-3] # 去掉年份和秒
                    label = f"[{dt_str}] {display_text}"

                # 建立子選單來提供編輯與刪除功能
                item_menu = Menu(self, tearoff=0)
                self.ui._update_menu_colors(item_menu)
                item_menu.add_command(label="編輯", command=lambda x=r: self.logic.open_reminder_window(x))
                item_menu.add_command(label="刪除", command=lambda x=r: self.ui._confirm_delete_reminder(x))

                self.add_cascade(label=_truncate(label), menu=item_menu)
