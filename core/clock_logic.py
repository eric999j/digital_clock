"""時鐘業務邏輯管理，包括設定、提醒和鍵盤監聽。"""
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

from core.events import Events
from core.observer import Observer
from services.config_service import ConfigManager
from services.hourly_web_service import HourlyWebService
from services.keyboard_service import KeyboardService
from services.pause_manager import PauseManager
from services.pomodoro_service import PomodoroService
from services.reminder_service import ReminderService
from services.vacation_schedule_service import VacationScheduleService

if TYPE_CHECKING:
    import tkinter as tk

class ClockLogic:
    """管理時鐘的業務邏輯，包括設定、提醒和鍵盤監聽。僅負責通知事件，UI 由 Observer 處理。"""

    def __init__(self, ui_controller: 'tk.Tk', config_manager: ConfigManager) -> None:
        """
        初始化 ClockLogic。

        Args:
            ui_controller: UI 控制器實例
            config_manager: 設定管理器實例
        """
        self.ui = ui_controller
        self.config_manager = config_manager
        self.config = self.config_manager.load_config() # 保持 config 屬性以相容部分舊代碼如果有的話，或給 get_config 使用
        self._save_delay_ms = self._resolve_save_delay_ms(self.config)
        self._save_after_id: str | None = None
        self._pending_config: dict[str, Any] | None = None
        self._pending_window_position: tuple[int, int] | None = None
        self._observers: list[Observer] = []

        # 初始化服務
        self.reminder_service = ReminderService(config_manager, self.notify_observers)
        self.hourly_service = HourlyWebService(config_manager, self.notify_observers)
        self.pause_manager = PauseManager(config_manager, self.notify_observers)

        # 鍵盤服務
        self.keyboard_service = KeyboardService(config_manager, self._on_screenshot_triggered)

        self.pomodoro = PomodoroService(
            self.config["pomodoro"],
            callbacks={
                "on_phase_change": self._pomodoro_phase_change,
                "on_tick": self._pomodoro_tick,
                "on_complete": self._pomodoro_phase_complete
            }
        )

        # 休假排程服務（依賴 pause_manager 與 pomodoro.stop）
        self.vacation_schedule_service = VacationScheduleService(
            config_manager,
            self.notify_observers,
            self.pause_manager,
            self.pomodoro.stop,
        )

        self.is_hidden: bool = False

    def add_observer(self, observer: Observer) -> None:
        """註冊觀察者。"""
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer: Observer) -> None:
        """移除觀察者。"""
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_observers(self, event: str, *args: Any, **kwargs: Any) -> None:
        """通知所有觀察者事件發生。單一觀察者拋例外不影響其餘派發。"""
        for observer in self._observers:
            try:
                observer.update(event, *args, **kwargs)
            except Exception as e:
                logger.error(
                    "Observer %s failed handling event %r: %s",
                    type(observer).__name__, event, e,
                )

    def start(self) -> None:
        """啟動所有背景服務和初始檢查。"""
        self.reminder_service.remove_expired_reminders()
        self.vacation_schedule_service.check()
        self.keyboard_service.start()

    def get_config(self) -> dict[str, Any]:
        """取得目前設定。"""
        return self.config_manager.load_config()

    def save_current_config(self, config: dict[str, Any] | None = None) -> None:
        """儲存目前設定到檔案。若傳入 config 則儲存該設定，否則從磁碟重新載入後儲存。"""
        self.config_manager.save_config(config if config is not None else self.get_config())

    def _resolve_save_delay_ms(self, config: dict[str, Any]) -> int:
        """
        從設定解析延遲儲存毫秒數。

        Args:
            config: 設定字典

        Returns:
            延遲儲存毫秒數
        """
        save_delay = config.get('system', {}).get('save_delay_ms', 1000)
        if isinstance(save_delay, int | float):
            return max(0, int(save_delay))
        return 1000

    def schedule_save(self, config: dict[str, Any] | None = None) -> None:
        """
        防抖延遲儲存設定，避免拖曳時頻繁寫入磁碟。

        Args:
            config: 要儲存的設定字典；若為 None 則從磁碟重新載入後儲存。
        """
        if config is not None:
            self._pending_config = config
            if self._pending_window_position is not None:
                x, y = self._pending_window_position
                config.setdefault('window', {})['x'] = x
                config['window']['y'] = y
        self._schedule_pending_save()

    def schedule_window_position_save(self, x: int, y: int) -> None:
        """
        防抖延遲儲存視窗位置，避免拖曳熱路徑反覆載入整份設定。

        Args:
            x: 視窗 x 座標
            y: 視窗 y 座標
        """
        self._pending_window_position = (x, y)
        if self._pending_config is not None:
            self._pending_config.setdefault('window', {})['x'] = x
            self._pending_config['window']['y'] = y
        self._schedule_pending_save()

    def _schedule_pending_save(self) -> None:
        """重新安排延遲儲存 callback。"""
        if self._save_after_id is not None:
            try:
                self.ui.after_cancel(self._save_after_id)
            except Exception as e:
                logger.debug("Cancel scheduled config save failed: %s", e)
        self._save_after_id = self.ui.after(self._save_delay_ms, self._do_save)

    def _do_save(self) -> None:
        """執行實際的儲存動作（由 schedule_save 排程呼叫）。"""
        self._save_after_id = None
        pending = self._pending_config
        pending_window_position = self._pending_window_position
        if pending is not None:
            self.config_manager.save_config(pending)
            self._pending_config = None
            self._pending_window_position = None
        elif pending_window_position is not None:
            config = self.get_config()
            x, y = pending_window_position
            config.setdefault('window', {})['x'] = x
            config['window']['y'] = y
            self.config_manager.save_config(config)
            self._pending_window_position = None
        else:
            self.save_current_config()

    def _pomodoro_phase_change(self, phase: str) -> None:
        self.notify_observers(Events.POMODORO_PHASE_CHANGE, phase)

    def _pomodoro_tick(self, phase: str, remaining_seconds: int) -> None:
        self.notify_observers(Events.POMODORO_TICK, phase, remaining_seconds)

    def _pomodoro_phase_complete(self, phase: str) -> None:
        self.notify_observers(Events.POMODORO_PHASE_COMPLETE, phase)

    def _on_screenshot_triggered(self) -> None:
        logger.info("Screenshot shortcut triggered (Win+Shift+S)")

    # --- 代理方法 (Delegates) ---

    def add_reminder(self, time_data: Any, message: str, weekdays: list[str], original_reminder: dict[str, Any] | None = None, title: str = "") -> None:
        self.reminder_service.add_reminder(time_data, message, weekdays, original_reminder, title)

    def delete_reminder(self, reminder_to_delete: dict[str, Any], notify: bool = True) -> None:
        self.reminder_service.delete_reminder(reminder_to_delete, notify)

    def check_reminders(self, now: datetime | None = None) -> None:
        """
        檢查所有提醒類型。

        Args:
            now: 可選的當前時間，用於同一個 tick 共享時間快照
        """
        check_time = now or datetime.now()
        # 熱路徑：使用唯讀快取避免每秒 deepcopy 整份 config
        config_snapshot = self.config_manager.load_config(read_only=True)

        # 整點網頁提醒
        self.hourly_service.check(now=check_time, config=config_snapshot)

        # 休假排程（自動進入/離開休假模式、清理過期排程）
        self.vacation_schedule_service.check(now=check_time, config=config_snapshot)

        # 一般提醒
        is_paused = self.pause_manager.get_pause_state('reminder', config=config_snapshot)
        self.reminder_service.check_reminders(is_paused, now=check_time, config=config_snapshot)

    def update_hourly_web_reminder(self, url: str, start_hour: int, end_hour: int) -> None:
        self.hourly_service.update_config(url, start_hour, end_hour)

    def toggle_hourly_web_pause(self) -> None:
        self.pause_manager.toggle_pause('hourly_web')

    def is_hourly_web_paused(self) -> bool:
        return self.pause_manager.get_pause_state('hourly_web')

    def toggle_reminder_pause(self) -> None:
        self.pause_manager.toggle_pause('reminder')

    def is_reminder_paused(self) -> bool:
        return self.pause_manager.get_pause_state('reminder')

    def toggle_vacation(self) -> None:
        self.pause_manager.toggle_vacation(self.pomodoro.stop)

    def is_on_vacation(self) -> bool:
        return self.pause_manager.get_pause_state('vacation')

    def add_vacation_schedule(self, start: str, end: str, note: str = "") -> None:
        """新增休假排程。"""
        self.vacation_schedule_service.add_schedule(start, end, note)

    def delete_vacation_schedule(self, schedule: dict[str, Any]) -> None:
        """刪除休假排程。"""
        self.vacation_schedule_service.delete_schedule(schedule)

    def list_vacation_schedules(self) -> list[dict[str, Any]]:
        """列出所有休假排程。"""
        return self.vacation_schedule_service.list_schedules()

    def open_vacation_schedule_window(self) -> None:
        """請求 UI 開啟休假排程設定視窗（透過事件解耦）。"""
        self.notify_observers(Events.OPEN_VACATION_SCHEDULE_WINDOW)

    def open_reminder_window(self, reminder_to_edit: dict[str, Any] | None = None) -> None:
        """請求 UI 開啟設定提醒的視窗（透過事件解耦，由 UI Observer 實作）。"""
        self.notify_observers(Events.OPEN_REMINDER_WINDOW, reminder_to_edit)

    def open_hourly_web_window(self) -> None:
        """請求 UI 開啟整點網頁提醒設定視窗（透過事件解耦）。"""
        self.notify_observers(Events.OPEN_HOURLY_WEB_WINDOW)

    def on_close(self) -> None:
        """應用程式關閉時的清理工作。"""
        # 停止服務
        if hasattr(self, 'keyboard_service'):
            self.keyboard_service.stop()

        if hasattr(self, 'pomodoro'):
            self.pomodoro.stop()

        # 關閉視窗
        if hasattr(self.ui, 'root'):
            self.ui.root.destroy()
        elif hasattr(self.ui, 'destroy'):
            self.ui.destroy()
