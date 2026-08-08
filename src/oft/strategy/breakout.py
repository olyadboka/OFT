"""Donchian breakout: buy on a new N-period high, sell on a new N-period low."""

from __future__ import annotations

from collections import deque
from decimal import Decimal

from oft.broker.models import Price
from oft.strategy.base import Signal, Strategy


class Breakout(Strategy):
    def __init__(self, window: int = 20) -> None:
        if window < 2:
            raise ValueError("window must be at least 2")
        self._window = window
        self._prices: deque[Decimal] = deque(maxlen=window)

    @property
    def name(self) -> str:
        return f"breakout({self._window})"

    def on_price(self, price: Price) -> Signal:
        mid = price.mid
        if len(self._prices) < self._window:
            self._prices.append(mid)
            return Signal.HOLD
        highest = max(self._prices)
        lowest = min(self._prices)
        self._prices.append(mid)
        if mid > highest:
            return Signal.BUY
        if mid < lowest:
            return Signal.SELL
        return Signal.HOLD
