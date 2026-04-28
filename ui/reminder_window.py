"""提醒設定視窗。"""
import tkinter as tk
from collections.abc import Callable
from datetime import datetime, timedelta
from tkinter import messagebox, ttk
from typing import Any


class ReminderWindow(tk.Toplevel):
    """一個用於設定提醒的彈出視窗。"""

    def __init__(self, parent: tk.Tk, callback: Callable, theme: dict[str, str] | None = None,
                 reminder_to_edit: dict[str, Any] | None = None, geometry: str = "400x500") -> None:
        """
        初始化提醒視窗。

        Args:
            parent: 父視窗
            callback: 新增/更新提醒的回調函數
            theme: 主題配色
            reminder_to_edit: (可選) 要編輯的提醒項目
            geometry: 視窗幾何設定
        """
        super().__init__(parent)
        self.callback = callback
        self.theme = theme or {'bg': '#F0F0F0', 'fg': '#000000'}
        self.reminder_to_edit = reminder_to_edit
        self.transient(parent)
        self.title("編輯提醒" if reminder_to_edit else "設定提醒")
        self.geometry(geometry)
        self.resizable(False, False)
        self.grab_set()  # 鎖定焦點

        self._last_date_selection: dict[str, str] = {}  # 用於儲存上次的日期選擇

        try:
            self._setup_style()
            self._apply_theme()
            self._create_widgets()
            self._populate_time_options()
            if self.reminder_to_edit:
                self._load_reminder_data()
        except Exception as e:
            messagebox.showerror("錯誤", f"無法建立提醒視窗：{e}", parent=parent)
            self.destroy()

    def _apply_theme(self) -> None:
        """套用主題配色到視窗。"""
        self.config(bg=self.theme['bg'])

    def _setup_style(self) -> None:
        """設置 ttk 樣式以符合主題，使用自定義樣式名稱以避免污染全域樣式。"""
        style = ttk.Style()

        bg = self.theme['bg']
        fg = self.theme['fg']

        # 判斷背景是亮色還是暗色
        try:
            r, g, b = int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16)
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            is_dark_theme = brightness < 128
        except (ValueError, IndexError):
            is_dark_theme = False  # 預設為亮色主題

        # 為不同的 ttk 元件設置"自定義"樣式 (Prefix with 'Reminder.')
        style.configure('Reminder.TFrame', background=bg)
        style.configure('Reminder.TLabelframe', background=bg, foreground=fg)
        style.configure('Reminder.TLabelframe.Label', background=bg, foreground=fg)
        style.configure('Reminder.TLabel', background=bg, foreground=fg)
        style.configure('Reminder.TCombobox', fieldbackground='white', foreground='black')
        style.configure('Reminder.TEntry', fieldbackground='white', foreground='black')
        style.configure('Reminder.TCheckbutton', background=bg, foreground=fg)

        # 根據主題的亮暗決定懸停顏色
        if is_dark_theme:
            # 暗色主題：按鈕文字固定為黑色，懸停時背景變亮
            style.configure('Reminder.TButton', background=bg, foreground='#000000', borderwidth=1)
            hover_bg = '#666666'
            hover_fg = '#000000'
        else:
            # 亮色主題：按鈕文字預設為主題前景，懸停時背景變暗
            style.configure('Reminder.TButton', background=bg, foreground=fg, borderwidth=1)
            hover_bg = '#CCCCCC'
            hover_fg = '#000000'

        style.map('Reminder.TButton',
                  relief=[('pressed', 'sunken'), ('!pressed', 'raised')],
                  background=[('active', hover_bg), ('pressed', hover_bg)],
                  foreground=[('active', hover_fg), ('pressed', hover_fg)])

    def _create_widgets(self) -> None:
        """建立視窗中的所有元件。"""
        # Apply Reminder.TFrame
        frame = ttk.Frame(self, padding="10", style='Reminder.TFrame')
        frame.pack(fill=tk.BOTH, expand=True)

        # 週期選擇
        weekday_frame = ttk.LabelFrame(frame, text="週期", padding="5", style='Reminder.TLabelframe')
        weekday_frame.pack(fill=tk.X, pady=5)

        self.weekday_vars = {
            "週一": tk.BooleanVar(), "週二": tk.BooleanVar(), "週三": tk.BooleanVar(),
            "週四": tk.BooleanVar(), "週五": tk.BooleanVar(), "週六": tk.BooleanVar(),
            "週日": tk.BooleanVar()
        }

        self.weekday_container = ttk.Frame(weekday_frame, style='Reminder.TFrame')
        self.weekday_container.pack(fill=tk.X)

        for i, day in enumerate(self.weekday_vars.keys()):
            cb = ttk.Checkbutton(self.weekday_container, text=day, variable=self.weekday_vars[day],
                                 command=self._toggle_date_selection, style='Reminder.TCheckbutton')
            cb.grid(row=0, column=i, padx=2, sticky='w')

        # 上班日快捷按鈕
        ttk.Button(self.weekday_container, text="上班日", command=self._select_workdays,
                   style='Reminder.TButton').grid(row=1, column=0, columnspan=2, pady=(5, 0), sticky='w')

        # 日期選擇
        # Apply Reminder.TLabelframe
        date_frame = ttk.LabelFrame(frame, text="日期", padding="5", style='Reminder.TLabelframe')
        date_frame.pack(fill=tk.X, pady=5)

        # [修正] 使用 timedelta 正確計算 5 分鐘後的時間 (自動處理進位與跨日/跨年)
        now = datetime.now()
        default_time = now + timedelta(minutes=5)

        self.year_var = tk.StringVar(value=str(default_time.year))
        self.month_var = tk.StringVar(value=str(default_time.month).zfill(2))
        self.day_var = tk.StringVar(value=str(default_time.day).zfill(2))

        # [修正] 加入 state="readonly" 與 style
        ttk.Label(date_frame, text="年:", style='Reminder.TLabel').pack(side=tk.LEFT)
        self.year_cb = ttk.Combobox(date_frame, textvariable=self.year_var, width=5, state="readonly", style='Reminder.TCombobox')
        self.year_cb.pack(side=tk.LEFT, padx=2)

        ttk.Label(date_frame, text="月:", style='Reminder.TLabel').pack(side=tk.LEFT)
        self.month_cb = ttk.Combobox(date_frame, textvariable=self.month_var, width=3, state="readonly", style='Reminder.TCombobox')
        self.month_cb.pack(side=tk.LEFT, padx=2)

        ttk.Label(date_frame, text="日:", style='Reminder.TLabel').pack(side=tk.LEFT)
        self.day_cb = ttk.Combobox(date_frame, textvariable=self.day_var, width=3, state="readonly", style='Reminder.TCombobox')
        self.day_cb.pack(side=tk.LEFT, padx=2)

        # 時間選擇
        time_frame = ttk.LabelFrame(frame, text="時間", padding="5", style='Reminder.TLabelframe')
        time_frame.pack(fill=tk.X, pady=5)

        # [修正] 使用計算過的正確時間
        self.hour_var = tk.StringVar(value=str(default_time.hour).zfill(2))
        self.minute_var = tk.StringVar(value=str(default_time.minute).zfill(2))

        ttk.Label(time_frame, text="時:", style='Reminder.TLabel').pack(side=tk.LEFT)
        self.hour_cb = ttk.Combobox(time_frame, textvariable=self.hour_var, width=3, state="readonly", style='Reminder.TCombobox')
        self.hour_cb.pack(side=tk.LEFT, padx=5)

        ttk.Label(time_frame, text="分:", style='Reminder.TLabel').pack(side=tk.LEFT)
        self.minute_cb = ttk.Combobox(time_frame, textvariable=self.minute_var, width=3, state="readonly", style='Reminder.TCombobox')
        self.minute_cb.pack(side=tk.LEFT, padx=5)

        # 提醒標題
        title_frame = ttk.LabelFrame(frame, text="提醒標題", padding="5", style='Reminder.TLabelframe')
        title_frame.pack(fill=tk.X, pady=5)
        self.title_entry = ttk.Entry(title_frame, style='Reminder.TEntry')
        self.title_entry.pack(fill=tk.X, expand=True)

        # 提醒訊息
        msg_frame = ttk.LabelFrame(frame, text="提醒訊息", padding="5", style='Reminder.TLabelframe')
        msg_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.msg_entry = tk.Text(msg_frame, height=10, bg='white', fg='black', font='TkDefaultFont')
        self.msg_entry.pack(fill=tk.BOTH, expand=True)

        # 按鈕
        btn_frame = ttk.Frame(frame, style='Reminder.TFrame')
        btn_frame.pack(fill=tk.X, pady=10)

        ttk.Button(btn_frame, text="設定完成", command=self.on_submit, style='Reminder.TButton').pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy, style='Reminder.TButton').pack(side=tk.RIGHT)

    def _populate_time_options(self) -> None:
        """填入日期和時間的下拉選單選項。"""
        now = datetime.now()
        self.year_cb['values'] = [str(y) for y in range(now.year, now.year + 5)]
        self.month_cb['values'] = [str(m).zfill(2) for m in range(1, 13)]
        self.day_cb['values'] = [str(d).zfill(2) for d in range(1, 32)]
        self.hour_cb['values'] = [str(h).zfill(2) for h in range(24)]
        self.minute_cb['values'] = [str(m).zfill(2) for m in range(60)]

    def on_submit(self) -> None:
        """處理提交事件，驗證並回呼。"""
        try:
            hour = int(self.hour_var.get())
            minute = int(self.minute_var.get())
            title = self.title_entry.get().strip()
            message = self.msg_entry.get("1.0", "end-1c").strip() # 去除多餘的換行和空白

            selected_weekdays = [day for day, var in self.weekday_vars.items() if var.get()]

            if selected_weekdays:
                # 週期性提醒
                reminder_time = f"{hour:02d}:{minute:02d}"
                self.callback(reminder_time, message, selected_weekdays, self.reminder_to_edit, title)
            else:
                # 單次提醒
                year = int(self.year_var.get())
                month = int(self.month_var.get())
                day = int(self.day_var.get())
                reminder_datetime = datetime(year, month, day, hour, minute)

                # 編輯模式下，如果時間未改，允許等於現在時間
                is_editing_without_time_change = False
                if self.reminder_to_edit and not self.reminder_to_edit.get('weekdays'):
                    original_dt = datetime.strptime(self.reminder_to_edit['datetime'], '%Y-%m-%d %H:%M:%S')
                    if original_dt == reminder_datetime:
                        is_editing_without_time_change = True

                if not is_editing_without_time_change and reminder_datetime <= datetime.now():
                    messagebox.showerror("錯誤", "提醒時間必須是未來的時間。", parent=self)
                    return
                self.callback(reminder_datetime, message, [], self.reminder_to_edit, title)

            self.destroy()

        except ValueError as e:
            messagebox.showerror("錯誤", f"請輸入有效的日期和時間：{e}", parent=self)
        except Exception as e:
            messagebox.showerror("錯誤", f"發生錯誤：{e}", parent=self)

    def _load_reminder_data(self) -> None:
        """如果處於編輯模式，則載入現有提醒的資料。"""
        if not self.reminder_to_edit:
            return

        self.title_entry.insert(0, self.reminder_to_edit.get('title', ''))
        self.msg_entry.insert("1.0", self.reminder_to_edit.get('message', ''))

        if self.reminder_to_edit.get('weekdays'):
            # 週期性提醒
            for day in self.reminder_to_edit['weekdays']:
                if day in self.weekday_vars:
                    self.weekday_vars[day].set(True)

            time_parts = self.reminder_to_edit.get('time', '00:00').split(':')
            self.hour_var.set(time_parts[0])
            self.minute_var.set(time_parts[1])

            # 禁用日期選擇
            self.year_cb.config(state='disabled')
            self.month_cb.config(state='disabled')
            self.day_cb.config(state='disabled')

        else:
            # 單次提醒
            dt = datetime.strptime(self.reminder_to_edit['datetime'], '%Y-%m-%d %H:%M:%S')
            self.year_var.set(str(dt.year))
            self.month_var.set(str(dt.month).zfill(2))
            self.day_var.set(str(dt.day).zfill(2))
            self.hour_var.set(str(dt.hour).zfill(2))
            self.minute_var.set(str(dt.minute).zfill(2))

            # 禁用週期選擇
            for var in self.weekday_vars.values():
                var.set(False)
            for child in self.weekday_container.winfo_children():
                child.config(state='disabled')

    def _toggle_date_selection(self):
        """根據週期選擇的狀態啟用或禁用日期選擇。"""
        is_any_weekday_selected = any(var.get() for var in self.weekday_vars.values())

        if is_any_weekday_selected:
            # 如果將要禁用，先儲存當前日期
            if self.year_cb.cget('state') != 'disabled':
                self._last_date_selection = {
                    'year': self.year_var.get(),
                    'month': self.month_var.get(),
                    'day': self.day_var.get()
                }

            date_state = 'disabled'
            # 設定為週期性提醒時，將日期重設為今天，避免混淆
            now = datetime.now()
            self.year_var.set(str(now.year))
            self.month_var.set(str(now.month).zfill(2))
            self.day_var.set(str(now.day).zfill(2))
        else:
            # 如果將要啟用，恢復之前儲存的日期
            date_state = 'readonly'
            if self._last_date_selection:
                self.year_var.set(self._last_date_selection['year'])
                self.month_var.set(self._last_date_selection['month'])
                self.day_var.set(self._last_date_selection['day'])

        self.year_cb.config(state=date_state)
        self.month_cb.config(state=date_state)
        self.day_cb.config(state=date_state)

    def _select_workdays(self) -> None:
        """選擇上班日（週一至週五）。"""
        workdays = ["週一", "週二", "週三", "週四", "週五"]
        for day, var in self.weekday_vars.items():
            var.set(day in workdays)
        self._toggle_date_selection()
