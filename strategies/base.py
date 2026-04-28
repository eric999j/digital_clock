"""策略模式基礎介面。"""
from abc import ABC, abstractmethod
from typing import Any


class BaseStrategy(ABC):  # noqa: B024 - 標記類別，子類各自宣告抽象方法
    """策略基礎抽象類別（標記用途，子類自訂主要方法）。"""


class CheckStrategy(BaseStrategy):
    """需要週期性檢查條件的策略基類。"""

    @abstractmethod
    def check(self, *args: Any, **kwargs: Any) -> Any:
        """檢查是否滿足觸發條件。"""
        raise NotImplementedError


class PhaseStrategy(BaseStrategy):
    """負責計算下一個階段的策略基類。"""

    @abstractmethod
    def next_phase(self, *args: Any, **kwargs: Any) -> Any:
        """根據當前狀態回傳下一個階段。"""
        raise NotImplementedError

