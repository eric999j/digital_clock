"""暫停與勿擾來源的純狀態政策。"""
from dataclasses import dataclass, field
from typing import Any

PAUSE_KEYS = ('reminder', 'hourly_web')
MANUAL_SOURCE = 'manual'
VACATION_SOURCE = 'vacation'


@dataclass
class PauseState:
    """提醒、整點啟動與勿擾的來源集合。"""

    pause_sources: dict[str, set[str]] = field(default_factory=dict)
    vacation_sources: set[str] = field(default_factory=set)

    def set_pause_source(self, key: str, paused: bool) -> None:
        """新增或移除指定功能的手動來源。"""
        if key not in self.pause_sources:
            return
        if paused:
            self.pause_sources[key].add(MANUAL_SOURCE)
        else:
            self.pause_sources[key].discard(MANUAL_SOURCE)

    def set_vacation_source(self, source: str, active: bool) -> None:
        """更新單一勿擾來源並同步兩項功能的共同暫停來源。"""
        normalized = source.strip() or MANUAL_SOURCE
        if active:
            self.vacation_sources.add(normalized)
        else:
            self.vacation_sources.discard(normalized)
        if self.vacation_sources:
            for sources in self.pause_sources.values():
                sources.add(VACATION_SOURCE)
        else:
            for sources in self.pause_sources.values():
                sources.discard(VACATION_SOURCE)


class PausePolicy:
    """由持久化設定推導並更新來源集合。"""

    @staticmethod
    def from_config(config: dict[str, Any]) -> PauseState:
        """依新來源集合或舊版布林快照建立狀態。"""
        raw_pause_sources = config.get('pause_sources')
        if isinstance(raw_pause_sources, dict):
            pause_sources = {
                key: {
                    str(source)
                    for source in raw_pause_sources.get(key, [])
                    if isinstance(source, str)
                }
                for key in PAUSE_KEYS
            }
            inconsistent = (
                (
                    config.get('on_vacation', False)
                    and not any(
                        VACATION_SOURCE in sources
                        for sources in pause_sources.values()
                    )
                )
                or (
                    config.get('reminder_paused', False)
                    and not pause_sources['reminder']
                )
                or (
                    config.get('hourly_web_reminder', {}).get('paused', False)
                    and not pause_sources['hourly_web']
                )
            )
            if not inconsistent:
                return PauseState(
                    pause_sources,
                    PausePolicy.vacation_sources_from_config(config),
                )

        vacation_active = bool(config.get('on_vacation', False))
        previous = config.get('vacation_previous_state', {})
        pause_sources = {key: set() for key in PAUSE_KEYS}
        reminder_manual = (
            bool(previous.get('reminder_paused', False))
            if vacation_active
            else bool(config.get('reminder_paused', False))
        )
        hourly_manual = (
            bool(previous.get('hourly_web_paused', False))
            if vacation_active
            else bool(
                config.get('hourly_web_reminder', {}).get('paused', False)
            )
        )
        if reminder_manual:
            pause_sources['reminder'].add(MANUAL_SOURCE)
        if hourly_manual:
            pause_sources['hourly_web'].add(MANUAL_SOURCE)
        if vacation_active:
            for sources in pause_sources.values():
                sources.add(VACATION_SOURCE)
        return PauseState(
            pause_sources,
            PausePolicy.vacation_sources_from_config(config),
        )

    @staticmethod
    def vacation_sources_from_config(config: dict[str, Any]) -> set[str]:
        """由來源集合或舊版單一來源推導勿擾來源。"""
        raw = config.get('vacation_sources')
        if isinstance(raw, list) and (
            raw or not config.get('on_vacation', False)
        ):
            return {
                str(source)
                for source in raw
                if isinstance(source, str)
            }
        if config.get('on_vacation', False):
            return {str(config.get('on_vacation_source') or MANUAL_SOURCE)}
        return set()
