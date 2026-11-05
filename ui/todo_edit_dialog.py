"""待辦事項新增／編輯對話框。"""
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from core.todo_task import PRIORITIES, PRIORITY_HIGH, PRIORITY_LOW, PRIORITY_NORMAL, TodoTask, parse_date_input
from core.url_validator import is_safe_url
from ui.theme_utils import apply_themed_ttk_style, themed_error
from ui.window_bounds import clamp_position, get_screen_bounds

STYLE_PREFIX = 'Todo'
_PRIORITY_LABELS = ((PRIORITY_LOW, "低"), (PRIORITY_NORMAL, "普通"), (PRIORITY_HIGH, "高"))
_DATE_CHOICES = ("", "今天", "明天", "下週")


class TodoEditDialog(tk.Toplevel):
    """新增或編輯單一待辦；編輯時另提供完成狀態。"""

    def __init__(
        self,
        parent: tk.Misc,
        on_submit: Callable[[dict[str, Any]], None],
        theme: dict[str, str] | None = None,
        task: TodoTask | None = None,
        parent_text: str | None = None,
    ) -> None:
        """
        Args:
            parent: 上層視窗
            on_submit: 驗證通過後以欄位字典呼叫（text/project/priority/start_date/due_date/link[/is_done]）
            theme: 時鐘主題配色
            task: 編輯對象；None 表示新增
            parent_text: 新增子項時顯示的父項內容
        """
        super().__init__(parent)
        self._on_submit = on_submit
        self._task = task
        self.theme = theme or {'bg': '#F0F0F0', 'fg': '#000000'}
        self.transient(parent)
        if task is not None:
            self.title("編輯待辦")
        elif parent_text:
            self.title("新增子項")
        else:
            self.title("新增待辦")
        self.resizable(False, False)
        self.config(bg=self.theme['bg'])

        self._text_var = tk.StringVar(self, value=task.text if task else "")
        self._project_var = tk.StringVar(self, value=(task.project or "") if task else "")
        self._priority_var = tk.StringVar(self, value=task.priority if task else PRIORITY_NORMAL)
        self._start_var = tk.StringVar(self, value=task.start_date.isoformat() if task and task.start_date else "今天")
        self._due_var = tk.StringVar(self, value=task.due_date.isoformat() if task and task.due_date else "")
        self._link_var = tk.StringVar(self, value=(task.link or "") if task else "")
        self._done_var = tk.BooleanVar(self, value=task.is_done if task else False)

        apply_themed_ttk_style(STYLE_PREFIX, self.theme)
        self._create_widgets(parent_text)
        self._place_near(parent)
        self._text_entry.focus_set()

    def _create_widgets(self, parent_text: str | None) -> None:
        outer = ttk.Frame(self, padding="12", style=f'{STYLE_PREFIX}.TFrame')
        outer.pack(fill=tk.BOTH, expand=True)

        # 底部按鈕先 pack，確保永遠可見
        buttons = ttk.Frame(outer, style=f'{STYLE_PREFIX}.TFrame')
        buttons.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))
        ttk.Button(buttons, text="取消", command=self.destroy,
                   style=f'{STYLE_PREFIX}.TButton').pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(buttons, text="確定", command=self._submit,
                   style=f'{STYLE_PREFIX}.TButton').pack(side=tk.RIGHT)

        form = ttk.Frame(outer, style=f'{STYLE_PREFIX}.TFrame')
        form.pack(fill=tk.BOTH, expand=True)
        form.columnconfigure(1, weight=1)
        row = 0

        if parent_text:
            ttk.Label(form, text=f"父項：{parent_text}", style=f'{STYLE_PREFIX}.TLabel',
                      wraplength=360, justify=tk.LEFT).grid(row=row, column=0, columnspan=2, sticky='w', pady=(0, 6))
            row += 1

        def add_row(label: str, widget: tk.Widget) -> None:
            nonlocal row
            ttk.Label(form, text=label, style=f'{STYLE_PREFIX}.TLabel').grid(
                row=row, column=0, sticky='w', padx=(0, 8), pady=3)
            widget.grid(row=row, column=1, sticky='ew', pady=3)
            row += 1

        self._text_entry = ttk.Entry(form, textvariable=self._text_var, width=42, style=f'{STYLE_PREFIX}.TEntry')
        add_row("內容", self._text_entry)
        add_row("專案", ttk.Entry(form, textvariable=self._project_var, style=f'{STYLE_PREFIX}.TEntry'))

        priority_frame = ttk.Frame(form, style=f'{STYLE_PREFIX}.TFrame')
        for value, label in _PRIORITY_LABELS:
            ttk.Radiobutton(priority_frame, text=label, value=value, variable=self._priority_var,
                            style=f'{STYLE_PREFIX}.TRadiobutton').pack(side=tk.LEFT, padx=(0, 10))
        add_row("優先級", priority_frame)

        add_row("開始日", ttk.Combobox(form, textvariable=self._start_var, values=_DATE_CHOICES,
                                      style=f'{STYLE_PREFIX}.TCombobox'))
        add_row("截止日", ttk.Combobox(form, textvariable=self._due_var, values=_DATE_CHOICES,
                                      style=f'{STYLE_PREFIX}.TCombobox'))
        add_row("連結", ttk.Entry(form, textvariable=self._link_var, style=f'{STYLE_PREFIX}.TEntry'))

        if self._task is not None:
            ttk.Checkbutton(form, text="已完成", variable=self._done_var,
                            style=f'{STYLE_PREFIX}.TCheckbutton').grid(row=row, column=1, sticky='w', pady=3)

        self.bind('<Return>', lambda _e: self._submit())
        self.bind('<Escape>', lambda _e: self.destroy())

    def _place_near(self, parent: tk.Misc) -> None:
        """放在上層視窗附近並限制在可視範圍。"""
        self.update_idletasks()
        width, height = self.winfo_reqwidth(), self.winfo_reqheight()
        x, y = parent.winfo_rootx() + 40, parent.winfo_rooty() + 40
        x, y = clamp_position(x, y, width, height, get_screen_bounds(self))
        self.geometry(f"+{x}+{y}")

    def _collect(self) -> dict[str, Any]:
        """讀取並驗證欄位；不合法時拋出 ValueError（訊息可直接顯示給使用者）。"""
        text = self._text_var.get().strip()
        if not text:
            raise ValueError("請輸入待辦內容")
        start = parse_date_input(self._start_var.get())
        due = parse_date_input(self._due_var.get())
        if start and due and due < start:
            raise ValueError("截止日期不能早於開始日期")
        link = self._link_var.get().strip()
        if link and not is_safe_url(link):
            raise ValueError("連結僅支援 http / https 網址")
        priority = self._priority_var.get()
        values: dict[str, Any] = {
            'text': text,
            'project': self._project_var.get().strip() or None,
            'priority': priority if priority in PRIORITIES else PRIORITY_NORMAL,
            'start_date': start,
            'due_date': due,
            'link': link or None,
        }
        if self._task is not None:
            values['is_done'] = bool(self._done_var.get())
        return values

    def _submit(self) -> None:
        try:
            values = self._collect()
        except ValueError as e:
            themed_error(self, str(e), self.theme, title="輸入錯誤")
            return
        self.destroy()
        self._on_submit(values)
