"""待辦事項視窗：樹狀清單、搜尋篩選、拖曳排序、復原／重做、匯入匯出。"""
import logging
import time
import tkinter as tk
import webbrowser
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, ttk
from tkinter import font as tkfont
from typing import Any

from core.todo_commands import (
    POSITION_AFTER,
    POSITION_BEFORE,
    POSITION_INTO,
    POSITION_PROMOTE,
    POSITION_ROOT,
)
from core.todo_filter import FILTER_ALL, FILTER_MODES, TodoFilter, TodoNode
from core.todo_task import PRIORITY_HIGH, PRIORITY_LOW, TodoTask
from core.url_validator import is_safe_url
from services.todo_service import TodoService
from ui.theme_utils import (
    BUTTON_FG,
    BUTTON_HOVER_BG,
    BUTTON_PRESSED_BG,
    apply_themed_ttk_style,
    is_dark_theme,
    shift_color,
    themed_confirm,
    themed_error,
)
from ui.todo_edit_dialog import STYLE_PREFIX, TodoEditDialog

logger = logging.getLogger(__name__)

_PRIORITY_TEXT = {PRIORITY_LOW: "低", PRIORITY_HIGH: "高"}
_DONE_MARK, _OPEN_MARK = "☑", "☐"
_DRAG_THRESHOLD_PX = 8
_PROMOTE_DRAG_PX = 20
_DUE_SOON_DAYS = 3
_MIN_SIZE = (620, 400)
_TREE_COLUMN_MIN = 160
_SHIFT_MASK, _CONTROL_MASK = 0x1, 0x4
_LINK_REOPEN_GUARD_SEC = 0.5
# 表頭沿用按鈕的中性灰底黑字，不隨時鐘主題變化
_HEADER_BG = BUTTON_HOVER_BG
_HEADER_FG = BUTTON_FG
_HEADER_GAP = BUTTON_PRESSED_BG

# 深淺主題各自的標記色；其餘顏色由時鐘主題的 bg/fg 衍生
_LIGHT_ACCENTS = {
    'link': '#0064d0', 'high': '#c0392b', 'low': '#2e8b57', 'done': '#888888',
    'overdue': '#ffe1e1', 'today': '#fff4c9', 'soon': '#fff9df', 'drop': '#cfe8ff',
}
_DARK_ACCENTS = {
    'link': '#5ea9ff', 'high': '#ff9a92', 'low': '#7ee787', 'done': '#8a8a8a',
    'overdue': '#5c2a2a', 'today': '#5c4b1f', 'soon': '#4a4426', 'drop': '#264f78',
}


def format_short_date(value: date | None, today: date) -> str:
    """MM/DD；非當年度顯示 YYYY/MM/DD；None 為空字串。"""
    if value is None:
        return ""
    return value.strftime("%m/%d") if value.year == today.year else value.strftime("%Y/%m/%d")


class TodoWindow(tk.Toplevel):
    """待辦事項視窗；配色完全跟隨數位時鐘主題。"""

    def __init__(
        self,
        parent: tk.Misc,
        service: TodoService,
        theme: dict[str, str] | None = None,
        geometry: str = "760x560",
        on_close: Callable[[str], None] | None = None,
    ) -> None:
        """
        Args:
            parent: 主時鐘視窗
            service: 待辦服務
            theme: 時鐘目前的主題配色
            geometry: 視窗大小（WxH）
            on_close: 關閉時以「WxH」呼叫，供儲存視窗大小
        """
        super().__init__(parent)
        self.service = service
        self.theme = theme or {'bg': '#F0F0F0', 'fg': '#000000'}
        self._on_close = on_close
        self._collapsed: set[str] = set()
        self._filter_modes = dict(FILTER_MODES)
        self._filter_labels = {label: mode for mode, label in FILTER_MODES}
        self._search_after_id: str | None = None
        self._drag: dict[str, Any] | None = None
        self._drop_item: str | None = None
        self._last_link_open: float = float('-inf')
        self._drop_saved_tags: tuple[str, ...] = ()
        self._fonts: dict[tuple[bool, bool, bool], tkfont.Font] = {}

        self.transient(parent)
        self.title("待辦事項")
        self.geometry(geometry)
        self.minsize(*_MIN_SIZE)
        # 不使用 grab_set，讓主時鐘仍可接收拖曳事件
        self.protocol("WM_DELETE_WINDOW", self.close)

        self._filter_var = tk.StringVar(self, value=self._filter_modes[FILTER_ALL])
        self._search_var = tk.StringVar(self)
        self._entry_var = tk.StringVar(self)
        self._status_var = tk.StringVar(self)
        self._stats_var = tk.StringVar(self)

        try:
            self._create_widgets()
            self._create_menu()
            self._bind_keys()
            self._apply_colors()
            self.refresh()
        except Exception as e:
            logger.error("Error building todo window: %s", e)
            themed_error(parent, f"無法建立待辦視窗：{e}", self.theme, title="錯誤")
            self.destroy()

    # ---- 版面 ----

    def _create_widgets(self) -> None:
        p = STYLE_PREFIX
        outer = ttk.Frame(self, padding="10", style=f'{p}.TFrame')
        outer.pack(fill=tk.BOTH, expand=True)

        # 底部元件先 pack，確保永遠可見
        status_bar = ttk.Frame(outer, style=f'{p}.TFrame')
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(6, 0))
        ttk.Label(status_bar, textvariable=self._status_var, style=f'{p}.TLabel').pack(side=tk.LEFT)
        ttk.Label(status_bar, textvariable=self._stats_var, style=f'{p}.TLabel').pack(side=tk.RIGHT)

        ttk.Label(
            outer,
            text="Ctrl+N 新增｜Ctrl+F 搜尋｜F2 編輯｜Space 完成｜Del 刪除｜Ctrl+Z/Y 復原/重做｜拖曳調整順序與階層（左拖提升一層）",
            style=f'{p}.TLabel', wraplength=720, justify=tk.LEFT,
        ).pack(fill=tk.X, side=tk.BOTTOM, pady=(6, 0))

        header = ttk.Frame(outer, style=f'{p}.TFrame')
        header.pack(fill=tk.X)
        ttk.Label(header, text="搜尋", style=f'{p}.TLabel').pack(side=tk.LEFT)
        self._search_entry = ttk.Entry(header, textvariable=self._search_var, width=22, style=f'{p}.TEntry')
        self._search_entry.pack(side=tk.LEFT, padx=(4, 2))
        ttk.Button(header, text="✕", width=3, command=self._clear_search, style=f'{p}.TButton').pack(side=tk.LEFT)
        ttk.Label(header, text="篩選", style=f'{p}.TLabel').pack(side=tk.LEFT, padx=(12, 4))
        combo = ttk.Combobox(
            header, textvariable=self._filter_var, state='readonly', width=10,
            values=[label for _mode, label in FILTER_MODES], style=f'{p}.TCombobox',
        )
        combo.pack(side=tk.LEFT)
        combo.bind('<<ComboboxSelected>>', lambda _e: self.refresh())
        self._redo_button = ttk.Button(header, text="↷ 重做", command=self._redo, style=f'{p}.TButton')
        self._redo_button.pack(side=tk.RIGHT)
        self._undo_button = ttk.Button(header, text="↶ 復原", command=self._undo, style=f'{p}.TButton')
        self._undo_button.pack(side=tk.RIGHT, padx=(0, 4))
        self._search_var.trace_add('write', lambda *_: self._schedule_search())

        adder = ttk.Frame(outer, style=f'{p}.TFrame')
        adder.pack(fill=tk.X, pady=(8, 6))
        self._add_entry = ttk.Entry(adder, textvariable=self._entry_var, style=f'{p}.TEntry')
        self._add_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._add_entry.bind('<Return>', lambda _e: self._quick_add())
        ttk.Button(adder, text="新增", command=self._quick_add, style=f'{p}.TButton').pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(adder, text="詳細新增…", command=self._add_dialog, style=f'{p}.TButton').pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(adder, text="匯入…", command=self._import, style=f'{p}.TButton').pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(adder, text="匯出…", command=self._export, style=f'{p}.TButton').pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(adder, text="還原…", command=self._restore, style=f'{p}.TButton').pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(adder, text="⊞", width=3, command=lambda: self._set_all_open(True),
                   style=f'{p}.TButton').pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(adder, text="⊟", width=3, command=lambda: self._set_all_open(False),
                   style=f'{p}.TButton').pack(side=tk.LEFT, padx=(4, 0))

        tree_frame = ttk.Frame(outer, style=f'{p}.TFrame')
        tree_frame.pack(fill=tk.BOTH, expand=True)
        columns = ('status', 'project', 'priority', 'start', 'due')
        column_specs = (
            ('status', "完成", 54), ('project', "專案", 100), ('priority', "優先級", 64),
            ('start', "開始", 76), ('due', "截止", 76),
        )
        # 表頭自繪：Windows 預設的 vista 主題會忽略 Treeview.Heading 的背景與文字色
        self._header = tk.Frame(tree_frame, bg=_HEADER_GAP)
        self._header.pack(fill=tk.X, side=tk.TOP)
        self._header_font = tkfont.Font(root=self, font=tkfont.nametofont('TkDefaultFont'), weight='bold')
        self._header.columnconfigure(0, weight=1, minsize=_TREE_COLUMN_MIN)
        for index, text in enumerate(("項目", *(spec[1] for spec in column_specs))):
            label = tk.Label(
                self._header, text=text, bg=_HEADER_BG, fg=_HEADER_FG, font=self._header_font,
                anchor='w' if index == 0 else 'center', padx=8, pady=4,
            )
            label.grid(row=0, column=index, sticky='nsew', padx=(0, 1), pady=(0, 1))
        for index, (_name, _text, width) in enumerate(column_specs, start=1):
            self._header.columnconfigure(index, minsize=width, weight=0)

        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show='tree', selectmode='extended', style=f'{p}.Treeview',
        )
        self.tree.column('#0', width=330, minwidth=_TREE_COLUMN_MIN, stretch=True)
        for name, _text, width in column_specs:
            self.tree.column(name, width=width, minwidth=width, stretch=False, anchor='center')
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 表頭右側留出捲軸寬度，讓欄位與清單對齊
        self._header.columnconfigure(len(column_specs) + 1, minsize=scrollbar.winfo_reqwidth(), weight=0)
        tk.Frame(self._header, bg=_HEADER_GAP).grid(row=0, column=len(column_specs) + 1, sticky='nsew')
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._empty_label = tk.Label(self.tree, text="尚無待辦事項\n在上方輸入內容後按 Enter 新增", justify=tk.CENTER)

    def _create_menu(self) -> None:
        self._menu = tk.Menu(self, tearoff=0)
        # 開啟 Toplevel 或確認視窗的項目延後到選單收合後，避免 Windows 上 grab 衝突
        self._menu.add_command(label="編輯…", command=lambda: self.after_idle(self._edit_selected))
        self._menu.add_command(label="新增子項…", command=lambda: self.after_idle(self._add_subtask_dialog))
        self._menu.add_command(label="標示完成", command=self._toggle_selected)
        self._menu.add_command(label="刪除", command=lambda: self.after_idle(self._delete_selected))
        self._menu.add_separator()
        self._menu.add_command(label="開啟連結", command=self._open_link)
        self._menu.add_command(label="移除連結", command=self._remove_link)

    def _bind_keys(self) -> None:
        self.bind('<Control-n>', lambda _e: self._focus_add_entry())
        self.bind('<Control-f>', lambda _e: self._focus_search())
        self.bind('<Control-z>', lambda _e: self._undo())
        self.bind('<Control-y>', lambda _e: self._redo())
        self.bind('<Escape>', lambda _e: self._clear_search())
        self.tree.bind('<F2>', lambda _e: self._edit_selected())
        self.tree.bind('<Return>', lambda _e: self._edit_selected())
        self.tree.bind('<space>', lambda _e: (self._toggle_selected(), 'break')[1])
        self.tree.bind('<Delete>', lambda _e: self._delete_selected())
        self.tree.bind('<Double-Button-1>', self._on_double_click)
        self.tree.bind('<ButtonPress-1>', self._on_press)
        self.tree.bind('<B1-Motion>', self._on_motion)
        self.tree.bind('<Motion>', self._on_hover)
        self.tree.bind('<Leave>', lambda _e: self._set_cursor(''))
        self.tree.bind('<ButtonRelease-1>', self._on_release)
        self.tree.bind('<Button-3>', self._on_right_click)
        self.tree.bind('<<TreeviewOpen>>', lambda _e: self._remember_open_state(True))
        self.tree.bind('<<TreeviewClose>>', lambda _e: self._remember_open_state(False))

    # ---- 配色 ----

    def apply_theme(self, theme: dict[str, str] | None) -> None:
        """時鐘切換主題時重新套用配色。"""
        if theme:
            self.theme = theme
            self._apply_colors()
            self.refresh()

    def _accents(self) -> dict[str, str]:
        return _DARK_ACCENTS if is_dark_theme(self.theme.get('bg')) else _LIGHT_ACCENTS

    def _apply_colors(self) -> None:
        bg, fg = self.theme['bg'], self.theme['fg']
        dark = is_dark_theme(bg)
        accents = self._accents()
        self.config(bg=bg)
        apply_themed_ttk_style(STYLE_PREFIX, self.theme)

        style = ttk.Style()
        sel_bg = shift_color(bg, 55 if dark else -40)
        base_font = tkfont.nametofont('TkDefaultFont')
        style.configure(f'{STYLE_PREFIX}.Treeview', background=bg, fieldbackground=bg, foreground=fg,
                        rowheight=int(base_font.metrics('linespace') * 1.6), borderwidth=0)
        # vista 主題的 field 元件忽略 fieldbackground，只留 treearea 才能讓空白處同主題底色
        style.layout(f'{STYLE_PREFIX}.Treeview', [('Treeview.treearea', {'sticky': 'nswe'})])
        style.map(f'{STYLE_PREFIX}.Treeview',
                  background=[('selected', sel_bg)], foreground=[('selected', fg)])

        self._fonts = {}
        for bold in (False, True):
            for strike in (False, True):
                for underline in (False, True):
                    font = tkfont.Font(
                        root=self, font=base_font, weight='bold' if bold else 'normal',
                        overstrike=strike, underline=underline,
                    )
                    self._fonts[(bold, strike, underline)] = font
                    self.tree.tag_configure(self._font_tag(bold, strike, underline), font=font)
        for name in ('link', 'high', 'low', 'done'):
            self.tree.tag_configure(f'fg_{name}', foreground=accents[name])
        for name in ('overdue', 'today', 'soon', 'drop'):
            self.tree.tag_configure(f'bg_{name}', background=accents[name])

        self._empty_label.config(bg=bg, fg=fg)
        self._menu.config(bg=bg, fg=fg, activebackground=sel_bg, activeforeground=fg)

    @staticmethod
    def _font_tag(bold: bool, strike: bool, underline: bool) -> str:
        return f"font_{int(bold)}{int(strike)}{int(underline)}"

    # ---- 繪製 ----

    def _current_mode(self) -> str:
        return self._filter_labels.get(self._filter_var.get(), FILTER_ALL)

    def refresh(self) -> None:
        """依目前篩選與搜尋重建清單，保留選取、捲動位置與折疊狀態。"""
        if not self.winfo_exists():
            return
        selected = self.tree.selection()
        scroll = self.tree.yview()[0]
        self.tree.delete(*self.tree.get_children())
        query = self._search_var.get()
        nodes = TodoFilter.apply(self.service.tasks, self._current_mode(), query)
        self._insert_nodes(nodes, '', date.today())
        keep = [iid for iid in selected if self.tree.exists(iid)]
        if keep:
            self.tree.selection_set(keep)
        self.tree.yview_moveto(scroll)
        if nodes:
            self._empty_label.place_forget()
        else:
            self._empty_label.config(text=(
                "沒有符合的待辦" if query.strip() or self._current_mode() != FILTER_ALL
                else "尚無待辦事項\n在上方輸入內容後按 Enter 新增"))
            self._empty_label.place(relx=0.5, rely=0.4, anchor='center')
        total, pending, done = self.service.stats()
        self._stats_var.set(f"共 {total}｜待辦 {pending}｜完成 {done}")
        self._status_var.set(self.service.last_message)
        self._update_history_buttons()

    def _insert_nodes(self, nodes: Sequence[TodoNode], parent: str, today: date) -> None:
        for node in nodes:
            task = node.task
            self.tree.insert(
                parent, tk.END, iid=task.id, text=task.text,
                values=self._row_values(task, today),
                tags=self._row_tags(task, today),
                open=task.id not in self._collapsed,
            )
            self._insert_nodes(node.children, task.id, today)

    @staticmethod
    def _row_values(task: TodoTask, today: date) -> tuple[str, str, str, str, str]:
        return (
            _DONE_MARK if task.is_done else _OPEN_MARK,
            task.project or "",
            _PRIORITY_TEXT.get(task.priority, ""),
            format_short_date(task.start_date, today),
            format_short_date(task.due_date, today),
        )

    def _row_tags(self, task: TodoTask, today: date) -> tuple[str, ...]:
        tags = [self._font_tag(bool(task.children), task.is_done, bool(task.link))]
        if task.link:
            tags.append('fg_link')
        elif task.is_done:
            tags.append('fg_done')
        elif task.priority == PRIORITY_HIGH:
            tags.append('fg_high')
        elif task.priority == PRIORITY_LOW:
            tags.append('fg_low')
        if not task.is_done and task.due_date is not None:
            if task.due_date < today:
                tags.append('bg_overdue')
            elif task.due_date == today:
                tags.append('bg_today')
            elif task.due_date <= today + timedelta(days=_DUE_SOON_DAYS):
                tags.append('bg_soon')
        return tuple(tags)

    def _after_change(self, select: str | None = None) -> None:
        self.refresh()
        if select and self.tree.exists(select):
            self.tree.selection_set(select)
            self.tree.see(select)

    def _update_history_buttons(self) -> None:
        self._undo_button.state(['!disabled'] if self.service.history.can_undo() else ['disabled'])
        self._redo_button.state(['!disabled'] if self.service.history.can_redo() else ['disabled'])

    # ---- 搜尋 ----

    def _schedule_search(self) -> None:
        if self._search_after_id is not None:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(180, self._run_search)

    def _run_search(self) -> None:
        self._search_after_id = None
        self.refresh()

    def _clear_search(self) -> None:
        if self._search_var.get():
            self._search_var.set("")

    def _focus_search(self) -> None:
        self._search_entry.focus_set()
        self._search_entry.select_range(0, tk.END)

    def _focus_add_entry(self) -> None:
        self._add_entry.focus_set()

    # ---- 操作 ----

    def _selected_ids(self) -> list[str]:
        return list(self.tree.selection())

    def _quick_add(self) -> None:
        text = self._entry_var.get().strip()
        if not text:
            return
        task = self.service.add_task(text)
        self._entry_var.set("")
        self._after_change(task.id if task else None)

    def _add_dialog(self) -> None:
        TodoEditDialog(self, lambda values: self._apply_add(None, values), self.theme)

    def _add_subtask_dialog(self) -> None:
        ids = self._selected_ids()
        parent = self.service.find_task(ids[0]) if ids else None
        if parent is None:
            return
        TodoEditDialog(self, lambda values: self._apply_add(parent.id, values), self.theme, parent_text=parent.text)

    def _apply_add(self, parent_id: str | None, values: dict[str, Any]) -> None:
        text = values.pop('text')
        task = self.service.add_task(text, parent_id, **values)
        if parent_id:
            self._collapsed.discard(parent_id)
        self._after_change(task.id if task else None)

    def _edit_selected(self) -> None:
        ids = self._selected_ids()
        task = self.service.find_task(ids[0]) if ids else None
        if task is None:
            return
        TodoEditDialog(self, lambda values: self._apply_edit(task.id, values), self.theme, task=task)

    def _apply_edit(self, task_id: str, values: dict[str, Any]) -> None:
        self.service.update_task(task_id, **values)
        self._after_change(task_id)

    def _toggle_selected(self) -> None:
        ids = self._selected_ids()
        if ids and self.service.toggle_done(ids):
            self._after_change()

    def _delete_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        themed_confirm(
            self, f"確定要刪除選取的 {len(ids)} 項待辦嗎？\n（含其子項，可用 Ctrl+Z 復原）",
            lambda: self._apply_delete(ids), self.theme, title="確認刪除", yes_text="刪除", no_text="取消",
        )

    def _apply_delete(self, ids: list[str]) -> None:
        if self.service.delete_tasks(ids):
            self._after_change()

    def _open_link(self) -> None:
        ids = self._selected_ids()
        task = self.service.find_task(ids[0]) if ids else None
        if task is not None:
            self._open_task_link(task)

    def _open_task_link(self, task: TodoTask) -> None:
        if not task.link:
            return
        if is_safe_url(task.link):
            webbrowser.open_new_tab(task.link)
        else:
            themed_error(self, "連結僅支援 http / https 網址", self.theme)

    def _remove_link(self) -> None:
        ids = self._selected_ids()
        if ids and self.service.remove_link(ids[0]):
            self._after_change()

    def _undo(self) -> None:
        if self.service.undo():
            self._after_change()

    def _redo(self) -> None:
        if self.service.redo():
            self._after_change()

    def _import(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, title="匯入待辦（JSON 或 Markdown）",
            filetypes=[("待辦檔案", "*.json *.md"), ("JSON", "*.json"),
                       ("Markdown", "*.md"), ("所有檔案", "*.*")],
        )
        if not path:
            return
        try:
            count = self.service.import_file(path)
        except (OSError, ValueError) as e:
            themed_error(self, f"匯入失敗：{e}", self.theme, title="匯入失敗")
            return
        self._after_change()
        self._status_var.set(f"已匯入 {count} 項待辦")

    def _export(self) -> None:
        themed_confirm(
            self,
            "匯出不會清空；匯入會附加。\n"
            "• JSON：完整備份（含日期、優先級、專案），可用「還原」復原。\n"
            "• Markdown：方便閱讀與分享，不含日期、優先級、專案。\n"
            "請在存檔視窗選擇格式。",
            self._export_file, self.theme, title="匯出前確認", yes_text="繼續匯出", no_text="取消",
        )

    def _export_file(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self, title="匯出待辦", defaultextension=".json", initialfile="todo.json",
            filetypes=[("JSON 完整備份", "*.json"), ("Markdown 清單", "*.md")],
        )
        if not path:
            return
        try:
            self.service.export_to_file(path)
        except (OSError, ValueError) as e:
            themed_error(self, f"匯出失敗：{e}", self.theme, title="匯出失敗")
            return
        self._status_var.set(f"已匯出至 {path}")

    def _restore(self) -> None:
        themed_confirm(
            self, "還原會以備份取代目前所有待辦（可按「復原」取消）。\n只接受 JSON 備份。",
            self._restore_file, self.theme, title="還原備份", yes_text="選擇備份", no_text="取消",
        )

    def _restore_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, title="還原待辦備份", filetypes=[("JSON 備份", "*.json")],
        )
        if not path:
            return
        try:
            count = self.service.restore_backup(path)
        except (OSError, ValueError) as e:
            themed_error(self, f"還原失敗：{e}", self.theme, title="還原失敗")
            return
        self._after_change()
        self._status_var.set(f"已還原 {count} 項待辦")

    # ---- 折疊 ----

    def _remember_open_state(self, is_open: bool) -> None:
        iid = self.tree.focus()
        if not iid:
            return
        if is_open:
            self._collapsed.discard(iid)
        else:
            self._collapsed.add(iid)

    def _set_all_open(self, is_open: bool) -> None:
        def walk(parent: str) -> None:
            for iid in self.tree.get_children(parent):
                self.tree.item(iid, open=is_open)
                if is_open:
                    self._collapsed.discard(iid)
                else:
                    self._collapsed.add(iid)
                walk(iid)

        walk('')

    # ---- 滑鼠 ----

    def _on_double_click(self, event: tk.Event) -> str | None:
        if self._link_at(event) is not None:
            return 'break'  # 連結文字上的點擊已用來開啟連結，編輯請用 F2 或點其他欄位
        if self.tree.identify_region(event.x, event.y) in ('tree', 'cell') and self.tree.identify_row(event.y):
            self.after_idle(self._edit_selected)
            return 'break'
        return None

    def _link_at(self, event: tk.Event) -> TodoTask | None:
        """滑鼠位置正好在有連結項目的文字上時回傳該項目。"""
        iid = self.tree.identify_row(event.y)
        # 資料欄的儲存格也會回報 text 元件，需限定在項目欄
        if not iid or self.tree.identify_column(event.x) != '#0' or self.tree.identify_element(event.x, event.y) != 'text':
            return None
        task = self.service.find_task(iid)
        return task if task is not None and task.link else None

    def _set_cursor(self, cursor: str) -> None:
        if str(self.tree.cget('cursor')) != cursor:
            self.tree.configure(cursor=cursor)

    def _on_hover(self, event: tk.Event) -> None:
        if self._drag is None or not self._drag['started']:
            self._set_cursor('hand2' if self._link_at(event) is not None else '')

    def _maybe_open_link(self, event: tk.Event, pressed_iid: str) -> None:
        """單擊連結文字時開啟連結；Ctrl/Shift 多選時不開啟，短時間內重複點擊只開一次。"""
        if event.state & (_SHIFT_MASK | _CONTROL_MASK):
            return
        task = self._link_at(event)
        now = time.monotonic()
        if task is None or task.id != pressed_iid or now - self._last_link_open < _LINK_REOPEN_GUARD_SEC:
            return
        self._last_link_open = now
        self._open_task_link(task)

    def _on_right_click(self, event: tk.Event) -> None:
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        if iid not in self.tree.selection():
            self.tree.selection_set(iid)
        task = self.service.find_task(iid)
        if task is None:
            return
        single = len(self.tree.selection()) == 1
        self._menu.entryconfigure(0, state='normal' if single else 'disabled')
        self._menu.entryconfigure(1, state='normal' if single else 'disabled')
        self._menu.entryconfigure(2, label="標示未完成" if task.is_done else "標示完成")
        has_link = single and bool(task.link)
        self._menu.entryconfigure(5, state='normal' if has_link else 'disabled')
        self._menu.entryconfigure(6, state='normal' if has_link else 'disabled')
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    def _on_press(self, event: tk.Event) -> str | None:
        iid = self.tree.identify_row(event.y)
        self._drag = None
        if not iid:
            return None
        if self.tree.identify_region(event.x, event.y) == 'cell' and self.tree.identify_column(event.x) == '#1':
            self.tree.selection_set(iid)
            self._toggle_selected()
            return 'break'
        self._drag = {'iid': iid, 'x': event.x, 'y': event.y, 'started': False}
        return None

    def _on_motion(self, event: tk.Event) -> None:
        drag = self._drag
        if drag is None:
            return
        if not drag['started']:
            if abs(event.x - drag['x']) < _DRAG_THRESHOLD_PX and abs(event.y - drag['y']) < _DRAG_THRESHOLD_PX:
                return
            drag['started'] = True
            self.tree.configure(cursor='hand2')
        target = self.tree.identify_row(event.y)
        self._set_drop_target(target if target and target != drag['iid'] else None)

    def _on_release(self, event: tk.Event) -> None:
        drag, self._drag = self._drag, None
        self._clear_drop_target()
        self.tree.configure(cursor='')
        if drag is None:
            return
        if not drag['started']:
            self._maybe_open_link(event, drag['iid'])
            return
        task_id = drag['iid']
        target = self.tree.identify_row(event.y)
        position, target_id = self._resolve_drop(task_id, target, event.y, event.x - drag['x'])
        if position and self.service.move_task(task_id, target_id, position):
            self._after_change(task_id)

    def _resolve_drop(
        self, task_id: str, target: str, y: int, delta_x: int,
    ) -> tuple[str | None, str | None]:
        """把放開位置轉成 (語意位置, 目標 id)：往左拖提升、目標列上／中／下段為之前／成為子項／之後。"""
        if delta_x < -_PROMOTE_DRAG_PX and self.service.parent_id_of(task_id) is not None:
            return POSITION_PROMOTE, None
        if not target:
            return POSITION_ROOT, None
        if target == task_id:
            return None, None
        bbox = self.tree.bbox(target)
        if not bbox:
            return None, None
        _x, top, _w, height = bbox
        ratio = (y - top) / max(height, 1)
        if ratio < 0.25:
            return POSITION_BEFORE, target
        if ratio > 0.75:
            return POSITION_AFTER, target
        return POSITION_INTO, target

    def _set_drop_target(self, iid: str | None) -> None:
        if iid == self._drop_item:
            return
        self._clear_drop_target()
        if iid:
            self._drop_saved_tags = tuple(self.tree.item(iid, 'tags'))
            kept = tuple(t for t in self._drop_saved_tags if not t.startswith('bg_'))
            self.tree.item(iid, tags=kept + ('bg_drop',))
            self._drop_item = iid

    def _clear_drop_target(self) -> None:
        if self._drop_item and self.tree.exists(self._drop_item):
            self.tree.item(self._drop_item, tags=self._drop_saved_tags)
        self._drop_item = None

    # ---- 關閉 ----

    def close(self) -> None:
        """記錄視窗大小並關閉。"""
        if self._search_after_id is not None:
            self.after_cancel(self._search_after_id)
            self._search_after_id = None
        if self._on_close is not None:
            try:
                self._on_close(f"{self.winfo_width()}x{self.winfo_height()}")
            except Exception as e:
                logger.debug("Todo window close callback failed: %s", e)
        self.destroy()
