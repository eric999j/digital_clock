"""時鐘業務邏輯管理，包括設定、提醒和鍵盤監聽。"""
import copy
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

from core.app_state import AppState
from core.check_coordinator import CheckCoordinator
from core.clock_logic_facade import ClockLogicFacade
from core.events import Events
from core.observer import Observer
from core.typed_events import EventPublisher, TypedEvent, as_typed_event
from services.calendar_sync_service import CalendarSyncService
from services.config_service import ConfigManager
from services.config_store import ConfigStore, persist_config
from services.countdown_service import CountdownService
from services.hourly_web_service import HourlyWebService
from services.keyboard_service import KeyboardService
from services.notification_center import NotificationCenter
from services.pause_manager import PauseManager
from services.pomodoro_service import PomodoroService
from services.reminder_service import ReminderService
from services.timezone_service import TimezoneService
from services.todo_service import TodoService
from services.vacation_schedule_service import VacationScheduleService

if TYPE_CHECKING:
    import tkinter as tk


def _build_config_patch(
    original: dict[str, Any],
    updated: dict[str, Any],
) -> dict[str, tuple[str, Any]]:
    """建立遞迴設定變更集，保留新增、取代與刪除語意。"""
    patch: dict[str, tuple[str, Any]] = {}
    for key in original.keys() - updated.keys():
        patch[key] = ('delete', None)
    for key, value in updated.items():
        if key not in original:
            patch[key] = ('replace', copy.deepcopy(value))
            continue
        previous = original[key]
        if isinstance(previous, dict) and isinstance(value, dict):
            nested = _build_config_patch(previous, value)
            if nested:
                patch[key] = ('merge', nested)
        elif previous != value:
            patch[key] = ('replace', copy.deepcopy(value))
    return patch


def _apply_config_patch(
    latest: dict[str, Any],
    patch: dict[str, tuple[str, Any]],
) -> dict[str, Any]:
    """將設定變更集套用至最新完整設定，不覆蓋無關欄位。"""
    merged = copy.deepcopy(latest)
    for key, (operation, value) in patch.items():
        if operation == 'delete':
            merged.pop(key, None)
        elif operation == 'merge':
            current = merged.get(key)
            base = current if isinstance(current, dict) else {}
            merged[key] = _apply_config_patch(base, value)
        elif operation == 'replace':
            merged[key] = copy.deepcopy(value)
        else:
            raise ValueError(f"Unknown config patch operation: {operation}")
    return merged


class ClockLogic(ClockLogicFacade):
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
        self.config_store = ConfigStore(config_manager)
        self.config = self.config_store.mutable() # 相容舊 UI；型別化存取請使用 config_store
        self._save_delay_ms = self._resolve_save_delay_ms(self.config)
        self._save_after_id: str | None = None
        self._pending_config: dict[str, Any] | None = None
        self._pending_config_base: dict[str, Any] | None = None
        self._pending_window_position: tuple[int, int] | None = None
        self._observers: list[Observer] = []

        # 初始化服務
        self.reminder_service = ReminderService(config_manager, self.notify_observers)
        self.hourly_service = HourlyWebService(config_manager, self.notify_observers)
        self.todo_service = TodoService(config_manager, self.notify_observers)
        self.pause_manager = PauseManager(config_manager, self.notify_observers)
        self.countdown_service = CountdownService(self.notify_observers)
        self.timezone_service = TimezoneService(config_manager, self.notify_observers)
        # 鍵盤服務
        self.keyboard_service = KeyboardService(config_manager, self._on_screenshot_triggered)

        self.pomodoro = PomodoroService(
            lambda: self.config_manager.load_config(read_only=True).get('pomodoro', {}),
            callbacks={
                "on_phase_change": self._pomodoro_phase_change,
                "on_tick": self._pomodoro_tick,
                "on_complete": self._pomodoro_phase_complete,
                "on_pause_toggle": self._pomodoro_pause_toggled,
            }
        )
        # P2: pomodoro.stop 儲存在 PauseManager 內，避免 VacationScheduleService 直接耗合 Pomodoro
        self.pause_manager.set_pomodoro_stop(self.pomodoro.stop)

        # 休假排程服務（依賴 pause_manager）
        self.vacation_schedule_service = VacationScheduleService(
            config_manager,
            self.notify_observers,
            self.pause_manager,
        )

        # 行事曆同步服務（Outlook ICS → 自動休假）
        self.calendar_sync_service = CalendarSyncService(
            config_manager,
            self.notify_observers,
            self.pause_manager,
        )
        self.check_coordinator = CheckCoordinator(
            config_manager,
            self.vacation_schedule_service,
            self.calendar_sync_service,
            self.hourly_service,
            self.todo_service,
            self.reminder_service,
            self.pause_manager,
        )

        self.is_hidden: bool = False

        # 跨模組狀態與通知中心：先於 UI 註冊，UI 收到事件時狀態已是最新
        self.app_state = AppState(self.notify_observers)
        self.notification_center = NotificationCenter(self.notify_observers)
        self.add_observer(self.app_state)
        self.add_observer(self.notification_center)

    def add_observer(self, observer: Observer) -> None:
        """註冊觀察者。"""
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer: Observer) -> None:
        """移除觀察者。"""
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_observers(
        self,
        event: str | TypedEvent,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """驗證事件封包並通知觀察者；單一觀察者失敗不影響其餘派發。"""
        typed = as_typed_event(event, *args, **kwargs)
        event_name, event_args, event_kwargs = typed.legacy()
        for observer in self._observers:
            try:
                observer.update(event_name, *event_args, **event_kwargs)
            except Exception as e:
                logger.error(
                    "Observer %s failed handling event %r: %s",
                    type(observer).__name__, event_name, e,
                )

    def start(self) -> None:
        """啟動所有背景服務和初始檢查。"""
        self.app_state.sync(
            on_vacation=self.is_on_vacation(),
            reminders_paused=self.is_reminder_paused(),
            hourly_web_paused=self.is_hourly_web_paused(),
            todo_pending=self.todo_service.pending_count(),
        )
        self.reminder_service.remove_expired_reminders()
        self.vacation_schedule_service.check()
        self.calendar_sync_service.start()
        self.hourly_service.run_startup_rules()
        self.keyboard_service.start()

    def get_config(self) -> dict[str, Any]:
        """取得目前設定。"""
        store = getattr(self, 'config_store', None)
        if store is not None:
            return store.mutable()
        return self.config_manager.load_config()

    def save_current_config(self, config: dict[str, Any] | None = None) -> None:
        """儲存目前設定到檔案。若傳入 config 則儲存該設定，否則從磁碟重新載入後儲存。"""
        persist_config(
            self.config_manager,
            config if config is not None else self.get_config(),
        )

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
            if self._pending_config_base is None:
                self._pending_config_base = self.config_manager.load_config()
            self._pending_config = copy.deepcopy(config)
            if self._pending_window_position is not None:
                x, y = self._pending_window_position
                self._pending_config.setdefault('window', {})['x'] = x
                self._pending_config['window']['y'] = y
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

    def _scheduler(self) -> Any:
        """
        取得提供 ``after`` / ``after_cancel`` 的排程物件。

        UI 控制器（DigitalClock）本身並非 Tk 視窗，排程方法在其 ``root`` 上；
        測試用 stub 則直接提供這兩個方法。
        """
        if hasattr(self.ui, 'after'):
            return self.ui
        return getattr(self.ui, 'root', self.ui)

    def _schedule_pending_save(self) -> None:
        """重新安排延遲儲存 callback。"""
        scheduler = self._scheduler()
        if self._save_after_id is not None:
            try:
                scheduler.after_cancel(self._save_after_id)
            except Exception as e:
                logger.debug("Cancel scheduled config save failed: %s", e)
        self._save_after_id = scheduler.after(self._save_delay_ms, self._do_save)

    def _do_save(self) -> None:
        """合併待儲存狀態，並將實際磁碟寫入交給背景 worker。"""
        self._save_after_id = None
        pending = self._pending_config
        pending_window_position = self._pending_window_position
        if pending is not None:
            base = copy.deepcopy(self._pending_config_base or pending)
            change_set = copy.deepcopy(pending)
            self._write_config_update(
                lambda latest: _apply_config_patch(
                    latest,
                    _build_config_patch(base, change_set),
                ),
            )
            self._pending_config = None
            self._pending_config_base = None
            self._pending_window_position = None
        elif pending_window_position is not None:
            x, y = pending_window_position
            self._write_config_update(
                lambda latest: self._with_window_position(latest, x, y),
            )
            self._pending_window_position = None
        else:
            self._write_config(self.get_config())

    @staticmethod
    def _with_window_position(
        config: dict[str, Any],
        x: int,
        y: int,
    ) -> dict[str, Any]:
        """套用視窗位置到最新設定副本。"""
        config.setdefault('window', {})['x'] = x
        config['window']['y'] = y
        return config

    def _write_config_update(
        self,
        update: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        """排入基於最新設定的背景更新；測試 stub 退回同步路徑。"""
        schedule_update = getattr(
            type(self.config_manager),
            'schedule_config_update',
            None,
        )
        if schedule_update is None:
            latest = self.get_config()
            self.config_manager.save_config(update(latest))
            return
        schedule_update(self.config_manager, update)

    def _write_config(self, config: dict[str, Any]) -> None:
        """由背景 writer 儲存；精簡測試 stub 退回同步相容路徑。"""
        persist_config(self.config_manager, config)

    def flush_pending_save(self) -> None:
        """立即寫入尚未落盤的設定。

        關閉程式時需要先沖刷延遲儲存，避免使用者剛變更主題、字型或視窗
        位置就關閉程式而遺失設定。
        """
        save_after_id = getattr(self, '_save_after_id', None)
        if save_after_id is not None:
            try:
                self._scheduler().after_cancel(save_after_id)
            except Exception as e:
                logger.debug("Cancel pending config save failed: %s", e)
            self._save_after_id = None

        if (
            getattr(self, '_pending_config', None) is not None
            or getattr(self, '_pending_window_position', None) is not None
        ):
            self._do_save()
        flush = getattr(self.config_manager, 'flush_config_saves', None)
        if flush is not None:
            flush()

    def _pomodoro_phase_change(self, phase: str) -> None:
        self.notify_observers(
            EventPublisher.publish(Events.POMODORO_PHASE_CHANGE, phase),
        )

    def _pomodoro_tick(self, phase: str, remaining_seconds: int) -> None:
        self.notify_observers(
            EventPublisher.publish(
                Events.POMODORO_TICK,
                phase,
                remaining_seconds,
            ),
        )

    def _pomodoro_phase_complete(self, phase: str) -> None:
        self.notify_observers(
            EventPublisher.publish(Events.POMODORO_PHASE_COMPLETE, phase),
        )

    def _pomodoro_pause_toggled(self, is_paused: bool) -> None:
        self.notify_observers(
            EventPublisher.publish(Events.POMODORO_PAUSE_TOGGLED, is_paused),
        )

    def _on_screenshot_triggered(self) -> None:
        """將截圖事件安全轉送到 Tk 主執行緒。"""
        logger.info("Screenshot shortcut triggered")
        root = getattr(self.ui, 'root', None)
        if root is not None:
            root.after(0, lambda: self.notify_observers(Events.SCREENSHOT_TRIGGERED))

    def on_close(self) -> None:
        """應用程式關閉時的清理工作。"""
        self.flush_pending_save()

        # 停止服務
        if hasattr(self, 'keyboard_service'):
            self.keyboard_service.stop()

        if hasattr(self, 'pomodoro'):
            self.pomodoro.stop()

        if hasattr(self, 'calendar_sync_service'):
            self.calendar_sync_service.stop()
        if hasattr(self.config_manager, 'close_config_writer'):
            self.config_manager.close_config_writer()

        # 關閉視窗
        if hasattr(self.ui, 'root'):
            self.ui.root.destroy()
        elif hasattr(self.ui, 'destroy'):
            self.ui.destroy()
