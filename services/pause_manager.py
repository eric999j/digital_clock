"""暫停狀態管理器，以來源集合管理手動與自動暫停。"""
from collections.abc import Callable
from typing import Any

from core.events import Events
from core.pause_policy import MANUAL_SOURCE, PAUSE_KEYS, PausePolicy, PauseState
from services.config_service import ConfigManager


class PauseManager:
    """管理提醒、整點啟動與休假的暫停來源。

    ``pause_sources`` 是設定檔中的可持久化真實狀態；舊版布林欄位仍會同步
    寫入，讓既有設定、服務與舊版本程式可安全共存。
    """

    _PAUSE_KEYS = PAUSE_KEYS
    _MANUAL = MANUAL_SOURCE

    def __init__(self, config_manager: ConfigManager, notify_callback: Callable[[str, Any], None]) -> None:
        self.config_manager = config_manager
        self.notify = notify_callback
        self._pomodoro_stop: Callable[[], None] = lambda: None

    def set_pomodoro_stop(self, callback: Callable[[], None]) -> None:
        """設定休假剛開始時應停止的番茄鐘回呼。"""
        self._pomodoro_stop = callback

    @property
    def config(self) -> dict[str, Any]:
        """取得可修改的設定副本。"""
        return self.config_manager.load_config()

    @classmethod
    def _legacy_pause_sources(cls, config: dict[str, Any]) -> dict[str, set[str]]:
        """由舊版布林欄位推導來源，不就地修改傳入的唯讀快照。"""
        return PausePolicy.from_config(config).pause_sources

    @staticmethod
    def _vacation_sources(config: dict[str, Any]) -> set[str]:
        return PausePolicy.vacation_sources_from_config(config)

    def _sync_legacy_fields(
        self, config: dict[str, Any], pause_sources: dict[str, set[str]], vacation_sources: set[str],
    ) -> None:
        """同步新來源集合與舊版讀取欄位。"""
        config['pause_sources'] = {key: sorted(sources) for key, sources in pause_sources.items()}
        config['vacation_sources'] = sorted(vacation_sources)
        config['reminder_paused'] = bool(pause_sources['reminder'])
        config.setdefault('hourly_web_reminder', {})['paused'] = bool(pause_sources['hourly_web'])
        config['on_vacation'] = bool(vacation_sources)
        if vacation_sources:
            # 僅供舊版程式與設定檔相容；新碼須使用 has_vacation_source。
            config['on_vacation_source'] = sorted(vacation_sources)[0]
        else:
            config.pop('on_vacation_source', None)

    def get_pause_state(self, key: str, config: dict[str, Any] | None = None) -> bool:
        """回傳功能是否至少被一個來源暫停。"""
        config_data = config if config is not None else self.config
        if key == 'vacation':
            return bool(self._vacation_sources(config_data))
        if key in self._PAUSE_KEYS:
            return bool(self._legacy_pause_sources(config_data)[key])
        return False

    def set_pause_state(self, key: str, paused: bool) -> None:
        """新增或移除指定功能的手動暫停來源。"""
        if key not in self._PAUSE_KEYS:
            return
        config = self.config
        state = self._state_from(config)
        sources = state.pause_sources
        vacation_sources = state.vacation_sources
        was_paused = bool(sources[key])
        state.set_pause_source(key, paused)
        is_paused = bool(sources[key])
        self._sync_legacy_fields(config, sources, vacation_sources)
        self.config_manager.save_config(config)
        if was_paused != is_paused:
            event = Events.REMINDER_PAUSE_TOGGLED if key == 'reminder' else Events.HOURLY_WEB_PAUSE_TOGGLED
            self.notify(event, is_paused)

    def toggle_pause(self, key: str) -> None:
        """切換指定功能的手動暫停來源。"""
        if key not in self._PAUSE_KEYS:
            return
        sources = self._legacy_pause_sources(self.config)
        self.set_pause_state(key, self._MANUAL not in sources[key])

    def set_vacation_source(self, source: str, active: bool) -> None:
        """新增或移除一個休假來源，且只影響該來源。

        休假有效時會以 ``vacation`` 來源暫停提醒與整點啟動；最後一個
        休假來源移除後才會解除這個共同來源，不會覆蓋使用者的手動暫停。
        """
        source = source.strip() or self._MANUAL
        config = self.config
        state = self._state_from(config)
        sources = state.pause_sources
        vacation_sources = state.vacation_sources
        was_vacation = bool(vacation_sources)
        before = {key: bool(sources[key]) for key in self._PAUSE_KEYS}
        state.set_vacation_source(source, active)
        is_vacation = bool(vacation_sources)
        self._sync_legacy_fields(config, sources, vacation_sources)
        self.config_manager.save_config(config)

        for key in self._PAUSE_KEYS:
            after = bool(sources[key])
            if before[key] != after:
                event = Events.REMINDER_PAUSE_TOGGLED if key == 'reminder' else Events.HOURLY_WEB_PAUSE_TOGGLED
                self.notify(event, after)
        if was_vacation != is_vacation:
            if is_vacation:
                self._pomodoro_stop()
            self.notify(Events.VACATION_TOGGLED, is_vacation)

    def toggle_vacation(self, source: str = _MANUAL) -> None:
        """切換指定來源的休假狀態。

        使用者按下全域「休假」開關時，若目前只由自動來源持有休假，
        視為明確手動結束，會釋放那些自動來源；其後各服務的去重狀態
        會避免在同一個事件／排程區間立刻重新取得。
        """
        current = self._vacation_sources(self.config)
        if source == self._MANUAL and self._MANUAL not in current and current:
            for held_source in tuple(current):
                self.set_vacation_source(held_source, False)
            return
        self.set_vacation_source(source, source not in current)

    def has_vacation_source(self, source: str, config: dict[str, Any] | None = None) -> bool:
        """回傳某個來源是否仍持有休假狀態。"""
        config_data = config if config is not None else self.config
        return source in self._vacation_sources(config_data)

    def get_vacation_source(self, config: dict[str, Any] | None = None) -> str | None:
        """相容舊 API：只有單一來源時回傳該來源。"""
        config_data = config if config is not None else self.config
        sources = self._vacation_sources(config_data)
        return next(iter(sources)) if len(sources) == 1 else None

    def _state_from(self, config: dict[str, Any]) -> PauseState:
        """建立來源狀態並同步升級後的持久化欄位。"""
        state = PausePolicy.from_config(config)
        config['pause_sources'] = {
            key: sorted(sources)
            for key, sources in state.pause_sources.items()
        }
        config['vacation_sources'] = sorted(state.vacation_sources)
        config.pop('vacation_previous_state', None)
        return state
