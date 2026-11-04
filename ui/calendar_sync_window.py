"""行事曆同步（Outlook ICS）設定視窗。"""
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from ui.theme_utils import apply_themed_ttk_style, themed_error, themed_info


class CalendarSyncWindow(tk.Toplevel):
    """設定 Outlook ICS 連結、同步週期與事件前預告時間。"""

    def __init__(
        self,
        parent: tk.Tk,
        settings: dict[str, Any],
        save_callback: Callable[[bool, str, int, int], None],
        test_callback: Callable[[str], int],
        theme: dict[str, str] | None = None,
        geometry: str = "460x270",
    ) -> None:
        """
        初始化行事曆同步設定視窗。

        Args:
            parent: 父視窗
            settings: 目前設定 `{enabled, ics_url, refresh_minutes, lead_minutes}`
            save_callback: 儲存回調 `(enabled, ics_url, refresh_minutes, lead_minutes)`；
                輸入無效時應拋出 `ValueError`
            test_callback: 測試連線回調 `(ics_url) -> 事件數`；失敗時拋出例外
            theme: 主題配色
            geometry: 視窗幾何設定
        """
        super().__init__(parent)
        self.settings = settings
        self.save_callback = save_callback
        self.test_callback = test_callback
        self.theme = theme or {'bg': '#F0F0F0', 'fg': '#000000'}
        self.transient(parent)
        self.title("行事曆同步設定")
        self.geometry(geometry)
        self.resizable(False, False)
        # 不使用 grab_set，讓主時鐘仍可接收拖曳事件

        try:
            apply_themed_ttk_style('Calendar', self.theme)
            self.config(bg=self.theme['bg'])
            self._create_widgets()
        except Exception as e:
            themed_error(parent, f"無法建立行事曆同步視窗：{e}", self.theme, title="錯誤")
            self.destroy()

    def _create_widgets(self) -> None:
        frame = ttk.Frame(self, padding="10", style='Calendar.TFrame')
        frame.pack(fill=tk.BOTH, expand=True)

        # 按鈕列先 pack 到底部，避免被中間區塊推出可視範圍
        button_frame = ttk.Frame(frame, style='Calendar.TFrame')
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        self.test_button = ttk.Button(
            button_frame, text="測試連線", command=self._on_test, style='Calendar.TButton'
        )
        self.test_button.pack(side=tk.LEFT)
        ttk.Button(
            button_frame, text="取消", command=self.destroy, style='Calendar.TButton'
        ).pack(side=tk.RIGHT)
        ttk.Button(
            button_frame, text="儲存", command=self._on_save, style='Calendar.TButton'
        ).pack(side=tk.RIGHT, padx=5)

        self.enabled_var = tk.BooleanVar(value=bool(self.settings.get('enabled')))
        ttk.Checkbutton(
            frame, text="啟用：行事曆事件進行時自動進入勿擾模式",
            variable=self.enabled_var, style='Calendar.TCheckbutton',
        ).pack(anchor=tk.W, pady=(0, 8))

        ttk.Label(frame, text="Outlook ICS 連結（https，含密鑰請勿外流）：",
                  style='Calendar.TLabel').pack(anchor=tk.W)
        self.url_var = tk.StringVar(value=str(self.settings.get('ics_url', '')))
        ttk.Entry(frame, textvariable=self.url_var, show="*",
                  style='Calendar.TEntry').pack(fill=tk.X, pady=(2, 8))

        row = ttk.Frame(frame, style='Calendar.TFrame')
        row.pack(fill=tk.X)
        self.refresh_var = tk.StringVar(value=str(self.settings.get('refresh_minutes', 15)))
        self.lead_var = tk.StringVar(value=str(self.settings.get('lead_minutes', 10)))
        ttk.Label(row, text="同步間隔(分)：", style='Calendar.TLabel').grid(row=0, column=0, sticky=tk.W)
        tk.Spinbox(row, from_=1, to=1440, width=6, textvariable=self.refresh_var).grid(
            row=0, column=1, padx=(0, 15))
        ttk.Label(row, text="事件前預告(分，0=不預告)：", style='Calendar.TLabel').grid(
            row=0, column=2, sticky=tk.W)
        tk.Spinbox(row, from_=0, to=120, width=5, textvariable=self.lead_var).grid(row=0, column=3)

    def _read_numbers(self) -> tuple[int, int]:
        try:
            return int(self.refresh_var.get()), int(self.lead_var.get())
        except ValueError:
            raise ValueError("同步間隔與預告時間必須是整數") from None

    def _on_save(self) -> None:
        try:
            refresh, lead = self._read_numbers()
            self.save_callback(self.enabled_var.get(), self.url_var.get(), refresh, lead)
        except ValueError as e:
            themed_error(self, str(e), self.theme)
            return
        self.destroy()

    def _on_test(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            themed_error(self, "請先輸入 ICS 連結", self.theme)
            return
        self.test_button.config(state=tk.DISABLED, text="測試中...")

        def worker() -> None:
            try:
                count = self.test_callback(url)
                result: tuple[bool, str] = (
                    True, f"連線成功，未來 7 天內共 {count} 個事件（已含週期性事件）")
            except ImportError:
                result = (False, "缺少套件：請安裝 icalendar 與 recurring-ical-events")
            except Exception as e:
                # 不顯示完整 URL，僅顯示例外類型與訊息
                result = (False, f"連線失敗：{type(e).__name__}")
                if isinstance(e, ValueError):
                    result = (False, str(e))
            try:
                self.after(0, lambda: self._show_test_result(*result))
            except tk.TclError:
                pass  # 視窗已被關閉

        threading.Thread(target=worker, name="calendar-test", daemon=True).start()

    def _show_test_result(self, ok: bool, message: str) -> None:
        if not self.winfo_exists():
            return
        self.test_button.config(state=tk.NORMAL, text="測試連線")
        if ok:
            themed_info(self, message, self.theme, title="測試連線")
        else:
            themed_error(self, message, self.theme, title="測試連線")
