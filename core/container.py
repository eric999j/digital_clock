"""依賴注入容器，用於管理服務實例。"""
from typing import Any, TypeVar

T = TypeVar('T')

class ServiceContainer:
    """簡易的依賴注入容器。"""

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}

    def register(self, name: str, service: Any) -> None:
        """
        註冊服務。

        Args:
            name: 服務名稱
            service: 服務實例
        """
        self._services[name] = service

    def get(self, name: str) -> Any:
        """
        取得服務。

        Args:
            name: 服務名稱

        Returns:
            服務實例

        Raises:
            KeyError: 如果服務未註冊
        """
        if name not in self._services:
            raise KeyError(f"Service '{name}' not found in container.")
        return self._services[name]
