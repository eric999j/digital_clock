"""休假排程服務：管理排定的休假並依日期自動切換休假模式。"""
import copy
import logging
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from core.events import Events
from services.config_service import ConfigManager
from services.pause_manager import PauseManager
from strategies.vacation_schedule_strategy import VacationScheduleStrategy

logger = logging.getLogger(__name__)


class VacationScheduleService:
    """管理排定的休假並依日期自動切換休假模式。

    - 使用者可透過 UI 新增/刪除排程（日期範圍 + 備註）。
    - 每次 tick 呼叫 `check`：當今日進入排程範圍且尚未觸發 → 自動進入休假；
      當唯一由排程觸發的休假結束且無其他 active 排程 → 自動離開休假。
    - 已完全過期的排程（`end < today`）與無效的排程於檢查時自動清除，
      比照週期提醒的自動清理機制。
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        notify_callback: Callable[[str, Any], None],
        pause_manager: PauseManager,
        pomodoro_stop_callback: Callable[[], None],
    ) -> None:
        """
        初始化休假排程服務。

        Args:
            config_manager: 設定管理器
            notify_callback: 通知回調函數 (event, *args)
            pause_manager: 暫停管理器，用來查詢/切換休假狀態
            pomodoro_stop_callback: 切換休假時停止番茄鐘的回調
        """
        self.config_manager = config_manager
        self.notify = notify_callback
        self.pause_manager = pause_manager
        self.pomodoro_stop = pomodoro_stop_callback
        self.strategy = VacationScheduleStrategy()

    @property
    def config(self) -> dict[str, Any]:
        return self.config_manager.load_config()

    def list_schedules(self) -> list[dict[str, Any]]:
        """回傳所有排程的淺拷貝清單。"""
        return list(self.config.get('vacation_schedules', []))

    def add_schedule(
        self,
        start: str | date,
        end: str | date,
        note: str = "",
    ) -> dict[str, Any]:
        """
        新增排程。

        Args:
            start: 起始日期（ISO 字串或 `date` 物件）
            end: 結束日期（ISO 字串或 `date` 物件）
            note: 備註

        Returns:
            新增後的排程字典。

        Raises:
            ValueError: 日期格式無效或結束早於開始。
        """
        start_str = self._to_iso(start)
        end_str = self._to_iso(end)
        if start_str is None or end_str is None:
            raise ValueError("日期格式無效")
        if end_str < start_str:
            raise ValueError("結束日期不可早於開始日期")

        schedule: dict[str, Any] = {
            'start': start_str,
            'end': end_str,
            'note': (note or "").strip(),
            'auto_started': False,
        }
        config = self.config
        schedules = config.setdefault('vacation_schedules', [])
        schedules.append(schedule)
        schedules.sort(key=lambda s: (s.get('start', ''), s.get('end', '')))
        self.config_manager.save_config(config)
        self.notify(Events.VACATION_SCHEDULE_ADDED, schedule)
        return schedule

    def delete_schedule(self, schedule_to_delete: dict[str, Any]) -> None:
        """
        刪除排程。

        以「start/end/note 相同」做比對，僅移除第一筆相符的排程。
        """
        config = self.config
        schedules = config.get('vacation_schedules', [])
        for idx, existing in enumerate(schedules):
            if self._matches(existing, schedule_to_delete):
                removed = schedules.pop(idx)
                self.config_manager.save_config(config)
                self.notify(Events.VACATION_SCHEDULE_DELETED, removed)
                return

    def check(
        self,
        now: datetime | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        """
        檢查排程並在需要時觸發休假狀態轉換與清理過期排程。

        Args:
            now: 可選的當前時間快照
            config: 可選的設定快照（用來快速判斷是否需處理；實際修改仍會重新載入）。
        """
        current = now or datetime.now()
        today = current.date()

        # 快速跳出：若快照顯示無排程則直接返回，避免多餘的 load
        if config is not None and not config.get('vacation_schedules'):
            return

        # 使用同一輪檢查已取得的快照，複製一份供 auto_started 標記與清理使用。
        # 這樣可避免每秒再次 stat/load 設定檔，也不會修改 ConfigManager 的唯讀快取。
        config_data = copy.deepcopy(config) if config is not None else self.config
        schedules = config_data.get('vacation_schedules', [])
        if not schedules:
            return

        classification = self.strategy.check(schedules, today)
        expired = classification['expired']
        active = classification['active']
        future = classification['future']
        invalid = classification['invalid']

        # 記錄「有 auto_started 標記」的過期排程，代表當前休假可能由排程觸發
        expired_had_auto_started = any(s.get('auto_started') for s in expired)

        # 標記今日新進入的排程；避免同 tick 循環進入與離開後再次自動進入
        newly_marked: list[dict[str, Any]] = []
        for schedule in active:
            if not schedule.get('auto_started'):
                schedule['auto_started'] = True
                newly_marked.append(schedule)

        current_on_vacation = self.pause_manager.get_pause_state(
            'vacation', config=config_data
        )
        vacation_source = self.pause_manager.get_vacation_source(config=config_data)

        should_enter = bool(newly_marked) and not current_on_vacation
        should_exit = (
            expired_had_auto_started
            and current_on_vacation
            and not active
            and vacation_source == 'schedule'
        )

        removed_any = bool(expired) or bool(invalid)
        config_changed = removed_any or bool(newly_marked)

        if config_changed:
            remaining = active + future
            remaining.sort(key=lambda s: (s.get('start', ''), s.get('end', '')))
            config_data['vacation_schedules'] = remaining
            self.config_manager.save_config(config_data)
            self.notify(Events.VACATION_SCHEDULE_UPDATED, remaining)

        # 觸發狀態變更（呼叫 toggle_vacation 會再次讀寫 config，故放在最後）
        if should_enter:
            self.pause_manager.toggle_vacation(self.pomodoro_stop, source='schedule')
        elif should_exit:
            self.pause_manager.toggle_vacation(self.pomodoro_stop, source='schedule')

    @staticmethod
    def _to_iso(value: str | date) -> str | None:
        """將輸入轉為 ISO 格式日期字串（YYYY-MM-DD）；失敗回傳 None。"""
        try:
            if isinstance(value, date) and not isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, datetime):
                return value.date().isoformat()
            return date.fromisoformat(str(value)).isoformat()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _matches(a: dict[str, Any], b: dict[str, Any]) -> bool:
        """以 start/end/note 三欄比對兩筆排程是否相同。"""
        keys = ('start', 'end', 'note')
        return all(a.get(k) == b.get(k) for k in keys)
