"""自訂倒數計時設定視窗。"""
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from services.countdown_service import CountdownService
from ui.theme_utils import apply_themed_ttk_style, themed_error


class CountdownWindow(tk.Toplevel):
    """輸入時、分、秒與名稱後開始倒數的小視窗。"""

    def __init__(
        self,
        parent: tk.Tk,
        callback: Callable[[int, str], None],
        theme: dict[str, str] | None = None,
        geometry: str = "340x210",
    ) -> None:
        """
        初始化倒數視窗。

        Args:
            parent: 父視窗
            callback: 開始倒數的回調函數 ``(seconds, label)``
            theme: 主題配色
            geometry: 視窗幾何設定
        """
        super().__init__(parent)
        self.callback = callback
        self.theme = theme or {'bg': '#F0F0F0', 'fg': '#000000'}
        self.transient(parent)
        self.title("自訂倒數計時")
        self.geometry(geometry)
        self.resizable(False, False)
        # 不使用 grab_set，讓主時鐘仍可接收拖曳事件

        try:
            apply_themed_ttk_style('Countdown', self.theme)
            ttk.Style().configure('Countdown.TSpinbox', fieldbackground='white', foreground='black')
            self.config(bg=self.theme['bg'])
            self._create_widgets()
        except Exception as e:
            themed_error(parent, f"無法建立倒數視窗：{e}", self.theme, title="錯誤")
            self.destroy()

    def _create_widgets(self) -> None:
        """建立視窗中的所有元件。"""
        frame = ttk.Frame(self, padding="12", style='Countdown.TFrame')
        frame.pack(fill=tk.BOTH, expand=True)

        # 先 pack 底部按鈕列，避免被可展開區塊擠出可視範圍
        btn_frame = ttk.Frame(frame, style='Countdown.TFrame')
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="開始", command=self.on_submit, style='Countdown.TButton').pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy, style='Countdown.TButton').pack(side=tk.RIGHT)

        time_frame = ttk.LabelFrame(frame, text="時間", padding="8", style='Countdown.TLabelframe')
        time_frame.pack(fill=tk.X, pady=(0, 8))

        self.hours_var = tk.StringVar(value="0")
        self.minutes_var = tk.StringVar(value="5")
        self.seconds_var = tk.StringVar(value="0")
        for var, upper, unit in (
            (self.hours_var, 23, "時"),
            (self.minutes_var, 59, "分"),
            (self.seconds_var, 59, "秒"),
        ):
            ttk.Spinbox(
                time_frame, from_=0, to=upper, width=4, textvariable=var,
                wrap=True, justify=tk.CENTER, style='Countdown.TSpinbox',
            ).pack(side=tk.LEFT, padx=(0, 2))
            ttk.Label(time_frame, text=unit, style='Countdown.TLabel').pack(side=tk.LEFT, padx=(0, 10))

        label_frame = ttk.LabelFrame(frame, text="名稱（選填）", padding="8", style='Countdown.TLabelframe')
        label_frame.pack(fill=tk.X)
        self.label_entry = ttk.Entry(label_frame, style='Countdown.TEntry')
        self.label_entry.pack(fill=tk.X)
        self.label_entry.focus_set()

        self.bind('<Return>', lambda e: self.on_submit())
        self.bind('<Escape>', lambda e: self.destroy())

    def _read_seconds(self) -> int:
        """讀取輸入並換算成總秒數；輸入不是整數時拋出 ValueError。"""
        hours = int(self.hours_var.get())
        minutes = int(self.minutes_var.get())
        seconds = int(self.seconds_var.get())
        if min(hours, minutes, seconds) < 0 or minutes > 59 or seconds > 59:
            raise ValueError("時間超出範圍")
        return hours * 3600 + minutes * 60 + seconds

    def on_submit(self) -> None:
        """驗證輸入後開始倒數並關閉視窗。"""
        try:
            total = self._read_seconds()
        except ValueError:
            themed_error(self, "請輸入有效的時間（分、秒需介於 0 到 59）。", self.theme, title="輸入錯誤")
            return

        if not 1 <= total <= CountdownService.MAX_SECONDS:
            themed_error(self, "倒數時間必須大於 0 秒，且不超過 24 小時。", self.theme, title="輸入錯誤")
            return

        label = self.label_entry.get().strip()
        self.destroy()
        self.callback(total, label)
