"""TradingEngine: stream prices, ask the strategy, size via risk, and execute on a Broker."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from oft.broker.base import Broker
from oft.broker.models import Order, OrderType
from oft.strategy.base import Signal, Strategy

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from oft.broker.models import Price
    from oft.risk.base import RiskDecision, RiskManager

    OnTick = Callable[[Price], Awaitable[None]]


class TradingEngine:
    def __init__(
        self,
        broker: Broker,
        strategy: Strategy,
        instrument: str,
        units: Decimal | str = "1000",
        risk: RiskManager | None = None,
    ) -> None:
        self._broker = broker
        self._strategy = strategy
        self._instrument = instrument
        self._units = Decimal(units)
        self._risk = risk
        self._signals: list[Signal] = []
        self._decisions: list[RiskDecision] = []

    @property
    def signals(self) -> list[Signal]:
        return self._signals

    @property
    def decisions(self) -> list[RiskDecision]:
        return self._decisions

    async def run(
        self, max_ticks: int | None = None, on_tick: OnTick | None = None
    ) -> None:
        ticks = 0
        async for price in self._broker.stream_prices([self._instrument]):
            signal = self._strategy.on_price(price)
            if signal is not Signal.HOLD:
                self._signals.append(signal)
                await self._execute(signal, price)
            if on_tick is not None:
                await on_tick(price)
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                return

    async def _execute(self, signal: Signal, price: Price) -> None:
        target = await self._target_units(signal, price)
        if target is not None:
            await self._reconcile(target)

    async def _target_units(self, signal: Signal, price: Price) -> Decimal | None:
        if self._risk is None:
            if signal is Signal.BUY:
                return self._units
            if signal is Signal.SELL:
                return -self._units
            return Decimal(0)
        account = await self._broker.get_account_summary()
        decision = self._risk.evaluate(signal, account, price)
        self._decisions.append(decision)
        return decision.target_units if decision.approved else None

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
