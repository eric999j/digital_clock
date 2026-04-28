import tkinter.font as tkfont
from tkinter import Menu
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 避免循環引用，只在型別檢查時匯入
    from ..main_window import DigitalClock

class ContextMenu(Menu):
    """主右鍵選單。"""

    def __init__(self, ui: 'DigitalClock', **kwargs):
        super().__init__(ui.root, tearoff=0, **kwargs)
        self.ui = ui
        self.logic = ui.logic
        self._build_menu()

    def _build_menu(self) -> None:
        """建立選單項目。"""
        # 開始休假/開始工作
        vacation_label = "開始工作" if self.logic.is_on_vacation() else "開始休假"
        self.add_command(label=vacation_label, command=self.logic.toggle_vacation)
        self.add_separator()

        # 番茄鐘
        self.pomodoro_menu = Menu(self, tearoff=0)
        self.pomodoro_menu.add_command(label="狀態: [就緒]", state="normal")
        self.pomodoro_menu.add_separator()
        self.pomodoro_menu.add_command(label="開始專注", command=lambda: self.logic.pomodoro.start_focus())
        self.pomodoro_menu.add_command(label="停止", command=lambda: self.logic.pomodoro.stop())
        self.add_cascade(label="番茄鐘", menu=self.pomodoro_menu)

        # 週期提醒 (由 ReminderMenu 處理，這裡預留或由外部掛載)
        # 為了架構清晰，我們這裡還是保留結構，但在 main_window 中組合
        self.add_separator()
        # self.add_cascade(label="週期提醒", menu=reminder_menu) # Will be added by main window

        # 整點網頁
        self.hourly_web_menu = Menu(self, tearoff=0)
        self.hourly_web_menu.add_command(label="設定", command=self.logic.open_hourly_web_window)
        pause_label = "啟動" if self.logic.is_hourly_web_paused() else "暫停"
        self.hourly_web_menu.add_command(label=pause_label, command=self.logic.toggle_hourly_web_pause)
        self.add_cascade(label="整點網頁", menu=self.hourly_web_menu)
        self.add_separator()

        # 時鐘設定
        self._add_clock_settings_menu()
        self.add_separator()

        self.add_command(label="離開", command=self.logic.on_close)

    def _add_clock_settings_menu(self) -> None:
        """新增時鐘設定選單。"""
        clock_settings_menu = Menu(self, tearoff=0)

        # 字型
        font_menu = Menu(clock_settings_menu, tearoff=0)
        available_fonts = set(tkfont.families())
        for font in self.ui.RECOMMENDED_FONTS:
            if font in available_fonts:
                font_menu.add_radiobutton(label=font, variable=self.ui.font_var, value=font,
                                          command=lambda f=font: self.ui.change_font(f))
        clock_settings_menu.add_cascade(label="字型選擇", menu=font_menu)
        clock_settings_menu.add_separator()

        # 配色
        theme_menu = Menu(clock_settings_menu, tearoff=0)
        for key, theme in self.ui.config['themes'].items():
            theme_menu.add_radiobutton(label=theme['name'], variable=self.ui.theme_var, value=key,
                                      command=lambda k=key: self.ui.apply_theme(k))
        clock_settings_menu.add_cascade(label="配色方案", menu=theme_menu)
        clock_settings_menu.add_separator()

        # 時間格式
        time_format_menu = Menu(clock_settings_menu, tearoff=0)
        time_format_menu.add_radiobutton(label="24小時制", variable=self.ui.time_format_var, value="24h",
                                         command=lambda: self.ui.change_time_format("24h"))
        time_format_menu.add_radiobutton(label="12小時制", variable=self.ui.time_format_var, value="12h",
                                         command=lambda: self.ui.change_time_format("12h"))
        clock_settings_menu.add_cascade(label="時間格式", menu=time_format_menu)

        self.add_cascade(label="時鐘設定", menu=clock_settings_menu)
