"""RSI mean-reversion: buy when RSI crosses down into oversold, sell into overbought."""

from __future__ import annotations

from collections import deque
from decimal import Decimal

from oft.broker.models import Price
from oft.strategy.base import Signal, Strategy


class RsiStrategy(Strategy):
    def __init__(
        self, window: int = 14, oversold: int = 30, overbought: int = 70
    ) -> None:
        if window < 2:
            raise ValueError("window must be at least 2")
        if not 0 < oversold < overbought < 100:
            raise ValueError("require 0 < oversold < overbought < 100")
        self._window = window
        self._oversold = Decimal(oversold)
        self._overbought = Decimal(overbought)
        self._gains: deque[Decimal] = deque(maxlen=window)
        self._losses: deque[Decimal] = deque(maxlen=window)
        self._prev_price: Decimal | None = None
        self._prev_rsi: Decimal | None = None

    @property
    def name(self) -> str:
        return f"rsi({self._window},{int(self._oversold)}/{int(self._overbought)})"

    def on_price(self, price: Price) -> Signal:
        mid = price.mid
        if self._prev_price is None:
            self._prev_price = mid
            return Signal.HOLD
        change = mid - self._prev_price
        self._prev_price = mid
        self._gains.append(change if change > 0 else Decimal(0))
        self._losses.append(-change if change < 0 else Decimal(0))
        if len(self._gains) < self._window:
            return Signal.HOLD
        rsi = self._rsi(sum(self._gains) / self._window, sum(self._losses) / self._window)
        signal = Signal.HOLD
        if self._prev_rsi is not None:
            if self._prev_rsi >= self._oversold and rsi < self._oversold:
                signal = Signal.BUY
            elif self._prev_rsi <= self._overbought and rsi > self._overbought:
                signal = Signal.SELL
        self._prev_rsi = rsi
        return signal

    @staticmethod
    def _rsi(avg_gain: Decimal, avg_loss: Decimal) -> Decimal:
        if avg_loss == 0:
            return Decimal(100)
        rs = avg_gain / avg_loss
        return Decimal(100) - (Decimal(100) / (Decimal(1) + rs))
