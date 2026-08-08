"""TradingEngine: stream prices, ask the strategy, and execute its signals on a Broker."""

from __future__ import annotations

from decimal import Decimal

from oft.broker.base import Broker
from oft.broker.models import Order, OrderType
from oft.strategy.base import Signal, Strategy


class TradingEngine:
    def __init__(
        self,
        broker: Broker,
        strategy: Strategy,
        instrument: str,
        units: Decimal | str = "1000",
    ) -> None:
        self._broker = broker
        self._strategy = strategy
        self._instrument = instrument
        self._units = Decimal(units)
        self._signals: list[Signal] = []

    @property
    def signals(self) -> list[Signal]:
        return self._signals

    async def run(self, max_ticks: int | None = None) -> None:
        ticks = 0
        async for price in self._broker.stream_prices([self._instrument]):
            signal = self._strategy.on_price(price)
            if signal is not Signal.HOLD:
                self._signals.append(signal)
                await self._execute(signal)
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                return

    async def _execute(self, signal: Signal) -> None:
        if signal is Signal.BUY:
            await self._reconcile(self._units)
        elif signal is Signal.SELL:
            await self._reconcile(-self._units)
        elif signal is Signal.CLOSE:
            await self._reconcile(Decimal(0))

    async def _reconcile(self, target_units: Decimal) -> None:
        await self._broker.close_position(self._instrument)
        if target_units != 0:
            await self._broker.place_order(
                Order(
                    instrument=self._instrument,
                    units=target_units,
                    type=OrderType.MARKET,
                )
            )
