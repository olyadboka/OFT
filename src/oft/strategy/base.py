"""Strategy contract: turn market data into trading signals, with no side effects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from oft.broker.models import Price


class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"
    HOLD = "HOLD"


class Strategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def on_price(self, price: Price) -> Signal: ...
