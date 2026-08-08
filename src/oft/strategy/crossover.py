"""SMA crossover: buy when the fast average crosses above the slow one, sell when below."""

from __future__ import annotations

from collections import deque
from decimal import Decimal

from oft.broker.models import Price
from oft.strategy.base import Signal, Strategy


class SmaCrossover(Strategy):
    def __init__(self, fast: int, slow: int) -> None:
        if fast >= slow:
            raise ValueError("fast window must be shorter than slow window")
        self._fast = fast
        self._slow = slow
        self._prices: deque[Decimal] = deque(maxlen=slow)
        self._fast_above: bool | None = None

    @property
    def name(self) -> str:
        return f"sma-crossover({self._fast}/{self._slow})"

    def on_price(self, price: Price) -> Signal:
        self._prices.append(price.mid)
        if len(self._prices) < self._slow:
            return Signal.HOLD
        window = list(self._prices)
        fast_avg = sum(window[-self._fast :]) / self._fast
        slow_avg = sum(window) / self._slow
        fast_above = fast_avg > slow_avg
        signal = Signal.HOLD
        if self._fast_above is not None and fast_above != self._fast_above:
            signal = Signal.BUY if fast_above else Signal.SELL
        self._fast_above = fast_above
        return signal
