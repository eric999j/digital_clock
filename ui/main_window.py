"""數位時鐘 UI 介面，負責視窗顯示與使用者互動。"""
import logging
import math
import sys
import time
import tkinter as tk
import tkinter.font as tkfont
import uuid
from datetime import datetime, timedelta
from tkinter import Menu, messagebox
from typing import Any

from core.clock_logic import ClockLogic
from core.observer import Observer
from services.config_service import ConfigManager
from services.log_service import LogService
from ui.clock_renderer import ClockRenderer
from ui.dpi import get_scale_factor, scale_px
from ui.event_router import build_event_handlers
from ui.feature_event_controller import FeatureEventController
from ui.info_band_presenter import InfoBandPresenter
from ui.menus.context_menu import ContextMenu
from ui.menus.reminder_menu import ReminderMenu
from ui.menus.vacation_menu import VacationMenu
from ui.theme_utils import BUTTON_BG, BUTTON_FG, random_theme, themed_confirm, themed_error, themed_info
from ui.window_bounds import clamp_position, get_screen_bounds, position_popup_outside
from ui.window_controller import WindowController

logger = logging.getLogger(__name__)

LOG_CLEANUP_CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000


class DigitalClock(FeatureEventController, Observer):
    """管理時鐘的UI介面與使用者互動，並作為 ClockLogic 的 Observer。"""

    def __init__(self, config_manager: ConfigManager) -> None:
        """初始化數位時鐘 UI。"""
        self.root = tk.Tk()
        self._ui_scale: float = get_scale_factor(self.root)
        self.logic = ClockLogic(self, config_manager)
        self.logic.add_observer(self)  # 註冊為 observer
        self.config = self.logic.get_config()
        self._window_controller = WindowController(self)

        # 從配置中讀取常數
        app_conf = self.config['appearance']
        behavior_conf = self.config['ui_behavior']

        self.RECOMMENDED_FONTS = app_conf['recommended_fonts']
        self.TIME_FORMATS = app_conf['time_formats']
        self.DATE_FORMATS = app_conf['date_formats']
        self.CORNER_RADIUS = app_conf['corner_radius']

        self.WIDTH_CALC_TEXTS = behavior_conf['width_calc_text']
        self.WIDTH_SAFETY_FACTOR = behavior_conf['width_safety_factor']
        self.WIDTH_PADDING = self._px(behavior_conf['width_padding'])
        self.MIN_WIDTH = self._px(behavior_conf['min_width'])
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
        self.font_size_var = tk.IntVar(value=app_conf['font_size'])
        self.theme_var = tk.StringVar(value=app_conf['theme'])
        self.time_format_var = tk.StringVar(value=app_conf.get('time_format', '24h'))
        self.date_format_var = tk.StringVar(value=app_conf.get('date_format', 'full'))
        self.alpha_focused_var = tk.DoubleVar(value=self.config['window']['alpha_focused'])
        self.alpha_unfocused_var = tk.DoubleVar(value=self.config['window']['alpha_unfocused'])
        self.corner_radius_var = tk.IntVar(value=app_conf['corner_radius'])
        self.log_auto_clear_var = tk.BooleanVar(
            value=self.config.get('system', {}).get('log_auto_clear_enabled', True)
        )
        self.drag_offset: dict[str, int] = {'x': 0, 'y': 0}
        # 當滑鼠移至時間標籤上方時，暫停時間更新並顯示日期
        self._hovering_time: bool = False

        # --- 動畫相關變數 ---
        self._current_display_text: str = ""  # 當前顯示的時間文字
        self._animation_active: bool = False  # 是否正在執行動畫
        self._char_animations: dict[int, dict[str, Any]] = {}  # 每個字元位置的動畫狀態
        self._background_item: int | None = None
        self._reminder_popups: list[tk.Toplevel] = []
        self._todo_window: tk.Toplevel | None = None
        self._notification_window: tk.Toplevel | None = None
        self._todo_pending: int = self.logic.todo_service.pending_count()
        self._last_logic_tick: datetime | None = None

        # --- 時鐘下方資訊列（倒數計時、多時區）---
        self._info_lines: list[str] = []
        self._info_items: list[int] = []
        self._info_font: tkfont.Font | None = None
        self._info_font_size: int = 9
        self._info_line_px: int = 14
        self._base_height: int = self.config['window']['height']
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
        self._clock_renderer = ClockRenderer(self)
        self._info_band_presenter = InfoBandPresenter(self)

        try:
            self._setup_window()
            self._setup_label()
            self._create_context_menu()
            self._setup_event_handlers()
            self._bind_events()

            self.apply_theme(self.config['appearance']['theme'], save=False)
            # withdraw 狀態下 Canvas 仍可能回報 1x1。先以全透明方式顯示並
            # 處理 Configure 事件，待取得最終尺寸、完成首次繪製後才顯示給使用者。
            self.root.attributes('-alpha', 0.0)
            self.root.deiconify()
            self.root.update()
            self.logic.start()
            self.update_time()
            self.root.attributes('-alpha', self.config['window']['alpha_focused'])
            self.enforce_topmost()
            self.root.after(5000, self._ensure_visible)
        except Exception as e:
            messagebox.showerror("初始化錯誤", f"無法啟動時鐘：{e}")
            raise

    def _px(self, value: int | float) -> int:
        """將 96 DPI 基準的像素值換算為目前螢幕的實際像素。"""
        return scale_px(value, getattr(self, '_ui_scale', 1.0))

    def _setup_event_handlers(self) -> None:
        """設定事件處理映射。"""
        self._event_handlers = build_event_handlers(self)

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

    def _setup_window(self) -> None:
        """初始化視窗屬性、大小與位置。"""
        # 初始化期間先保持隱藏，待 Canvas 完成配置與首次繪製後再顯示，
        # 防止使用者看見以預設 1x1 Canvas 座標繪出的瞬間畫面。
        self.root.withdraw()
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
            try:
                self.root.wm_attributes('-transparentcolor', self.transparent_color)
            except tk.TclError:
                logger.debug("Window manager does not support -transparentcolor")

        self.root.protocol("WM_DELETE_WINDOW", self.logic.on_close)
        self._adjust_window_width(is_initial=True)

        win_conf = self.config['window']
        x, y = win_conf['x'], win_conf['y']
        if x is None:  # 首次啟動時置中
            x = (self.root.winfo_screenwidth() - win_conf['width']) // 2
        # 螢幕解析度或配置改變後，已儲存的位置可能落在可視範圍外
        x, y = self._clamp_window_position(x, y, win_conf['width'], win_conf['height'])

        self.root.geometry(f"{win_conf['width']}x{win_conf['height']}+{x}+{y}")
        self.root.attributes('-alpha', win_conf['alpha_focused'])

    def _clamp_window_position(self, x: int, y: int, width: int, height: int) -> tuple[int, int]:
        """將視窗位置限制在可視螢幕範圍內，避免時鐘被拖出或移到螢幕外。"""
        return clamp_position(x, y, width, height, get_screen_bounds(self.root))

    def _apply_window_size(self, width: int, height: int) -> None:
        """
        變更視窗大小並保持在可視範圍內。

        字型放大、資訊列增高時，靠近螢幕邊緣的視窗可能超出可視範圍，
        此時會自動內移並同步儲存新位置。
        """
        old_x, old_y = self.root.winfo_x(), self.root.winfo_y()
        x, y = self._clamp_window_position(old_x, old_y, width, height)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        if (x, y) != (old_x, old_y):
            self.config['window']['x'] = x
            self.config['window']['y'] = y
            self.logic.schedule_window_position_save(x, y)

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

        # 休假模式 cascade：置換 ContextMenu 中的 placeholder（index 0）
        self.vacation_menu = VacationMenu(self.context_menu, self)
        self._update_menu_colors(self.vacation_menu)
        try:
            self.context_menu.entryconfigure(0, menu=self.vacation_menu)
        except Exception as e:
            logger.warning("Error attaching vacation menu: %s", e)

        # 週期提醒 (插入在整點網頁之前)
        self.reminder_menu = ReminderMenu(self.context_menu, self)
        self._update_menu_colors(self.reminder_menu)
        insert_at = self.context_menu.reminder_insert_index
        self.context_menu.insert_cascade(insert_at, label="提醒", menu=self.reminder_menu)
        self.context_menu.insert_separator(insert_at + 1)

    def _update_reminder_menu(self) -> None:
        """更新提醒選單的內容。"""
        # 委派給 ReminderMenu
        if hasattr(self, 'reminder_menu'):
            self.reminder_menu.update_menu()

    def _update_vacation_menu(self) -> None:
        """更新休假模式選單的內容。"""
        if hasattr(self, 'vacation_menu'):
            try:
                self.vacation_menu.update_menu()
                self._update_menu_colors(self.vacation_menu)
            except Exception as e:
                logger.warning("Error updating vacation menu: %s", e)

    def update_pomodoro_display(self, phase: str, remaining: int | None) -> None:
        """
        更新番茄鐘顯示文字。

        Args:
            phase: 番茄鐘階段
            remaining: 剩餘秒數
        """
        phase_map = {"FOCUS": "專注", "SHORT_BREAK": "短休息", "LONG_BREAK": "長休息"}
        is_phase_change = remaining is None

        if phase not in phase_map:
            self._pomodoro_line = ""
        else:
            seconds_left = self.logic.pomodoro.remaining_seconds if remaining is None else remaining
            minutes, seconds = divmod(max(0, seconds_left), 60)
            self._pomodoro_line = f"{phase_map[phase]} {minutes:02}:{seconds:02}"
            if self.logic.pomodoro.is_paused:
                self._pomodoro_line += " (暫停)"

        if is_phase_change:
            # 階段變更時立即更新時鐘下方資訊列；一般 tick 由 update_time 每秒刷新
            self._refresh_info_lines()

    def _update_menu_colors(self, menu: Menu | None = None) -> None:
        """
        更新菜單的配色 (遞歸更新子菜單)。

        Args:
            menu: 要更新的選單，若為 None 則使用主選單
        """
        if menu is None:
            menu = self.context_menu

        theme = self.config['themes'].get(self.config['appearance']['theme'])
        if not theme:
            return

        fg_color = theme['fg']
        bg_color = theme['bg']

        # 短路：主選單樹已套用過相同顏色時跳過遞迴，減少每次右鍵開選單的無謂重繪
        is_root_call = menu is getattr(self, 'context_menu', None)
        if is_root_call:
            cache_key = (bg_color, fg_color)
            if getattr(self, '_menu_color_cache_key', None) == cache_key:
                return
            self._menu_color_cache_key = cache_key

        try:
            menu.config(fg=fg_color, bg=bg_color, selectcolor=fg_color)

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

        display_msg = reminder.get('title', '').strip() or reminder.get('message', '')
        msg = f"您確定要刪除以下提醒嗎？\n\n時間: {time_str}\n訊息: {display_msg}"

        from ui.popup_utils import show_confirm_popup_window
        theme = self._get_current_theme()
        self.root.after_idle(lambda: show_confirm_popup_window(
            self.root, msg,
            yes_callback=lambda: self.logic.delete_reminder(reminder),
            theme=theme,
            title="確認刪除",
        ))

    def _confirm_delete_vacation_schedule(self, schedule: dict[str, Any]) -> None:
        """
        彈出確認對話框來刪除休假排程。

        Args:
            schedule: 要刪除的排程
        """
        start = schedule.get('start', '')
        end = schedule.get('end', '')
        note = str(schedule.get('note', '')).strip()
        detail = f"日期範圍: {start} ~ {end}"
        if note:
            detail += f"\n備註: {note}"
        msg = f"您確定要刪除以下勿擾排程嗎？\n\n{detail}"

        from ui.popup_utils import show_confirm_popup_window
        theme = self._get_current_theme()
        self.root.after_idle(lambda: show_confirm_popup_window(
            self.root, msg,
            yes_callback=lambda: self.logic.delete_vacation_schedule(schedule),
            theme=theme,
            title="確認刪除",
        ))

    def _show_context_menu(self, event: tk.Event) -> None:
        """
        在指定位置顯示右鍵選單。

        Args:
            event: 滑鼠事件
        """
        try:
            self._update_reminder_menu()
            self._update_vacation_menu()
            self.context_menu.countdown_menu.update_menu()
            self.context_menu.timezone_menu.update_menu()
            self.context_menu.pomodoro_menu.update_menu()
            self.context_menu.refresh_todo_menu()
            self.context_menu.refresh_notification_menu()
            popup_x, popup_y = self._context_menu_position(event.x_root, event.y_root)
            # 暫時取消時鐘置頂，避免子選單（如勿擾模式）被時鐘本體遮擋
            self.root.attributes('-topmost', False)
            self.context_menu.tk_popup(popup_x, popup_y)
        except Exception as e:
            logger.error("Error showing context menu: %s", e)
        finally:
            self.context_menu.grab_release()
            try:
                if not self.logic.is_hidden:
                    self.root.attributes('-topmost', True)
            except tk.TclError:
                pass
            self._context_menu_open = False
            # 選單開啟期間被延後的資訊列變更，在此補套用
            self._refresh_info_lines()

    def _context_menu_position(self, pointer_x: int, pointer_y: int) -> tuple[int, int]:
        """
        計算不與時鐘本體重疊的右鍵選單位置。

        Args:
            pointer_x: 指標螢幕座標 x
            pointer_y: 指標螢幕座標 y

        Returns:
            選單左上角螢幕座標
        """
        menu_width = max(1, self.context_menu.winfo_reqwidth())
        menu_height = max(1, self.context_menu.winfo_reqheight())
        root_x, root_y = self.root.winfo_x(), self.root.winfo_y()
        root_width = max(1, self.root.winfo_width())
        root_height = max(1, self.root.winfo_height())
        return position_popup_outside(
            pointer_x,
            pointer_y,
            menu_width,
            menu_height,
            (root_x, root_y, root_x + root_width, root_y + root_height),
            get_screen_bounds(self.root),
        )

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
            new_height = max(recommended_height, self._px(70))
            self.config['window']['height'] = new_height
        except Exception:
            # 若 metrics 失敗，使用舊方法或不變動
            new_height = self.config['window']['height']

        self._base_height = new_height
        self._update_info_font()

        # 清除渲染緩存，確保重新佈局
        if hasattr(self, '_last_render_state'):
            self._last_render_state.clear()

        if not is_initial:
            self._apply_window_size(new_width, new_height + self._info_band_height())
            self._render_info_band()

    def _on_resize(self, event: tk.Event | None = None) -> None:
        """
        當視窗大小改變時，只更新圓角背景座標。

        避免每次 Configure 事件都刪除並重建整張 Canvas，拖曳或調整字型時
        可明顯減少 Canvas item 建立與文字重繪。

        Args:
            event: 視窗事件
        """
        if hasattr(self, 'canvas') and self._background_item is not None:
            self._redraw_background()

    def _redraw_background(self) -> None:
        """依目前 Canvas 尺寸更新背景圓角矩形。"""
        self._get_clock_renderer().redraw_background()

    @staticmethod
    def _rounded_rect_points(x1: int, y1: int, x2: int, y2: int, radius: int) -> list[int]:
        """產生圓角矩形的 Canvas 多邊形座標。"""
        return ClockRenderer.rounded_rect_points(x1, y1, x2, y2, radius)

    def _draw_rounded_rect(self, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs: Any) -> int:
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
        return self._get_clock_renderer().draw_rounded_rect(
            x1, y1, x2, y2, radius, **kwargs,
        )

    def _get_clock_renderer(self) -> ClockRenderer:
        """取得延遲建立的 Canvas renderer，保留測試用 __new__ 相容性。"""
        renderer = getattr(self, '_clock_renderer', None)
        if renderer is None:
            renderer = self._clock_renderer = ClockRenderer(self)
        return renderer

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
        self._schedule_current_config_save()

    def change_font_size(self, font_size: int) -> None:
        """變更字型大小並立即重繪時鐘。"""
        if font_size < 8:
            return
        self.config['appearance']['font_size'] = font_size
        self._orig_font_size = font_size
        self.font_size_var.set(font_size)
        self._adjust_window_width()
        try:
            self._anim_font.configure(size=font_size)
        except tk.TclError:
            pass
        self._hover_size_cache = {}
        if self._current_display_text:
            self._draw_static_text(self._current_display_text)
        self._schedule_current_config_save()

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
        self._schedule_current_config_save()

    def change_date_format(self, date_format: str) -> None:
        """變更游標停留時顯示的日期格式。"""
        if date_format not in self.DATE_FORMATS:
            return
        self.config['appearance']['date_format'] = date_format
        self.date_format_var.set(date_format)
        self._schedule_current_config_save()

    def change_window_alpha(self, is_focused: bool, alpha: float) -> None:
        """變更指定焦點狀態下的視窗透明度。"""
        normalized_alpha = min(1.0, max(0.1, float(alpha)))
        key = 'alpha_focused' if is_focused else 'alpha_unfocused'
        self.config['window'][key] = normalized_alpha
        if is_focused:
            self.alpha_focused_var.set(normalized_alpha)
            self.root.attributes('-alpha', normalized_alpha)
        else:
            self.alpha_unfocused_var.set(normalized_alpha)
        self._schedule_current_config_save()

    def change_corner_radius(self, radius: int) -> None:
        """變更時鐘背景的圓角半徑。"""
        normalized_radius = max(0, int(radius))
        self.CORNER_RADIUS = normalized_radius
        self.config['appearance']['corner_radius'] = normalized_radius
        self.corner_radius_var.set(normalized_radius)
        self._redraw_background()
        self._schedule_current_config_save()

    def change_log_auto_clear(self) -> None:
        """變更日誌每月自動清理設定。"""
        self.config.setdefault('system', {})['log_auto_clear_enabled'] = self.log_auto_clear_var.get()
        self._schedule_current_config_save()

    def confirm_clear_log(self) -> None:
        """確認後清空目前的應用程式日誌。"""
        themed_confirm(
            self.root, "確定要清空目前的日誌檔嗎？", self._clear_log,
            self._get_current_theme(), title="清空日誌", yes_text="清空", no_text="取消",
        )

    def _clear_log(self) -> None:
        """清空日誌並重設下一次自動清理的起算時間。"""
        try:
            LogService(self.logic.config_manager).clear_log()
        except OSError as error:
            themed_error(self.root, f"無法清空日誌：{error}", self._get_current_theme(), title="清理失敗")
            return

        system_config = self.config.setdefault('system', {})
        system_config['log_last_cleared_at'] = datetime.now().isoformat(timespec='seconds')
        self._schedule_current_config_save()
        themed_info(self.root, "日誌已清空。", self._get_current_theme(), title="清理完成")

    def _schedule_current_config_save(self) -> None:
        """以目前記憶體設定排程儲存，保留連續調整的所有變更。"""
        self.logic.schedule_save(self.config)

    def _check_log_cleanup(self) -> None:
        """每日檢查日誌是否到達自動清理週期。"""
        try:
            LogService(self.logic.config_manager).clear_if_due()
        except OSError:
            logger.exception("Unable to automatically clear the log file")
        self.root.after(LOG_CLEANUP_CHECK_INTERVAL_MS, self._check_log_cleanup)

    def apply_random_theme(self) -> None:
        """依內建配色產生並套用新的隨機配色。"""
        templates = list(self.logic.config_manager.default_config['themes'].values())
        self.config['themes']['__random__'] = random_theme(templates)
        self.apply_theme('__random__')

    def confirm_delete_theme(self, key: str) -> None:
        """確認刪除指定配色。"""
        theme = self.config['themes'].get(key)
        if theme is None:
            return
        themed_confirm(
            self.root, f"確定要刪除「{theme['name']}」嗎？",
            lambda: self._delete_theme(key), self._get_current_theme(),
            title="刪除配色", yes_text="刪除", no_text="取消",
        )

    def _delete_theme(self, key: str) -> None:
        """刪除配色並在需要時切換至可用的主題。"""
        themes = self.config['themes']
        if key not in themes:
            return
        del themes[key]
        if key in self.logic.config_manager.default_config['themes']:
            deleted = self.config.setdefault('deleted_themes', [])
            if key not in deleted:
                deleted.append(key)
        self.context_menu.refresh_theme_menu()
        if self.config['appearance']['theme'] == key:
            if themes:
                self.apply_theme(next(iter(themes)))
            else:
                self.apply_random_theme()
        else:
            self._schedule_current_config_save()

    def _save_named_theme(self, name: str, theme: dict[str, str]) -> None:
        """以不重複的名稱收藏配色並立即選用。"""
        name = name.strip()
        if not name:
            raise ValueError("請輸入配色名稱")
        if len(name) > 40:
            raise ValueError("配色名稱不可超過 40 個字")
        if name.casefold() == '隨機配色' or any(
            item['name'].casefold() == name.casefold() for item in self.config['themes'].values()
        ):
            raise ValueError("配色名稱已存在，請使用其他名稱")
        key = f'custom_{uuid.uuid4().hex}'
        self.config['themes'][key] = {'name': name, 'bg': theme['bg'], 'fg': theme['fg']}
        self.context_menu.refresh_theme_menu()
        self.apply_theme(key)

    def save_current_theme(self) -> None:
        """顯示命名視窗，收藏目前配色。"""
        theme = self._get_current_theme()
        if not theme:
            return
        theme = dict(theme)
        dialog = tk.Toplevel(self.root)
        dialog.title("儲存目前配色")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.configure(bg=theme['bg'])
        frame = tk.Frame(dialog, bg=theme['bg'], padx=18, pady=14)
        frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(frame, text="配色名稱", bg=theme['bg'], fg=theme['fg']).pack(anchor='w')
        entry = tk.Entry(frame, width=30, bg='white', fg='black', insertbackground='black')
        entry.pack(fill=tk.X, pady=(6, 12))
        buttons = tk.Frame(frame, bg=theme['bg'])
        buttons.pack(fill=tk.X)

        def submit() -> None:
            try:
                self._save_named_theme(entry.get(), theme)
            except ValueError as error:
                themed_error(dialog, str(error), theme, title="無法儲存")
                return
            dialog.destroy()

        tk.Button(buttons, text="取消", command=dialog.destroy, bg=BUTTON_BG, fg=BUTTON_FG).pack(side=tk.RIGHT)
        tk.Button(buttons, text="儲存", command=submit, bg=BUTTON_BG, fg=BUTTON_FG).pack(side=tk.RIGHT, padx=(0, 6))
        dialog.bind('<Return>', lambda _event: submit())
        dialog.bind('<Escape>', lambda _event: dialog.destroy())
        entry.focus_set()

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
            self._info_items.clear()
            self._last_render_state.clear()
            self._background_item = None

            self.canvas.config(bg=self.transparent_color)
            width = max(1, self.root.winfo_width())
            height = max(1, self.root.winfo_height())
            radius = min(self._px(self.CORNER_RADIUS), width // 2, height // 2)
            self._background_item = self._draw_rounded_rect(
                0, 0, width, height, radius, fill=bg_color, outline=bg_color
            )

            # 更新文字標籤顏色（為了相容性保留）
            self.label.config(bg=bg_color, fg=fg_color)
            # 確保隱藏 label
            try:
                self.label.place_forget()
            except Exception:
                pass

            self.config['appearance']['theme'] = theme_key
            self.theme_var.set(theme_key)
            self.context_menu.refresh_theme_menu()

            # 重新繪製當前顯示的文字
            if self._current_display_text:
                self._draw_static_text(self._current_display_text)
            self._render_info_band()

            # 更新所有菜單的配色 (遞歸)。切換主題後強制失效快取
            self._menu_color_cache_key = None
            self._update_menu_colors(self.context_menu)

            todo_window = self._live_todo_window()
            if todo_window is not None:
                todo_window.apply_theme(theme)
            notification_window = self._live_notification_window()
            if notification_window is not None:
                notification_window.apply_theme(theme)

            if save:
                self._schedule_current_config_save()

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

            min_size = 8
            family = getattr(self, '_orig_font_family', self.config['appearance']['font_family'])
            start_size = getattr(self, '_orig_font_size', self.config['appearance']['font_size'])

            # 快取上次的字寬計算結果，避免每次 hover 都重複建立 tkfont 並線性測量
            cache_key = (family, start_size, date_text, avail_width)
            cached_size = getattr(self, '_hover_size_cache', {}).get(cache_key)
            if cached_size is not None:
                chosen_size = cached_size
            else:
                # 用 self._anim_font 進行測量（configure 開銷比建立新物件低）
                probe = self._anim_font
                try:
                    probe.configure(family=family, size=start_size)
                except tk.TclError:
                    probe = tkfont.Font(family=family, size=start_size)
                chosen_size = start_size
                while probe.measure(date_text) > avail_width and chosen_size > min_size:
                    chosen_size -= 1
                    try:
                        probe.configure(size=chosen_size)
                    except tk.TclError:
                        break
                if not hasattr(self, '_hover_size_cache'):
                    self._hover_size_cache = {}
                # 限制快取大小
                if len(self._hover_size_cache) > 32:
                    self._hover_size_cache.clear()
                self._hover_size_cache[cache_key] = chosen_size

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
            date_format = self.config['appearance'].get('date_format', 'full')
            date_text = now.strftime(self.DATE_FORMATS[date_format])
            return date_text + (weekdays[now.weekday()] if date_format == 'full' else '')
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
        x, y = self._clamp_window_position(x, y, self.root.winfo_width(), self.root.winfo_height())
        self.root.geometry(f'+{x}+{y}')
        # 同步最新視窗位置到 config，再排程儲存
        self.config['window']['x'] = x
        self.config['window']['y'] = y
        self.logic.schedule_window_position_save(x, y)


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
        self._get_clock_renderer().render_clock(text1, text2, progress)

    def _measure_char_width(self, char: str, font_family: str, font_size: int) -> int:
        """測量單字元寬度，使用字型+字元快取減少重複 Font.measure。"""
        return self._get_clock_renderer().measure_char_width(
            char, font_family, font_size,
        )

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

    def _get_next_idle_delay(self, now: datetime) -> int:
        """計算閒置時的下一次刷新時間，並在動畫前準時喚醒。"""
        next_second_ms = max(10, 1000 - now.microsecond // 1000)
        time_format = self.config['appearance'].get('time_format', '24h')
        format_str = self.TIME_FORMATS['24h'] if time_format == '24h' else self.TIME_FORMATS['12h']

        if '%S' in format_str:
            lead_window_ms = 800
            ms_to_next = 1000 - now.microsecond // 1000
        else:
            lead_window_ms = max(self.ANIMATION_DURATION_MS, 2000)
            ms_to_next = (60 - now.second) * 1000 - now.microsecond // 1000

        # 閒置時只在整秒刷新；若動畫即將開始，提前在動畫窗口起點喚醒。
        until_animation_ms = ms_to_next - lead_window_ms
        if 0 < until_animation_ms < next_second_ms:
            return max(10, until_animation_ms)
        return next_second_ms

    def _draw_static_text(self, text: str) -> None:
        """為了相容性保留，轉發至核心渲染引擎。"""
        self._render_clock(text)

    def _draw_animated_text(self) -> None:
        """為了相容性保留 (不再主動由外部調用)。"""
        pass

    # --- 時鐘下方資訊列（倒數計時、多時區）---

    INFO_BAND_PADDING = 6
    _context_menu_open: bool = False
    _pomodoro_line: str = ""
    _info_probe_font: tkfont.Font | None = None

    def _fit_info_font_size(self, available: int) -> int:
        """回傳資訊列在可用寬度內的最大字級；以独立的量測字型計算，不動到畫面上在用的字型。"""
        return self._get_info_band_presenter().fit_font_size(available)

    def _update_info_font(self) -> None:
        """依目前字型與大小更新資訊列字型與行高（字體約為時鐘的 1/4）。"""
        family = self.config['appearance']['font_family']
        self._info_font_size = max(9, self.config['appearance']['font_size'] // 4)
        if self._info_font is None:
            self._info_font = tkfont.Font(root=self.root, family=family, size=self._info_font_size)
        else:
            try:
                self._info_font.configure(family=family, size=self._info_font_size)
            except tk.TclError as e:
                logger.debug("Info font configure failed: %s", e)
        self._info_line_px = self._info_font.metrics('linespace') + 2

    def _info_band_height(self) -> int:
        """資訊列所需高度；沒有任何資訊時為 0，視窗維持原本大小。"""
        return self._get_info_band_presenter().band_height()

    def _compose_info_lines(self, now: datetime | None = None) -> list[str]:
        """組合資訊列文字：番茄鐘（若在執行）、倒數計時（若有）在前，接著是各已選時區。"""
        return self._get_info_band_presenter().compose_lines(now)

    def _refresh_info_lines(self, now: datetime | None = None) -> None:
        """重新計算資訊列內容並在有變化時更新畫面。"""
        self._get_info_band_presenter().refresh(now)

    def _set_info_lines(self, lines: list[str]) -> None:
        """
        設定資訊列；行數改變時調整視窗高度，否則只更新文字。

        Args:
            lines: 要顯示的文字行（空清單代表隱藏資訊列）
        """
        self._get_info_band_presenter().set_lines(lines)

    def _render_info_band(self) -> None:
        """在時鐘文字下方繪製資訊列；文字過寬時自動縮小字級以符合視窗寬度。"""
        self._get_info_band_presenter().render()

    def _get_info_band_presenter(self) -> InfoBandPresenter:
        """取得延遲建立的資訊列 presenter。"""
        presenter = getattr(self, '_info_band_presenter', None)
        if presenter is None:
            presenter = self._info_band_presenter = InfoBandPresenter(self)
        return presenter

    def _on_todo_link_click(self, event: tk.Event) -> None:
        """單擊「待辦 N 項」資訊列時開啟待辦視窗。"""
        self.logic.open_todo_window()

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

    def _ensure_visible(self) -> None:
        """定期確認時鐘仍可見。

        遠端桌面連線／中斷會改變螢幕範圍或讓視窗失去置頂與顯示狀態，
        此時重新夾回可視範圍、取消隱藏並恢復置頂。
        """
        try:
            if not self.logic.is_hidden:
                if self.root.state() in ('withdrawn', 'iconic'):
                    self.root.deiconify()
                x, y = self.root.winfo_x(), self.root.winfo_y()
                nx, ny = self._clamp_window_position(
                    x, y, self.root.winfo_width(), self.root.winfo_height())
                if (nx, ny) != (x, y):
                    self.root.geometry(f"+{nx}+{ny}")
                self.root.attributes('-topmost', True)
            self.root.after(5000, self._ensure_visible)
        except tk.TclError:
            logger.debug("Clock window destroyed; stop visibility watchdog")

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
        current_second = now.replace(microsecond=0)
        if self._last_logic_tick != current_second:
            logic_ran = True
            logic_start = time.perf_counter() if self.PERF_MONITOR_ENABLED else 0.0
            self._last_logic_tick = current_second
            self.logic.check_reminders(now)
            # 番茄鐘每秒 tick
            self.logic.pomodoro.tick()
            # 倒數計時每秒 tick，資訊列（倒數、各時區時間）同步刷新
            self.logic.countdown_service.tick()
            self._refresh_info_lines(now)
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
                delay = self._get_next_idle_delay(now)
            else:
                delay = self.IDLE_REFRESH_MS

        if self.PERF_MONITOR_ENABLED:
            loop_ms = (time.perf_counter() - loop_start) * 1000.0
            self._record_performance_sample(render_ms, loop_ms, logic_ms, logic_ran, is_animating)

        self.root.after(delay, self.update_time)

    def run(self) -> None:
        """啟動 tkinter 主迴圈。"""
        self.root.after(LOG_CLEANUP_CHECK_INTERVAL_MS, self._check_log_cleanup)
        self.root.mainloop()
