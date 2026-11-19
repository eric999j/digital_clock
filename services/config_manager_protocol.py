"""設定管理器協定，供 ConfigStore 解耦具體實作。"""
from collections.abc import Callable
from typing import Any, Protocol


class ConfigManagerProtocol(Protocol):
    """ConfigStore 所需的最小設定介面。"""

    def load_config(self, read_only: bool = False) -> dict[str, Any]:
        """載入完整設定。"""
        ...

    def save_config(self, config: dict[str, Any]) -> None:
        """保存完整設定。"""
        ...

    def schedule_config_save(self, config: dict[str, Any]) -> None:
        """背景保存完整設定。"""
        ...

    def schedule_config_update(
        self,
        update: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        """背景套用基於最新設定的更新。"""
        ...
