"""多時區顯示服務：管理使用者選擇的時區並計算各時區目前時間。"""
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.events import Events
from services.config_service import ConfigManager

logger = logging.getLogger(__name__)

# IANA 時區代碼 -> 顯示名稱（依大致由東至西排序）
PRESET_ZONES: dict[str, str] = {
    "Australia/Sydney": "雪梨",
    "Asia/Tokyo": "東京",
    "Asia/Seoul": "首爾",
    "Asia/Singapore": "新加坡",
    "Asia/Dubai": "杜拜",
    "Europe/Paris": "巴黎",
    "Europe/London": "倫敦",
    "UTC": "UTC",
    "America/New_York": "紐約",
    "America/Chicago": "芝加哥",
    "America/Los_Angeles": "洛杉磯",
}


@dataclass(frozen=True)
class ZoneTime:
    """單一時區的目前時間。

    Attributes:
        key: IANA 時區代碼
        label: 顯示名稱
        local_time: 該時區的目前時間（含 tzinfo）
        day_offset: 與本地日期相差的天數（-1、0、+1）
    """

    key: str
    label: str
    local_time: datetime
    day_offset: int


@cache
def _load_zone(key: str) -> ZoneInfo | None:
    """載入時區資料；系統缺少時區資料庫（Windows 未安裝 tzdata）時回傳 None。"""
    try:
        return ZoneInfo(key)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        logger.warning("找不到時區資料：%s（Windows 需安裝 tzdata 套件）", key)
        return None


class TimezoneService:
    """管理要顯示的時區清單（最多 ``MAX_ZONES`` 個）並計算各時區時間。"""

    MAX_ZONES: int = 3

    def __init__(self, config_manager: ConfigManager, notify_callback: Callable[..., None]) -> None:
        """
        初始化多時區服務。

        Args:
            config_manager: 設定管理器
            notify_callback: 通知回調函數 (event, *args)
        """
        self.config_manager = config_manager
        self.notify = notify_callback

    def available_zones(self) -> dict[str, str]:
        """回傳目前系統可用的預設時區（key -> 名稱）。"""
        return {key: label for key, label in PRESET_ZONES.items() if _load_zone(key) is not None}

    def get_selected(self, config: dict[str, Any] | None = None) -> list[str]:
        """
        取得已選時區。

        Args:
            config: 可選的設定快照；未提供時才從 ConfigManager 讀取（唯讀快取）

        Returns:
            有效、不重複且不超過上限的時區代碼清單
        """
        if config is None:
            config = self.config_manager.load_config(read_only=True)
        raw = (config.get('timezones') or {}).get('selected', [])
        selected: list[str] = []
        if isinstance(raw, list):
            for key in raw:
                if isinstance(key, str) and key in PRESET_ZONES and key not in selected:
                    selected.append(key)
        return selected[:self.MAX_ZONES]

    def toggle_zone(self, key: str) -> bool:
        """
        切換時區的顯示狀態。

        Args:
            key: IANA 時區代碼（必須是預設清單中的值）

        Returns:
            切換後該時區是否為已選；若無效或超過上限而未變更則回傳目前狀態
        """
        selected = self.get_selected()
        if key not in PRESET_ZONES:
            return False

        if key in selected:
            selected.remove(key)
        elif len(selected) >= self.MAX_ZONES or _load_zone(key) is None:
            return False
        else:
            selected.append(key)

        config = self.config_manager.load_config()
        config.setdefault('timezones', {})['selected'] = selected
        self.config_manager.save_config(config)
        self.notify(Events.TIMEZONES_UPDATED, list(selected))
        return key in selected

    def get_zone_times(
        self,
        now: datetime | None = None,
        config: dict[str, Any] | None = None,
    ) -> list[ZoneTime]:
        """
        計算所有已選時區的目前時間。

        Args:
            now: 可選的當前時間；naive 視為本機時間，帶 tzinfo 時直接作為「本地」基準
            config: 可選的設定快照

        Returns:
            依選擇順序排列的 ``ZoneTime`` 清單；無法載入的時區會被略過
        """
        base = now or datetime.now()
        local_now = base.astimezone() if base.tzinfo is None else base
        result: list[ZoneTime] = []
        for key in self.get_selected(config):
            zone = _load_zone(key)
            if zone is None:
                continue
            zone_time = local_now.astimezone(zone)
            day_offset = (zone_time.date() - local_now.date()).days
            result.append(ZoneTime(key, PRESET_ZONES[key], zone_time, day_offset))
        return result
