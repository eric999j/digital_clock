"""通知中心視窗：列出各模組的通知歷史，可標示已讀與清除；表格樣式與待辦事項視窗一致。"""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from services.notification_center import NotificationCenter
from ui.theme_utils import (
    BUTTON_FG,
    BUTTON_HOVER_BG,
    BUTTON_PRESSED_BG,
    apply_themed_ttk_style,
    is_dark_theme,
    shift_color,
)
from ui.todo_edit_dialog import STYLE_PREFIX

_HEADER_BG = BUTTON_HOVER_BG
_HEADER_FG = BUTTON_FG
_HEADER_GAP = BUTTON_PRESSED_BG
_MAIN_COLUMN_MIN = 160
_EMPTY_TEXT = "目前沒有通知"
# (欄位 key, 表頭, 寬度)；內容欄為 #0 並隨視窗伸縮
_COLUMN_SPECS = (('title', "標題", 110), ('source', "來源", 70), ('time', "時間", 120))


class NotificationWindow(tk.Toplevel):
    """通知中心（單例，由 ``DigitalClock`` 管理）；配色跟隨時鐘主題。"""

    def __init__(self, parent: tk.Tk, center: NotificationCenter, theme: dict[str, str] | None = None,
                 geometry: str = "620x380") -> None:
        """
        Args:
            parent: 父視窗
            center: 通知中心
            theme: 主題配色
            geometry: 視窗幾何設定
        """
        super().__init__(parent)
        self.center = center
        self.theme = theme or {'bg': '#F0F0F0', 'fg': '#000000'}
        self.title("通知中心")
        self.geometry(geometry)
        self.minsize(480, 280)
        self._build()
        self.apply_theme(self.theme)
        self.center.mark_all_read()

    def _build(self) -> None:
        p = STYLE_PREFIX
        outer = ttk.Frame(self, padding=10, style=f'{p}.TFrame')
        outer.pack(fill=tk.BOTH, expand=True)

        # 先 pack 底部按鈕列，避免被可展開區塊擠出可視範圍
        buttons = ttk.Frame(outer, style=f'{p}.TFrame')
        buttons.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))
        self._status = ttk.Label(buttons, style=f'{p}.TLabel')
        self._status.pack(side=tk.LEFT)
        ttk.Button(buttons, text="清除全部", command=self.center.clear, style=f'{p}.TButton').pack(side=tk.RIGHT)
        ttk.Button(buttons, text="全部標為已讀", command=self.center.mark_all_read,
                   style=f'{p}.TButton').pack(side=tk.RIGHT, padx=(0, 6))

        table = ttk.Frame(outer, style=f'{p}.TFrame')
        table.pack(fill=tk.BOTH, expand=True)

        # 表頭自繪：Windows 預設的 vista 主題會忽略 Treeview.Heading 的背景與文字色
        self._header = tk.Frame(table, bg=_HEADER_GAP)
        self._header.pack(fill=tk.X, side=tk.TOP)
        self._header_font = tkfont.Font(root=self, font=tkfont.nametofont('TkDefaultFont'), weight='bold')
        self._header.columnconfigure(0, weight=1, minsize=_MAIN_COLUMN_MIN)
        for index, text in enumerate(("內容", *(spec[1] for spec in _COLUMN_SPECS))):
            tk.Label(
                self._header, text=text, bg=_HEADER_BG, fg=_HEADER_FG, font=self._header_font,
                anchor='w' if index == 0 else 'center', padx=8, pady=4,
            ).grid(row=0, column=index, sticky='nsew', padx=(0, 1), pady=(0, 1))
        for index, (_name, _text, width) in enumerate(_COLUMN_SPECS, start=1):
            self._header.columnconfigure(index, minsize=width, weight=0)

        self.tree = ttk.Treeview(
            table, columns=[spec[0] for spec in _COLUMN_SPECS], show='tree', selectmode='browse',
            style=f'{p}.Treeview',
        )
        self.tree.column('#0', width=330, minwidth=_MAIN_COLUMN_MIN, stretch=True)
        for name, _text, width in _COLUMN_SPECS:
            self.tree.column(name, width=width, minwidth=width, stretch=False, anchor='center')
        scrollbar = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 表頭右側留出捲軸寬度，讓欄位與清單對齊
        self._header.columnconfigure(len(_COLUMN_SPECS) + 1, minsize=scrollbar.winfo_reqwidth(), weight=0)
        tk.Frame(self._header, bg=_HEADER_GAP).grid(row=0, column=len(_COLUMN_SPECS) + 1, sticky='nsew')
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._empty_label = tk.Label(self.tree, text=_EMPTY_TEXT, justify=tk.CENTER)

    def apply_theme(self, theme: dict[str, str]) -> None:
        """套用時鐘主題配色並重繪。"""
        self.theme = theme
        bg, fg = theme['bg'], theme['fg']
        self.configure(bg=bg)
        apply_themed_ttk_style(STYLE_PREFIX, theme)

        style = ttk.Style()
        sel_bg = shift_color(bg, 55 if is_dark_theme(bg) else -40)
        base_font = tkfont.nametofont('TkDefaultFont')
        style.configure(f'{STYLE_PREFIX}.Treeview', background=bg, fieldbackground=bg, foreground=fg,
                        rowheight=int(base_font.metrics('linespace') * 1.6), borderwidth=0)
        # vista 主題的 field 元件忽略 fieldbackground，只留 treearea 才能讓空白處同主題底色
        style.layout(f'{STYLE_PREFIX}.Treeview', [('Treeview.treearea', {'sticky': 'nswe'})])
        style.map(f'{STYLE_PREFIX}.Treeview',
                  background=[('selected', sel_bg)], foreground=[('selected', fg)])
        self._unread_font = tkfont.Font(root=self, font=base_font, weight='bold')
        self.tree.tag_configure('unread', font=self._unread_font)
        self._empty_label.config(bg=bg, fg=fg)
        self.refresh()

    def refresh(self) -> None:
        """重新載入通知清單。"""
        self.tree.delete(*self.tree.get_children())
        items = self.center.items()
        for item in items:
            self.tree.insert(
                '', tk.END, iid=str(item.id), text=item.message,
                values=(item.title, item.source_label, item.timestamp.strftime('%m/%d %H:%M:%S')),
                tags=() if item.read else ('unread',),
            )
        unread = self.center.unread_count()
        self._status.config(text=f"共 {len(items)} 則，未讀 {unread} 則" if items else "")
        if items:
            self._empty_label.place_forget()
        else:
            self._empty_label.place(relx=0.5, rely=0.4, anchor='center')
