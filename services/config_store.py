"""設定快照與型別化常用欄位。"""
import copy
from dataclasses import dataclass
from typing import Any

from services.config_manager_protocol import ConfigManagerProtocol


@dataclass(frozen=True)
class WindowConfig:
    """時鐘視窗設定。"""

    x: int | None
    y: int
    width: int
    height: int
    alpha_focused: float
    alpha_unfocused: float


@dataclass(frozen=True)
class AppearanceConfig:
    """時鐘外觀設定。"""

    font_family: str
    font_size: int
    theme: str
    time_format: str
    date_format: str
    corner_radius: int


@dataclass(frozen=True)
class ConfigSnapshot:
    """型別化設定快照，同時保留完整 dict 相容性。"""

    raw: dict[str, Any]
    window: WindowConfig
    appearance: AppearanceConfig

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "ConfigSnapshot":
        """建立快照；raw 為獨立深拷貝。"""
        raw = copy.deepcopy(config)
        window = raw.get("window", {})
        appearance = raw.get("appearance", {})
        return cls(
            raw=raw,
            window=WindowConfig(
                x=window.get("x"),
                y=int(window.get("y", 0)),
                width=int(window.get("width", 200)),
                height=int(window.get("height", 70)),
                alpha_focused=float(window.get("alpha_focused", 1.0)),
                alpha_unfocused=float(window.get("alpha_unfocused", 0.5)),
            ),
            appearance=AppearanceConfig(
                font_family=str(appearance.get("font_family", "Arial")),
                font_size=int(appearance.get("font_size", 56)),
                theme=str(appearance.get("theme", "blue")),
                time_format=str(appearance.get("time_format", "24h")),
                date_format=str(appearance.get("date_format", "full")),
                corner_radius=int(appearance.get("corner_radius", 30)),
            ),
        )

    def mutable(self) -> dict[str, Any]:
        """回傳可供既有 UI 與服務使用的獨立字典。"""
        return copy.deepcopy(self.raw)


class ConfigStore:
    """集中建立設定快照，避免各層自行假設巢狀字典型別。"""

    def __init__(self, manager: ConfigManagerProtocol) -> None:
        self.manager = manager

    def snapshot(self, read_only: bool = False) -> ConfigSnapshot:
        """
        由持久化來源建立目前設定快照。

        Args:
            read_only: 是否請 manager 使用其唯讀快取
        """
        return ConfigSnapshot.from_dict(self.manager.load_config(read_only=read_only))

    def mutable(self) -> dict[str, Any]:
        """回傳目前設定的可修改副本。"""
        return self.snapshot().mutable()


def persist_config(manager: ConfigManagerProtocol, config: dict[str, Any]) -> None:
    """
    使用共用背景 worker 儲存；測試替身仍走既有同步介面。

    Args:
        manager: 設定管理器或測試替身
        config: 要保存的完整設定
    """
    schedule = getattr(type(manager), "schedule_config_save", None)
    if schedule is not None:
        schedule(manager, config)
        return
    manager.save_config(config)
