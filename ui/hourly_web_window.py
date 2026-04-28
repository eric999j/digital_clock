"""整點網頁提醒設定視窗。"""
import tkinter as tk
import webbrowser
from collections.abc import Callable
from tkinter import messagebox, ttk
from typing import Any

from core.url_validator import is_safe_url


class HourlyWebWindow(tk.Toplevel):
    """用於設定整點網頁提醒的彈出視窗。"""

    def __init__(self, parent: tk.Tk, callback: Callable, theme: dict[str, str] | None = None,
                 current_config: dict[str, Any] | None = None, geometry: str = "700x600") -> None:
        """
        初始化整點網頁提醒設定視窗。

        Args:
            parent: 父視窗
            callback: 更新設定的回調函數 (enabled, url, hours, weekdays)
            theme: 主題配色
            current_config: 當前的整點網頁提醒設定
            geometry: 視窗幾何設定
        """
        super().__init__(parent)
        self.callback = callback
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
            messagebox.showerror("錯誤", f"無法建立設定視窗：{e}", parent=parent)
            self.destroy()

    def _apply_theme(self) -> None:
        """套用主題配色到視窗。"""
        self.config(bg=self.theme['bg'])

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

        style.configure('TFrame', background=bg)
        style.configure('TLabelFrame', background=bg, foreground=fg)
        style.configure('TLabelFrame.Label', background=bg, foreground=fg)
        style.configure('TLabel', background=bg, foreground=fg)
        style.configure('TCheckbutton', background=bg, foreground=fg)
        style.configure('TEntry', fieldbackground='white', foreground='black')

        if is_dark_theme:
            style.configure('TButton', background=bg, foreground='#000000', borderwidth=1)
            hover_bg = '#666666'
            hover_fg = '#000000'
        else:
            style.configure('TButton', background=bg, foreground=fg, borderwidth=1)
            hover_bg = '#CCCCCC'
            hover_fg = '#000000'

        style.map('TButton',
                  relief=[('pressed', 'sunken'), ('!pressed', 'raised')],
                  background=[('active', hover_bg), ('pressed', hover_bg)],
                  foreground=[('active', hover_fg), ('pressed', hover_fg)])

    def _create_widgets(self) -> None:
        """建立視窗中的所有元件。"""
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 說明 Label
        info_label = ttk.Label(
            main_frame,
            text="設定整點自動開啟的網頁。\n此功能僅在工作日 (週一至週五) 的指定時段內啟用。",
            justify=tk.LEFT
        )
        info_label.pack(fill=tk.X, pady=(0, 15))

        # 網址設定
        url_frame = ttk.LabelFrame(main_frame, text="目標網頁", padding="10")
        url_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(url_frame, text="網址 (URL):").pack(anchor='w', pady=(0, 5))
        self.url_entry = ttk.Entry(url_frame)
        self.url_entry.pack(fill=tk.X)
        ttk.Label(url_frame, text="例: https://google.com", font=('TkDefaultFont', 8)).pack(anchor='w', pady=(2, 0))

        # 時間範圍設定
        time_frame = ttk.LabelFrame(main_frame, text="啟用時段 (整點)", padding="10")
        time_frame.pack(fill=tk.X, pady=(0, 10))

        container = ttk.Frame(time_frame)
        container.pack(fill=tk.X)

        # 製作 00:00 - 23:00 的選單值
        hours_values = [f"{h:02d}:00" for h in range(24)]

        ttk.Label(container, text="從").pack(side=tk.LEFT)
        self.start_hour_combo = ttk.Combobox(container, values=hours_values, width=8, state="readonly")
        self.start_hour_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(container, text="到").pack(side=tk.LEFT)
        self.end_hour_combo = ttk.Combobox(container, values=hours_values, width=8, state="readonly")
        self.end_hour_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(container, text="(包含)").pack(side=tk.LEFT)

        # 底部按鈕 - 使用 side=BOTTOM 讓它貼底，並與上方保持距離
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

        ttk.Button(btn_frame, text="立即測試", command=self._test_open_url).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="儲存", command=self._on_submit).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.RIGHT, padx=10)

    def _load_config(self) -> None:
        """載入現有設定。"""
        self.url_entry.insert(0, self.current_config.get('url', ''))

        start_hour = self.current_config.get('start_hour', 8)
        end_hour = self.current_config.get('end_hour', 17)

        # 兼容舊設定：如果只有 hours 列表，取最小和最大值
        if 'hours' in self.current_config and 'start_hour' not in self.current_config:
            hours = self.current_config['hours']
            if hours:
                start_hour = min(hours)
                end_hour = max(hours)

        # 設定下拉選單
        try:
            self.start_hour_combo.current(start_hour)
            self.end_hour_combo.current(end_hour)
        except (tk.TclError, ValueError):
            self.start_hour_combo.current(8)
            self.end_hour_combo.current(17)

    def _on_submit(self) -> None:
        """處理儲存事件。"""
        try:
            url = self.url_entry.get().strip()

            # 從 "08:00" 格式字串解析出整數 8
            start_str = self.start_hour_combo.get()
            end_str = self.end_hour_combo.get()

            start_hour = int(start_str.split(':')[0])
            end_hour = int(end_str.split(':')[0])

            if start_hour > end_hour:
                messagebox.showerror("設定錯誤", "結束時間不能早於開始時間。", parent=self)
                return

            if url and not is_safe_url(url):
                messagebox.showerror(
                    "設定錯誤",
                    "請使用以 http:// 或 https:// 開頭的有效網址。",
                    parent=self,
                )
                return

            self.callback(url, start_hour, end_hour)
            self.destroy()

        except Exception as e:
            messagebox.showerror("錯誤", f"發生錯誤：{e}", parent=self)

    def _test_open_url(self) -> None:
        """立即測試開啟網頁。"""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("錯誤", "請先輸入網頁網址。", parent=self)
            return
        if not is_safe_url(url):
            messagebox.showerror(
                "錯誤",
                "請使用以 http:// 或 https:// 開頭的有效網址。",
                parent=self,
            )
            return
        try:
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("錯誤", f"無法開啟網頁：{e}", parent=self)

