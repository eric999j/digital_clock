"""整點網頁提醒設定視窗。"""
import tkinter as tk
import webbrowser
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from core.url_validator import is_safe_url


class HourlyWebWindow(tk.Toplevel):
    """用於設定整點網頁提醒的彈出視窗。"""

    def __init__(self, parent: tk.Tk, callback: Callable, theme: dict[str, str] | None = None,
                 current_config: dict[str, Any] | None = None, geometry: str = "560x430") -> None:
        super().__init__(parent)
        self.callback = callback
        self._rules: list[dict[str, Any]] = []
        self.theme = theme or {'bg': '#F0F0F0', 'fg': '#000000'}
        self.current_config = current_config or {}
        self.transient(parent)
        self.title("整點網頁提醒設定")
        self.geometry(geometry)
        self.resizable(False, False)
        self.grab_set()

        try:
            self._setup_style()
            self._apply_theme()
            self._create_widgets()
            self._load_config()
        except Exception as e:
            self._show_error(f"無法建立設定視窗：{e}")
            self.destroy()

    def _apply_theme(self) -> None:
        """套用主題配色到視窗。"""
        self.config(bg=self.theme['bg'])

    def _show_error(self, msg: str, title: str = "錯誤") -> None:
        """以主題樣式顯示錯誤視窗。"""
        from ui.popup_utils import show_reminder_popup_window
        show_reminder_popup_window(self, msg, self.theme, title=title, ok_text="確定")

    def _setup_style(self) -> None:
        """設置 ttk 樣式以符合主題。"""
        style = ttk.Style()
        bg = self.theme['bg']
        fg = self.theme['fg']

        try:
            r, g, b = int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16)
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            is_dark_theme = brightness < 128
        except (ValueError, IndexError):
            is_dark_theme = False

        style.configure('HourlyWeb.TFrame', background=bg)
        style.configure('HourlyWeb.TLabelframe', background=bg, foreground=fg)
        style.configure('HourlyWeb.TLabelframe.Label', background=bg, foreground=fg)
        style.configure('HourlyWeb.TLabel', background=bg, foreground=fg)
        style.configure('HourlyWeb.TCheckbutton', background=bg, foreground=fg)
        style.configure('HourlyWeb.TEntry', fieldbackground='white', foreground='black')

        if is_dark_theme:
            style.configure('HourlyWeb.TButton', background=bg, foreground='#000000', borderwidth=1)
            hover_bg = '#666666'
            hover_fg = '#000000'
        else:
            style.configure('HourlyWeb.TButton', background=bg, foreground=fg, borderwidth=1)
            hover_bg = '#CCCCCC'
            hover_fg = '#000000'

        style.map('HourlyWeb.TButton',
                  relief=[('pressed', 'sunken'), ('!pressed', 'raised')],
                  background=[('active', hover_bg), ('pressed', hover_bg)],
                  foreground=[('active', hover_fg), ('pressed', hover_fg)])

    def _create_widgets(self) -> None:
        outer = ttk.Frame(self, padding="12", style='HourlyWeb.TFrame')
        outer.pack(fill=tk.BOTH, expand=True)

        # 底部按鈕先 pack，確保永遠可見
        btn_frame = ttk.Frame(outer, style='HourlyWeb.TFrame')
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 0))
        ttk.Button(btn_frame, text="取消", command=self.destroy,
                   style='HourlyWeb.TButton').pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(btn_frame, text="儲存", command=self._on_submit,
                   style='HourlyWeb.TButton').pack(side=tk.RIGHT)

        # 新增規則表單（BOTTOM 之上，固定高度）
        add_frame = ttk.LabelFrame(outer, text="新增規則", padding="8", style='HourlyWeb.TLabelframe')
        add_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 6))

        url_row = ttk.Frame(add_frame, style='HourlyWeb.TFrame')
        url_row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(url_row, text="URL:", width=5, style='HourlyWeb.TLabel').pack(side=tk.LEFT)
        self._add_url_entry = ttk.Entry(url_row, style='HourlyWeb.TEntry')
        self._add_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(url_row, text="測試", command=self._test_url,
                   style='HourlyWeb.TButton').pack(side=tk.LEFT, padx=(4, 0))

        hour_row = ttk.Frame(add_frame, style='HourlyWeb.TFrame')
        hour_row.pack(fill=tk.X)
        hours_values = [f"{h:02d}:00" for h in range(24)]
        ttk.Label(hour_row, text="時段:", width=5, style='HourlyWeb.TLabel').pack(side=tk.LEFT)
        ttk.Label(hour_row, text="從", style='HourlyWeb.TLabel').pack(side=tk.LEFT)
        self._start_combo = ttk.Combobox(hour_row, values=hours_values, width=7, state="readonly")
        self._start_combo.current(8)
        self._start_combo.pack(side=tk.LEFT, padx=4)
        ttk.Label(hour_row, text="到", style='HourlyWeb.TLabel').pack(side=tk.LEFT)
        self._end_combo = ttk.Combobox(hour_row, values=hours_values, width=7, state="readonly")
        self._end_combo.current(17)
        self._end_combo.pack(side=tk.LEFT, padx=4)
        ttk.Label(hour_row, text="（含）", style='HourlyWeb.TLabel').pack(side=tk.LEFT)
        ttk.Button(hour_row, text="新增 ＋", command=self._add_rule,
                   style='HourlyWeb.TButton').pack(side=tk.RIGHT)

        # 說明標籤
        ttk.Label(
            outer,
            text="設定整點自動開啟的網頁（工作日指定時段）。支援多組規則，依序比對時段。",
            wraplength=520, justify=tk.LEFT, style='HourlyWeb.TLabel',
        ).pack(fill=tk.X, pady=(0, 6))

        # 規則清單（佔剩餘空間）
        list_frame = ttk.LabelFrame(outer, text="URL 排程規則", padding="6", style='HourlyWeb.TLabelframe')
        list_frame.pack(fill=tk.BOTH, expand=True)

        cols = ttk.Frame(list_frame, style='HourlyWeb.TFrame')
        cols.pack(fill=tk.BOTH, expand=True)
        self._rules_listbox = tk.Listbox(
            cols, height=5, selectmode=tk.SINGLE,
            bg='white', fg='black', font=('Consolas', 9), activestyle='dotbox',
        )
        self._rules_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._rules_listbox.bind('<Double-Button-1>', self._open_selected_rule_url)
        sb = ttk.Scrollbar(cols, orient=tk.VERTICAL, command=self._rules_listbox.yview)
        sb.pack(side=tk.LEFT, fill=tk.Y)
        self._rules_listbox.configure(yscrollcommand=sb.set)
        ttk.Button(list_frame, text="刪除選取", command=self._remove_rule,
                   style='HourlyWeb.TButton').pack(anchor='e', pady=(4, 0))

    def _load_config(self) -> None:
        url_rules: list[dict] = self.current_config.get('url_rules', [])
        # 自動遷移舊版單一 URL 設定
        if not url_rules:
            url = self.current_config.get('url', '').strip()
            if url:
                url_rules = [{
                    'url': url,
                    'start_hour': self.current_config.get('start_hour', 8),
                    'end_hour': self.current_config.get('end_hour', 17),
                }]
        self._refresh_listbox(url_rules)

    def _refresh_listbox(self, rules: list[dict]) -> None:
        self._rules: list[dict] = list(rules)
        self._rules_listbox.delete(0, tk.END)
        for r in self._rules:
            s, e = r.get('start_hour', 0), r.get('end_hour', 23)
            self._rules_listbox.insert(tk.END, f"{s:02d}:00–{e:02d}:00  {r.get('url', '')}")

    def _add_rule(self) -> None:
        url = self._add_url_entry.get().strip()
        if not url:
            self._show_error("請輸入 URL。")
            return
        if not is_safe_url(url):
            self._show_error("請使用以 http:// 或 https:// 開頭的有效網址。")
            return
        start_hour = int(self._start_combo.get().split(':')[0])
        end_hour = int(self._end_combo.get().split(':')[0])
        if start_hour > end_hour:
            self._show_error("結束時間不能早於開始時間。")
            return
        rules = list(getattr(self, '_rules', []))
        rules.append({'url': url, 'start_hour': start_hour, 'end_hour': end_hour})
        self._refresh_listbox(rules)
        self._add_url_entry.delete(0, tk.END)

    def _remove_rule(self) -> None:
        sel = self._rules_listbox.curselection()
        if not sel:
            return
        rules = list(getattr(self, '_rules', []))
        del rules[sel[0]]
        self._refresh_listbox(rules)

    def _open_selected_rule_url(self, _event: tk.Event) -> None:
        """雙擊規則清單時開啟該列 URL。"""
        sel = self._rules_listbox.curselection()
        if not sel:
            return

        idx = sel[0]
        if idx >= len(self._rules):
            return

        url = str(self._rules[idx].get('url', '')).strip()
        if not is_safe_url(url):
            self._show_error("此規則的網址無效，請先編輯為 http:// 或 https:// 開頭。")
            return

        try:
            webbrowser.open(url)
        except Exception as e:
            self._show_error(f"無法開啟網頁：{e}")

    def _test_url(self) -> None:
        url = self._add_url_entry.get().strip()
        if not url:
            self._show_error("請先輸入網頁網址。")
            return
        if not is_safe_url(url):
            self._show_error("請使用以 http:// 或 https:// 開頭的有效網址。")
            return
        try:
            webbrowser.open(url)
        except Exception as e:
            self._show_error(f"無法開啟網頁：{e}")

    def _on_submit(self) -> None:
        rules = list(getattr(self, '_rules', []))
        pending_url = self._add_url_entry.get().strip()
        if pending_url:
            if not is_safe_url(pending_url):
                self._show_error("請使用以 http:// 或 https:// 開頭的有效網址。")
                return
            start_hour = int(self._start_combo.get().split(':')[0])
            end_hour = int(self._end_combo.get().split(':')[0])
            if start_hour > end_hour:
                self._show_error("結束時間不能早於開始時間。")
                return
            rules.append({'url': pending_url, 'start_hour': start_hour, 'end_hour': end_hour})
            self._refresh_listbox(rules)
        self.callback(rules)
        self.destroy()
