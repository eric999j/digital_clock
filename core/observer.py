"""Observer 設計模式基類。"""
from abc import ABC, abstractmethod
from typing import Any


class Observer(ABC):
    """觀察者抽象基類。所有觀察者必須實作 `update`。"""

    @abstractmethod
    def update(self, event: str, *args: Any, **kwargs: Any) -> None:
        """
        當被觀察對象發生變化時被呼叫。

        Args:
            event: 事件名稱
            *args: 位置參數
            **kwargs: 關鍵字參數
        """
        raise NotImplementedError

