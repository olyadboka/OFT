"""Backtester: replay a strategy through the engine and measure the equity curve."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from oft.backtest.metrics import BacktestResult, summarize
from oft.strategy.engine import TradingEngine

if TYPE_CHECKING:
    from oft.broker.base import Broker
    from oft.broker.models import Price
    from oft.risk.base import RiskManager
    from oft.strategy.base import Strategy


class Backtester:
    def __init__(
        self,
        broker: Broker,
        strategy: Strategy,
        instrument: str,
        units: Decimal | str = "1000",
        risk: RiskManager | None = None,
    ) -> None:
        self._broker = broker
        self._instrument = instrument
        self._engine = TradingEngine(broker, strategy, instrument, units=units, risk=risk)
        self._equity: list[Decimal] = []
        self._balance: list[Decimal] = []

    @property
    def engine(self) -> TradingEngine:
        return self._engine

    async def run(self, bars: int) -> BacktestResult:
        await self._sample(None)
        await self._engine.run(max_ticks=bars, on_tick=self._sample)
        return summarize(self._equity, self._balance, bars)

    async def _sample(self, price: Price | None) -> None:
        account = await self._broker.get_account_summary()
        self._equity.append(account.margin_available + account.margin_used)
        self._balance.append(account.balance)
