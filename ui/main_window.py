"""數位時鐘 UI 介面，負責視窗顯示與使用者互動。"""
import logging
import math
import sys
import time
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime, timedelta
from tkinter import Menu, messagebox
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

from core.clock_logic import ClockLogic
from core.events import Events
from core.observer import Observer
from ui.menus.context_menu import ContextMenu
from ui.menus.reminder_menu import ReminderMenu

if TYPE_CHECKING:
    from core.container import ServiceContainer

class DigitalClock(Observer):
    """管理時鐘的UI介面與使用者互動，並作為 ClockLogic 的 Observer。"""

    def __init__(self, container: 'ServiceContainer') -> None:
        """初始化數位時鐘 UI。"""
        self.container = container
        self.root = tk.Tk()
        self.logic = ClockLogic(self, self.container.get('config_manager'))
        self.logic.add_observer(self)  # 註冊為 observer
        self.config = self.logic.get_config()

        # 從配置中讀取常數
        app_conf = self.config['appearance']
        behavior_conf = self.config['ui_behavior']

        self.RECOMMENDED_FONTS = app_conf['recommended_fonts']
        self.TIME_FORMATS = app_conf['time_formats']
        self.DATE_FORMATS = app_conf['date_formats']
        self.CORNER_RADIUS = app_conf['corner_radius']

        self.WIDTH_CALC_TEXTS = behavior_conf['width_calc_text']
        self.WIDTH_SAFETY_FACTOR = behavior_conf['width_safety_factor']
        self.WIDTH_PADDING = behavior_conf['width_padding']
        self.MIN_WIDTH = behavior_conf['min_width']
        animation_conf = behavior_conf.get('animation', {})
        self.ANIMATION_DURATION_MS = animation_conf.get('duration_ms', 300)
        self.ANIMATION_FPS = animation_conf.get('fps', 60)
        idle_refresh_ms = animation_conf.get('idle_refresh_ms', 250)
        if isinstance(idle_refresh_ms, int | float):
            self.IDLE_REFRESH_MS = max(50, int(idle_refresh_ms))
        else:
            self.IDLE_REFRESH_MS = 250
        relaxed_idle_refresh_ms = animation_conf.get('relaxed_idle_refresh_ms', 500)
        if isinstance(relaxed_idle_refresh_ms, int | float):
            self.RELAXED_IDLE_REFRESH_MS = max(self.IDLE_REFRESH_MS, int(relaxed_idle_refresh_ms))
        else:
            self.RELAXED_IDLE_REFRESH_MS = max(self.IDLE_REFRESH_MS, 500)
        relax_after_ms = animation_conf.get('relax_after_ms', 1500)
        if isinstance(relax_after_ms, int | float):
            self.RELAX_AFTER_MS = max(0, int(relax_after_ms))
        else:
            self.RELAX_AFTER_MS = 1500
        system_conf = self.config.get('system', {})
        perf_conf = system_conf.get('performance_monitor', {})
        self.PERF_MONITOR_ENABLED = bool(perf_conf.get('enabled', False))
        perf_log_interval = perf_conf.get('log_interval_sec', 60)
        if isinstance(perf_log_interval, int | float):
            self.PERF_MONITOR_INTERVAL_SEC = max(10, int(perf_log_interval))
        else:
            self.PERF_MONITOR_INTERVAL_SEC = 60

        self.font_var = tk.StringVar(value=app_conf['font_family'])
        self.theme_var = tk.StringVar(value=app_conf['theme'])
        self.time_format_var = tk.StringVar(value=app_conf.get('time_format', '24h'))
        self.drag_offset: dict[str, int] = {'x': 0, 'y': 0}
        self.pomodoro_display_text: str = ""  # 用於顯示番茄鐘狀態的文字
        # 當滑鼠移至時間標籤上方時，暫停時間更新並顯示日期
        self._hovering_time: bool = False

        # --- 動畫相關變數 ---
        self._current_display_text: str = ""  # 當前顯示的時間文字
        self._animation_active: bool = False  # 是否正在執行動畫
        self._char_animations: dict[int, dict[str, Any]] = {}  # 每個字元位置的動畫狀態

        # --- 性能優化緩存 ---
        self._canvas_items: list[dict[str, Any]] = []  # 存儲 Canvas ID 與狀態: [{'main': id, 'sub': id, 'char': 'x'}]
        self._last_render_state: dict[str, Any] = {} # 記錄上次渲染的參數以減少不必要的更新
        self._render_params: dict[str, Any] = {} # 快取的佈局參數 (center_y, line_height 等)
        self._char_width_cache: dict[tuple[str, int, str], int] = {}
        self._char_width_cache_limit: int = 512
        self._perf_stats: dict[str, float] = {
            'frames': 0.0,
            'animation_frames': 0.0,
            'render_ms_total': 0.0,
            'loop_ms_total': 0.0,
            'logic_ticks': 0.0,
            'logic_ms_total': 0.0,
        }
        self._perf_last_log_ts: float = time.perf_counter()
        self._last_active_ui_ts: float = self._perf_last_log_ts

        try:
            self._setup_window()
            self._setup_label()
            self._create_context_menu()
            self._setup_event_handlers()
            self._bind_events()

            self.apply_theme(self.config['appearance']['theme'], save=False)
            self.logic.start()
            self.update_time()
            self.enforce_topmost()
        except Exception as e:
            messagebox.showerror("初始化錯誤", f"無法啟動時鐘：{e}")
            raise

    def _setup_event_handlers(self) -> None:
        """設定事件處理映射。"""
        self._event_handlers = {
            Events.POMODORO_PHASE_CHANGE: self._on_pomodoro_phase_change,
            Events.POMODORO_TICK: self._on_pomodoro_tick,
            Events.POMODORO_PHASE_COMPLETE: self._on_pomodoro_phase_complete,
            Events.REMINDER_DUE: self._on_reminder_due,
            Events.REMINDER_ADDED: self._on_reminder_added,
            Events.REMINDER_UPDATED: self._on_reminder_updated,
            Events.REMINDER_DELETED: self._on_reminder_deleted,
            Events.HOURLY_WEB_UPDATED: self._on_hourly_web_updated,
            Events.HOURLY_WEB_PAUSE_TOGGLED: self._on_hourly_web_pause_toggled,
            Events.REMINDER_PAUSE_TOGGLED: self._on_reminder_pause_toggled,
            Events.VACATION_TOGGLED: self._on_vacation_toggled,
            Events.OPEN_REMINDER_WINDOW: self._on_open_reminder_window,
            Events.OPEN_HOURLY_WEB_WINDOW: self._on_open_hourly_web_window,
        }

    def update(self, event: str, *args: Any, **kwargs: Any) -> None:
        """
        Observer 事件處理。

        Args:
            event: 事件名稱
            *args: 位置參數
            **kwargs: 關鍵字參數
        """
        try:
            handler = self._event_handlers.get(event)
            if handler:
                handler(*args, **kwargs)
        except Exception as e:
            logger.error("Error handling event %s: %s", event, e)

    def _on_pomodoro_phase_change(self, phase: str, *args) -> None:
        self.update_pomodoro_display(phase, None)

    def _on_pomodoro_tick(self, phase: str, remaining: int, *args) -> None:
        self.update_pomodoro_display(phase, remaining)

    def _on_pomodoro_phase_complete(self, new_phase: str, *args) -> None:
        messagebox.showinfo("番茄鐘", f"階段結束，進入 {new_phase}")

    def _on_reminder_due(self, reminder: dict[str, Any], *args) -> None:
        from multiprocessing import Process

        from ui.popup_utils import show_reminder_popup

        # 訊息為空時改用標題
        display_text = reminder.get('message') or reminder.get('title', '')
        # 使用獨立進程顯示提醒，避免阻塞主線程
        p = Process(target=show_reminder_popup, args=(display_text,))
        p.start()

    def _on_reminder_added(self, *args) -> None:
        messagebox.showinfo("成功", "提醒已設定成功！", parent=self.root)
        self._update_reminder_menu()

    def _on_reminder_updated(self, *args) -> None:
        messagebox.showinfo("成功", "提醒已更新！", parent=self.root)
        self._update_reminder_menu()

    def _on_reminder_deleted(self, *args) -> None:
        messagebox.showinfo("成功", "提醒已刪除。", parent=self.root)
        self._update_reminder_menu()

    def _on_hourly_web_updated(self, *args) -> None:
        messagebox.showinfo("成功", "整點網頁提醒設定已更新！", parent=self.root)

    def _on_hourly_web_pause_toggled(self, is_paused: bool, *args) -> None:
        label = "啟動" if is_paused else "暫停"
        try:
            self.hourly_web_menu.entryconfigure(1, label=label)
        except Exception as e:
            logger.warning("Error updating hourly web menu: %s", e)

    def _on_reminder_pause_toggled(self, is_paused: bool, *args) -> None:
        label = "啟動" if is_paused else "暫停"
        try:
            self.reminder_menu.entryconfigure(1, label=label)
        except Exception as e:
            logger.warning("Error updating reminder menu: %s", e)

    def _on_vacation_toggled(self, is_vacation: bool, *args) -> None:
        label = "開始工作" if is_vacation else "開始休假"
        try:
            self.context_menu.entryconfigure(0, label=label)
        except Exception as e:
            logger.warning("Error updating vacation menu: %s", e)

    def _on_open_reminder_window(self, reminder_to_edit: dict[str, Any] | None = None, *args) -> None:
        """開啟設定提醒的視窗。"""
        from ui.reminder_window import ReminderWindow
        try:
            config = self.logic.get_config()
            theme = config['themes'].get(config['appearance']['theme'])
            geometry = config['ui_behavior']['reminder_window_geometry']
            ReminderWindow(self.root, self.logic.add_reminder, theme, reminder_to_edit, geometry=geometry)
        except Exception as e:
            logger.error("Error opening reminder window: %s", e)

    def _on_open_hourly_web_window(self, *args) -> None:
        """開啟整點網頁提醒設定視窗。"""
        from ui.hourly_web_window import HourlyWebWindow
        try:
            config = self.logic.get_config()
            theme = config['themes'].get(config['appearance']['theme'])
            current_config = config.get('hourly_web_reminder', {})
            geometry = config['ui_behavior']['hourly_web_window_geometry']
            HourlyWebWindow(self.root, self.logic.update_hourly_web_reminder, theme, current_config, geometry=geometry)
        except Exception as e:
            logger.error("Error opening hourly web window: %s", e)

    def _setup_window(self) -> None:
        """初始化視窗屬性、大小與位置。"""
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)

        # --- 平台特定的視窗設定 ---
        if sys.platform == "win32":
            self.transparent_color = 'black'
            self.root.config(bg=self.transparent_color)
            self.root.attributes('-transparentcolor', self.transparent_color)
            self.root.attributes('-toolwindow', True)
        elif sys.platform == "darwin": # macOS
            self.root.attributes('-transparent', True)
            self.root.config(bg='systemTransparent')
            self.transparent_color = 'systemTransparent'
        else: # Linux
            # 在 Linux 上，透明度依賴於視窗管理員的支援
            self.transparent_color = 'black'
            self.root.config(bg=self.transparent_color)
            self.root.wm_attributes('-transparentcolor', self.transparent_color)

        self.root.protocol("WM_DELETE_WINDOW", self.logic.on_close)
        self._adjust_window_width(is_initial=True)

        win_conf = self.config['window']
        x, y = win_conf['x'], win_conf['y']
        if x is None:  # 首次啟動時置中
            x = (self.root.winfo_screenwidth() - win_conf['width']) // 2

        self.root.geometry(f"{win_conf['width']}x{win_conf['height']}+{x}+{y}")
        self.root.attributes('-alpha', win_conf['alpha_focused'])

    def _setup_label(self) -> None:
        """初始化時鐘標籤與圓角背景。"""
        font_config = self.config['appearance']

        self.canvas = tk.Canvas(self.root, bg=self.transparent_color, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.label = tk.Label(self.canvas, font=(font_config['font_family'], font_config['font_size']))
        # 保存原始字型設定以便在 hover 結束時還原
        self._orig_font_family = font_config['font_family']
        self._orig_font_size = font_config['font_size']
        # 不再使用 label.pack()，改為隱藏 label，使用 canvas 直接繪製動畫文字
        # self.label.pack(expand=True)

        # 建立用於動畫的字體物件
        self._anim_font = tkfont.Font(family=font_config['font_family'], size=font_config['font_size'])

        self.root.bind('<Configure>', self._on_resize)

    def _bind_events(self) -> None:
        """綁定所有UI事件。"""
        # 讓背景和文字都能觸發事件
        for widget in [self.canvas, self.label]:
            widget.bind('<Button-1>', self._start_drag) # 左鍵點擊
            widget.bind('<B1-Motion>', self._drag) # 拖曳
            widget.bind('<Button-3>', self._show_context_menu) # 右鍵點擊
            widget.bind('<Double-Button-1>', lambda e: self.logic.on_close())
            # 滑鼠移入/移出時間區域，顯示或隱藏日期
            widget.bind('<Enter>', self._on_mouse_enter)
            widget.bind('<Leave>', self._on_mouse_leave)

        alpha_conf = self.config['window']
        self.root.bind('<FocusIn>', lambda e: self.root.attributes('-alpha', alpha_conf['alpha_focused']))
        self.root.bind('<FocusOut>', lambda e: self.root.attributes('-alpha', alpha_conf['alpha_unfocused']))

    def _create_context_menu(self) -> None:
        """建立右鍵選單。"""
        self.context_menu = ContextMenu(self)
        self._update_menu_colors(self.context_menu)

        # 綁定選單參考以供後續更新使用
        self.pomodoro_menu = self.context_menu.pomodoro_menu
        self.hourly_web_menu = self.context_menu.hourly_web_menu

        # 週期提醒 (插入在整點網頁之前)
        self.reminder_menu = ReminderMenu(self.context_menu, self)
        self._update_menu_colors(self.reminder_menu)
        # 插入位置計算: Vacation(0), Sep(1), Pomodoro(2), Sep(3) -> Insert at 4
        self.context_menu.insert_cascade(4, label="週期提醒", menu=self.reminder_menu)
        self.context_menu.insert_separator(5)

    def _update_reminder_menu(self) -> None:
        """更新提醒選單的內容。"""
        # 委派給 ReminderMenu
        if hasattr(self, 'reminder_menu'):
            self.reminder_menu.update_menu()

    def update_pomodoro_display(self, phase: str, remaining: int | None) -> None:
        """
        更新番茄鐘顯示文字。

        Args:
            phase: 番茄鐘階段
            remaining: 剩餘秒數
        """
        phase_map = {"FOCUS": "專注", "SHORT_BREAK": "短休息", "LONG_BREAK": "長休息", "IDLE": "就緒"}
        phase_text = phase_map.get(phase, phase)

        if phase == "IDLE":
            self.pomodoro_display_text = f"[{phase_text}]"
        elif remaining is None:
            self.pomodoro_display_text = f"[{phase_text}]"
        else:
            m = remaining // 60
            s = remaining % 60
            self.pomodoro_display_text = f"[{phase_text} {m:02}:{s:02}]"

        # 更新番茄鐘子選單的第一個項目（狀態顯示）
        if hasattr(self, 'pomodoro_menu'):
            try:
                # 更新 label，並確保 accelerator 為空
                self.pomodoro_menu.entryconfigure(0, label=f"狀態: {self.pomodoro_display_text}", accelerator="")
            except Exception as e:
                logger.warning("Error updating pomodoro menu: %s", e)

    def _update_menu_colors(self, menu: Menu | None = None) -> None:
        """
        更新菜單的配色 (遞歸更新子菜單)。

        Args:
            menu: 要更新的選單，若為 None 則使用主選單
        """
        if menu is None:
            menu = self.context_menu

        theme = self.config['themes'].get(self.config['appearance']['theme'])
        if theme:
            fg_color = theme['fg']
            bg_color = theme['bg']

            try:
                # 設置菜單的前景色和背景色
                menu.config(fg=fg_color, bg=bg_color, selectcolor=fg_color)

                # 遍歷所有項目，如果是 cascade 類型，則遞歸更新子菜單
                last_index = menu.index('end')
                if last_index is None:
                    return

                for i in range(last_index + 1):
                    if menu.type(i) == 'cascade':
                        try:
                            submenu_name = menu.entrycget(i, 'menu')
                            if submenu_name:
                                submenu = menu.nametowidget(submenu_name)
                                self._update_menu_colors(submenu)
                        except (tk.TclError, AttributeError):
                            continue
            except (tk.TclError, AttributeError):
                pass

    def _confirm_delete_reminder(self, reminder: dict[str, Any]) -> None:
        """
        彈出確認對話框來刪除提醒。

        Args:
            reminder: 要刪除的提醒
        """
        if reminder.get('weekdays'):
            weekdays_str = "".join([d.replace('週', '') for d in reminder['weekdays']])
            time_str = f"每週{weekdays_str} {reminder['time']}"
        else:
            time_str = datetime.strptime(reminder['datetime'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M')

        msg = f"您確定要刪除以下提醒嗎？\n\n時間: {time_str}\n訊息: {reminder['message']}"
        if messagebox.askyesno("確認刪除", msg, parent=self.root):
            self.logic.delete_reminder(reminder)

    def _show_context_menu(self, event: tk.Event) -> None:
        """
        在指定位置顯示右鍵選單。

        Args:
            event: 滑鼠事件
        """
        try:
            self._update_reminder_menu()
            # self._update_pomodoro_menu_label() # 已移除，改為即時更新子選單
            self.context_menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            logger.error("Error showing context menu: %s", e)
        finally:
            self.context_menu.grab_release()

    def _adjust_window_width(self, font_family: str | None = None, is_initial: bool = False) -> None:
        """
        根據字型和時間格式動態調整視窗寬度。

        Args:
            font_family: 字型名稱，若為 None 則使用當前字型
            is_initial: 是否為初始調整
        """
        font_conf = self.config['appearance']
        current_font = font_family or font_conf['font_family']

        # 取得目前的時間格式
        time_format = font_conf.get('time_format', '24h')

        # 定義寬度計算候選字串，選取各情境下可能的最寬字串，確保背景足夠容納
        if time_format == '24h':
            # 24h 制：測試最寬數字 0 和 8，以及標準邊界
            candidates = ["00:00", "08:08", "23:59", "20:00"]
        else:
            # 12h 制：測試最寬數字與中文上午/下午 (AM/PM)
            # 需考慮有些字型 "上午" 或 "下午" 特別寬，且 0 和 8 通常最寬
            candidates = ["12:00 上午", "12:00 下午", "08:08 上午", "08:08 下午", "10:00 上午", "10:00 下午"]

        test_font = tkfont.Font(family=current_font, size=font_conf['font_size'])

        # 計算最大寬度
        max_text_width = 0
        for text in candidates:
            width = test_font.measure(text)
            if width > max_text_width:
                max_text_width = width

        new_width = max(int(max_text_width * self.WIDTH_SAFETY_FACTOR + self.WIDTH_PADDING), self.MIN_WIDTH)
        self.config['window']['width'] = new_width

        # 同步調整高度以適應字型 (特別是含中文字元時的 baseline 問題)
        # 使用 metrics('linespace') 獲取字型建議行高，並加上適當的上下內距
        try:
            line_height = test_font.metrics("linespace")
            # 預設高度為行高的 1.3 倍，確保上下有空間
            recommended_height = int(line_height * 1.3)
            # 最小高度設為 70 (原始預設值) 或 line_height + padding
            new_height = max(recommended_height, 70)
            self.config['window']['height'] = new_height
        except Exception:
            # 若 metrics 失敗，使用舊方法或不變動
            new_height = self.config['window']['height']

        # 清除渲染緩存，確保重新佈局
        if hasattr(self, '_last_render_state'):
            self._last_render_state.clear()

        if not is_initial:
            self.root.geometry(f"{new_width}x{new_height}+{self.root.winfo_x()}+{self.root.winfo_y()}")

    def _on_resize(self, event: tk.Event | None = None) -> None:
        """
        當視窗大小改變時，重新繪製圓角背景。

        Args:
            event: 視窗事件
        """
        if hasattr(self, 'theme_var'): # 確保 theme_var 已初始化
            self.apply_theme(self.theme_var.get(), save=False)

    def _draw_rounded_rect(self, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs: Any) -> None:
        """
        在 Canvas 上繪製圓角矩形。

        Args:
            x1: 左上角 x 座標
            y1: 左上角 y 座標
            x2: 右下角 x 座標
            y2: 右下角 y 座標
            radius: 圓角半徑
            **kwargs: 其他繪圖參數
        """
        self.canvas.create_polygon(
            x1+radius, y1, x1+radius, y1, x2-radius, y1, x2-radius, y1,
            x2, y1, x2, y1+radius, x2, y1+radius, x2, y2-radius,
            x2, y2-radius, x2, y2, x2-radius, y2, x2-radius, y2,
            x1+radius, y2, x1+radius, y2, x1, y2, x1, y2-radius,
            x1, y2-radius, x1, y1+radius, x1, y1+radius, x1, y1,
            smooth=True, **kwargs
        )

    def change_font(self, font_family: str) -> None:
        """
        變更字型並自動調整視窗大小。

        Args:
            font_family: 字型名稱
        """
        self.config['appearance']['font_family'] = font_family
        self._orig_font_family = font_family
        self.font_var.set(font_family)
        self._adjust_window_width(font_family)
        # 更新動畫字體
        try:
            self._anim_font.configure(family=font_family)
        except tk.TclError:
            pass
        # 重新繪製當前顯示的文字
        if self._current_display_text:
            self._draw_static_text(self._current_display_text)
        fresh = self.logic.get_config()
        fresh['appearance']['font_family'] = font_family
        self.logic.save_current_config(fresh)

    def change_time_format(self, time_format: str) -> None:
        """
        變更時間格式(12/24小時制)。

        Args:
            time_format: 時間格式（'12h' 或 '24h'）
        """
        self.config['appearance']['time_format'] = time_format
        self.time_format_var.set(time_format)
        self._adjust_window_width()  # 調整視窗寬度以適應新的時間格式
        self._update_display_time()  # 立即更新時間顯示
        fresh = self.logic.get_config()
        fresh['appearance']['time_format'] = time_format
        self.logic.save_current_config(fresh)

    def apply_theme(self, theme_key: str, save: bool = True) -> None:
        """
        套用指定的配色主題。

        Args:
            theme_key: 主題鍵值
            save: 是否儲存設定
        """
        theme = self.config['themes'].get(theme_key)
        if theme:
            bg_color = theme['bg']
            fg_color = theme['fg']

            # 清除舊的背景並繪製新的
            self.canvas.delete("all")
            self._canvas_items.clear()  # 清除文字項目引用，強制重新建立
            self._last_render_state.clear()

            self.canvas.config(bg=self.transparent_color)
            self._draw_rounded_rect(0, 0, self.root.winfo_width(), self.root.winfo_height(),
                                    self.CORNER_RADIUS, fill=bg_color, outline=bg_color)

            # 更新文字標籤顏色（為了相容性保留）
            self.label.config(bg=bg_color, fg=fg_color)
            # 確保隱藏 label
            try:
                self.label.place_forget()
            except Exception:
                pass

            self.config['appearance']['theme'] = theme_key
            self.theme_var.set(theme_key)

            # 重新繪製當前顯示的文字
            if self._current_display_text:
                self._draw_static_text(self._current_display_text)

            # 更新所有菜單的配色 (遞歸)
            self._update_menu_colors(self.context_menu)

            if save:
                fresh = self.logic.get_config()
                fresh['appearance']['theme'] = theme_key
                self.logic.save_current_config(fresh)

    def _start_drag(self, event: tk.Event) -> None:
        """
        記錄拖曳起始點。

        Args:
            event: 滑鼠事件
        """
        self.drag_offset = {'x': event.x, 'y': event.y}

    def _on_mouse_enter(self, event: tk.Event) -> None:
        """
        當滑鼠移到時間顯示上方時，顯示日期並暫停時間自動更新。

        Args:
            event: 滑鼠事件
        """
        try:
            self._hovering_time = True
            date_text = self._get_date_text()
            # 依視窗可用寬度決定顯示日期的最適字型大小
            try:
                avail_width = max(10, self.root.winfo_width() - 20)
            except Exception:
                avail_width = 200

            # 從原始字型大小開始，逐步縮小直到可以完整顯示日期或到達最小字型
            min_size = 8
            family = getattr(self, '_orig_font_family', self.config['appearance']['font_family'])
            start_size = getattr(self, '_orig_font_size', self.config['appearance']['font_size'])
            chosen_size = start_size
            test_font = tkfont.Font(family=family, size=chosen_size)
            # 若日期過長，逐步減少字型大小
            while test_font.measure(date_text) > avail_width and chosen_size > min_size:
                chosen_size -= 1
                test_font = tkfont.Font(family=family, size=chosen_size)

            # 暫存原本的字型設定，用於後續還原
            self._hover_orig_font_size = self.config['appearance']['font_size']
            self.config['appearance']['font_size'] = chosen_size

            # 使用直接顯示方式（無動畫）
            self._set_display_text_direct(date_text)

            # 還原字型設定
            self.config['appearance']['font_size'] = self._hover_orig_font_size
            # 狀態清理
            self._last_render_state.clear()
        except Exception as e:
            logger.warning("Error in _on_mouse_enter: %s", e)

    def _on_mouse_leave(self, event: tk.Event) -> None:
        """
        當滑鼠離開時間顯示時，恢復顯示時間並繼續自動更新。

        Args:
            event: 滑鼠事件
        """
        try:
            self._hovering_time = False
            # 清除當前顯示文字，強制重新繪製時間
            self._current_display_text = ""
            # 立即更新一次時間顯示以恢復狀態
            self._update_display_time()
        except Exception as e:
            logger.warning("Error in _on_mouse_leave: %s", e)

    def _get_date_text(self) -> str:
        """回傳本地化的日期字串，例如：2025年12月22日 週一"""
        now = datetime.now()
        weekdays = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
        try:
            return now.strftime(self.DATE_FORMATS['full']) + weekdays[now.weekday()]
        except Exception:
            return now.strftime(self.DATE_FORMATS['short'])

    def _drag(self, event: tk.Event) -> None:
        """
        根據滑鼠移動來拖曳視窗。

        Args:
            event: 滑鼠事件
        """
        x = self.root.winfo_x() + event.x - self.drag_offset['x']
        y = self.root.winfo_y() + event.y - self.drag_offset['y']
        self.root.geometry(f'+{x}+{y}')
        # 同步最新視窗位置到 config，再排程儲存
        self.config['window']['x'] = x
        self.config['window']['y'] = y
        fresh = self.logic.get_config()
        fresh['window']['x'] = x
        fresh['window']['y'] = y
        self.logic.schedule_save(fresh)


    def _format_time_str(self, dt: datetime, time_format: str) -> str:
        """
        將 datetime 格式化為顯示用時間字串，12h 制使用固定中文上午/下午，
        不依賴系統語系，避免 strftime('%p') 在不同 Windows 語系下輸出不一致的問題。

        Args:
            dt: 要格式化的時間
            time_format: '24h' 或 '12h'

        Returns:
            格式化後的時間字串
        """
        if time_format == '24h':
            return dt.strftime(self.TIME_FORMATS['24h'])
        else:
            ampm = '上午' if dt.hour < 12 else '下午'
            display_hour = dt.hour % 12 or 12
            return f"{display_hour:02d}:{dt.minute:02d} {ampm}"

    def _update_display_time(self, now: datetime | None = None) -> bool:
        """
        根據配置的時間格式更新時間顯示，包含跨度較長且精準對齊的預期動畫。

        Args:
            now: 可選的當前時間快照

        Returns:
            bool: 是否處於動畫渲染期間
        """
        # 如果使用者正在 hover 在時間上方，暫時不要覆蓋日期顯示
        if getattr(self, '_hovering_time', False):
            return False

        current_time = now if now is not None else datetime.now()
        time_format = self.config['appearance'].get('time_format', '24h')
        format_str = self.TIME_FORMATS['24h'] if time_format == '24h' else self.TIME_FORMATS['12h']

        current_time_str = self._format_time_str(current_time, time_format)

        # 領先動畫時間（毫秒）
        if '%S' in format_str:
            lead_window_ms = 800
            ms_to_next = 1000 - (current_time.microsecond // 1000)
        else:
            lead_window_ms = max(self.ANIMATION_DURATION_MS, 2000)
            ms_to_next = (60 - current_time.second) * 1000 - (current_time.microsecond // 1000)

        # 檢查是否進入動畫期
        if ms_to_next <= lead_window_ms:
            target_time = current_time + timedelta(milliseconds=ms_to_next + 50)
            next_time_str = self._format_time_str(target_time, time_format)

            if next_time_str != current_time_str and len(next_time_str) == len(current_time_str):
                progress = 1.0 - (ms_to_next / lead_window_ms)
                # Sine Ease-in-out
                eased_progress = 0.5 * (1 - math.cos(progress * math.pi))
                self._render_clock(current_time_str, next_time_str, eased_progress)
                return True

        # 非動畫期間
        self._render_clock(current_time_str, None, 0.0)
        return False

    def _render_clock(self, text1: str, text2: str | None = None, progress: float = 0.0) -> None:
        """
        核心渲染引擎：優化 Canvas 性能，僅在必要時更新物件。

        Args:
            text1: 當前字串 (或舊字串)
            text2: 下一個字串 (動畫中)
            progress: 動畫進度 (0.0 到 1.0)
        """
        # 1. 檢查是否需要重新建立物件 (長度改變或初次運行)
        text_len = len(text1)
        if len(self._canvas_items) != text_len:
            for item in self._canvas_items:
                try:
                    self.canvas.delete(item['main'], item['sub'])
                except Exception as e:
                    logger.debug("Canvas item delete failed: %s", e)
            self._canvas_items.clear()
            for _ in range(text_len):
                self._canvas_items.append({
                    'main': self.canvas.create_text(0, 0, anchor='center'),
                    'sub': self.canvas.create_text(0, 0, anchor='center'),
                    'last_main_char': '', 'last_sub_char': ''
                })
            self._last_render_state.clear()

        # 2. 獲取當前渲染參數
        theme = self.config['themes'].get(self.config['appearance']['theme'])
        fg_color = theme['fg'] if theme else 'white'
        font_family = self.config['appearance']['font_family']
        font_size = self.config['appearance']['font_size']

        # 3. 佈局計算 (只有在關鍵參數變動時執行)
        win_w = self.root.winfo_width()
        curr_state_key = f"{text_len}_{font_family}_{font_size}_{win_w}"
        layout_changed = self._last_render_state.get('layout_key') != curr_state_key
        if layout_changed:
            try:
                self._anim_font.configure(family=font_family, size=font_size)
            except Exception as e:
                logger.debug("Animation font configure failed: %s", e)

            total_width = self._anim_font.measure(text1)
            start_x = (self.canvas.winfo_width() - total_width) / 2
            center_y = self.canvas.winfo_height() / 2
            line_height = font_size * 1.1

            self._render_params = {
                'start_x': start_x, 'center_y': center_y,
                'line_height': line_height, 'font': (font_family, font_size)
            }
            self._last_render_state['layout_key'] = curr_state_key

        params = self._render_params
        current_x = params['start_x']
        was_animating = self._last_render_state.get('was_animating', False)
        is_animating_frame = text2 is not None

        if (
            not is_animating_frame
            and not was_animating
            and not layout_changed
            and self._last_render_state.get('last_static_text') == text1
            and self._last_render_state.get('last_fg_color') == fg_color
        ):
            return

        # 4. 批次更新 Canvas 物件
        for i in range(text_len):
            char1 = text1[i]
            char2 = text2[i] if text2 else None
            item = self._canvas_items[i]
            char_width = self._measure_char_width(char1, font_family, font_size)
            cx = current_x + char_width / 2

            if char2 is not None and char1 != char2:
                # 動畫狀態
                y_offset = progress * params['line_height']
                main_y = params['center_y'] - y_offset
                sub_y = params['center_y'] + params['line_height'] - y_offset

                self.canvas.coords(item['main'], cx, main_y)
                self.canvas.coords(item['sub'], cx, sub_y)
                self.canvas.itemconfig(item['sub'], state='normal')

                if item['last_main_char'] != char1:
                    self.canvas.itemconfig(item['main'], text=char1, fill=fg_color, font=params['font'])
                    item['last_main_char'] = char1
                if item['last_sub_char'] != char2:
                    self.canvas.itemconfig(item['sub'], text=char2, fill=fg_color, font=params['font'])
                    item['last_sub_char'] = char2
            else:
                # 靜態狀態
                if self._last_render_state.get(f'static_{i}') != char1 or was_animating:
                    self.canvas.coords(item['main'], cx, params['center_y'])
                    self.canvas.itemconfig(item['main'], text=char1, fill=fg_color, font=params['font'], state='normal')
                    self.canvas.itemconfig(item['sub'], state='hidden')
                    item['last_main_char'] = char1
                    self._last_render_state[f'static_{i}'] = char1

            current_x += char_width

        self._last_render_state['was_animating'] = is_animating_frame
        if is_animating_frame:
            self._last_render_state['last_static_text'] = None
        else:
            self._last_render_state['last_static_text'] = text1
            self._last_render_state['last_fg_color'] = fg_color

    def _measure_char_width(self, char: str, font_family: str, font_size: int) -> int:
        """測量單字元寬度，使用字型+字元快取減少重複 Font.measure。"""
        cache_key = (font_family, font_size, char)
        cached = self._char_width_cache.get(cache_key)
        if cached is not None:
            return cached

        width = self._anim_font.measure(char)
        if len(self._char_width_cache) >= self._char_width_cache_limit:
            self._char_width_cache.clear()
        self._char_width_cache[cache_key] = width
        return width

    def _record_performance_sample(
        self,
        render_ms: float,
        loop_ms: float,
        logic_ms: float,
        logic_ran: bool,
        is_animating: bool
    ) -> None:
        """記錄 UI 迴圈性能樣本，並在指定間隔輸出摘要。"""
        stats = self._perf_stats
        stats['frames'] += 1.0
        if is_animating:
            stats['animation_frames'] += 1.0
        stats['render_ms_total'] += render_ms
        stats['loop_ms_total'] += loop_ms
        if logic_ran:
            stats['logic_ticks'] += 1.0
            stats['logic_ms_total'] += logic_ms

        now_perf = time.perf_counter()
        if now_perf - self._perf_last_log_ts < self.PERF_MONITOR_INTERVAL_SEC:
            return

        frame_count = max(1, int(stats['frames']))
        logic_tick_count = int(stats['logic_ticks'])
        avg_render = stats['render_ms_total'] / frame_count
        avg_loop = stats['loop_ms_total'] / frame_count
        avg_logic = (stats['logic_ms_total'] / logic_tick_count) if logic_tick_count else 0.0
        logger.info(
            (
                "Performance | frames=%d anim_frames=%d avg_loop=%.2fms "
                "avg_render=%.2fms logic_ticks=%d avg_logic=%.2fms"
            ),
            frame_count,
            int(stats['animation_frames']),
            avg_loop,
            avg_render,
            logic_tick_count,
            avg_logic
        )
        self._perf_stats = {
            'frames': 0.0,
            'animation_frames': 0.0,
            'render_ms_total': 0.0,
            'loop_ms_total': 0.0,
            'logic_ticks': 0.0,
            'logic_ms_total': 0.0,
        }
        self._perf_last_log_ts = now_perf

    def _draw_static_text(self, text: str) -> None:
        """為了相容性保留，轉發至核心渲染引擎。"""
        self._render_clock(text)

    def _draw_animated_text(self) -> None:
        """為了相容性保留 (不再主動由外部調用)。"""
        pass

    def _set_display_text_direct(self, text: str) -> None:
        """
        直接設定顯示文字，不使用動畫（用於 hover 日期顯示等）。
        """
        self._render_clock(text)

    def enforce_topmost(self) -> None:
        """每小時強制視窗置頂一次，防止長時間失效。"""
        if not self.logic.is_hidden:
            self.root.attributes('-topmost', True)
        self.root.after(3600000, self.enforce_topmost)

    def update_time(self) -> None:
        """主更新循環，負責 UI 更新與秒級邏輯檢查。"""
        loop_start = time.perf_counter() if self.PERF_MONITOR_ENABLED else 0.0
        now = datetime.now()
        render_start = time.perf_counter() if self.PERF_MONITOR_ENABLED else 0.0
        is_animating = self._update_display_time(now)
        render_ms = ((time.perf_counter() - render_start) * 1000.0) if self.PERF_MONITOR_ENABLED else 0.0
        logic_ran = False
        logic_ms = 0.0

        # 每秒執行一次邏輯檢查
        curr_sec = now.second
        if not hasattr(self, '_last_logic_tick') or self._last_logic_tick != curr_sec:
            logic_ran = True
            logic_start = time.perf_counter() if self.PERF_MONITOR_ENABLED else 0.0
            self._last_logic_tick = curr_sec
            self.logic.check_reminders(now)
            # 番茄鐘每秒 tick
            self.logic.pomodoro.tick()
            if self.PERF_MONITOR_ENABLED:
                logic_ms = (time.perf_counter() - logic_start) * 1000.0

        scheduler_now_perf = time.perf_counter()
        if is_animating or self._hovering_time:
            self._last_active_ui_ts = scheduler_now_perf

        # 動畫期間高刷新；非動畫期間依閒置時間採用一般或放寬刷新頻率
        if is_animating:
            delay = max(10, 1000 // self.ANIMATION_FPS)
        else:
            idle_elapsed_ms = (scheduler_now_perf - self._last_active_ui_ts) * 1000.0
            if idle_elapsed_ms >= self.RELAX_AFTER_MS:
                delay = self.RELAXED_IDLE_REFRESH_MS
            else:
                delay = self.IDLE_REFRESH_MS

        if self.PERF_MONITOR_ENABLED:
            loop_ms = (time.perf_counter() - loop_start) * 1000.0
            self._record_performance_sample(render_ms, loop_ms, logic_ms, logic_ran, is_animating)

        self.root.after(delay, self.update_time)

    def run(self) -> None:
        """啟動 tkinter 主迴圈。"""
        self.root.mainloop()
