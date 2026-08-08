"""SimBroker: a self-contained paper-trading Broker driven by synthetic prices."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from math import exp, sqrt
from random import Random

from oft.broker.base import Broker
from oft.broker.models import (
    AccountSummary,
    Candle,
    Order,
    OrderResult,
    OrderType,
    Price,
)

_PRICE_Q = Decimal("0.00001")
_MONEY_Q = Decimal("0.01")
_GRANULARITY = {
    "S5": 5,
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "H1": 3600,
    "H4": 14400,
    "D": 86400,
}


@dataclass
class _Holding:
    units: Decimal
    avg_price: Decimal


class SimBroker(Broker):
    def __init__(
        self,
        *,
        balance: str = "100000",
        currency: str = "USD",
        instruments: dict[str, str] | None = None,
        spread: str = "0.00012",
        volatility: float = 0.0005,
        drift: float = 0.0,
        leverage: int = 30,
        tick_seconds: float = 1.0,
        seed: int | None = None,
        account_id: str = "sim-account",
    ) -> None:
        self._balance = Decimal(balance)
        self._currency = currency
        self._spread = Decimal(spread)
        self._vol = volatility
        self._drift = drift
        self._leverage = leverage
        self._tick_seconds = tick_seconds
        self._account_id = account_id
        self._rng = Random(seed)
        self._mids: dict[str, Decimal] = {
            name: Decimal(px)
            for name, px in (instruments or {"EUR_USD": "1.10000"}).items()
        }
        self._holdings: dict[str, _Holding] = {}
        self._brackets: dict[str, tuple[Decimal | None, Decimal | None]] = {}
        self._order_seq = 0

    async def get_account_summary(self) -> AccountSummary:
        unrealized = sum(
            (self._mids[name] - h.avg_price) * h.units
            for name, h in self._holdings.items()
        )
        margin_used = sum(
            abs(h.units) * h.avg_price / self._leverage
            for h in self._holdings.values()
        )
        equity = self._balance + Decimal(unrealized)
        available = max(Decimal(0), equity - Decimal(margin_used))
        return AccountSummary(
            account_id=self._account_id,
            currency=self._currency,
            balance=self._balance.quantize(_MONEY_Q, ROUND_HALF_UP),
            margin_used=Decimal(margin_used).quantize(_MONEY_Q, ROUND_HALF_UP),
            margin_available=available.quantize(_MONEY_Q, ROUND_HALF_UP),
            open_position_count=len(self._holdings),
        )

    async def get_candles(
        self, instrument: str, granularity: str, count: int
    ) -> list[Candle]:
        self._require(instrument)
        if granularity not in _GRANULARITY:
            raise ValueError(f"unknown granularity: {granularity!r}")
        step = timedelta(seconds=_GRANULARITY[granularity])
        now = self._now()
        points = self._simulate(float(self._mids[instrument]), count + 1)
        candles: list[Candle] = []
        for i in range(count):
            open_ = Decimal(str(points[i]))
            close = Decimal(str(points[i + 1]))
            high = max(open_, close) * (Decimal(1) + Decimal("0.0003"))
            low = min(open_, close) * (Decimal(1) - Decimal("0.0003"))
            candles.append(
                Candle(
                    time=now - step * (count - i),
                    open=open_.quantize(_PRICE_Q),
                    high=high.quantize(_PRICE_Q),
                    low=low.quantize(_PRICE_Q),
                    close=close.quantize(_PRICE_Q),
                    volume=self._rng.randint(50, 500),
                )
            )
        return candles

    async def stream_prices(self, instruments: list[str]) -> AsyncIterator[Price]:
        for name in instruments:
            self._require(name)
        while True:
            for name in instruments:
                self._advance(name)
                self._check_brackets(name)
                yield self._quote(name)
            await asyncio.sleep(self._tick_seconds)

    async def place_order(self, order: Order) -> OrderResult:
        self._require(order.instrument)
        quote = self._quote(order.instrument)
        fill_price = self._match(order, quote)
        if fill_price is None:
            return OrderResult(order_id=self._next_id(), filled=False, time=self._now())
        self._apply_fill(order.instrument, order.units, fill_price)
        self._set_bracket(order)
        return OrderResult(
            order_id=self._next_id(),
            filled=True,
            fill_price=fill_price,
            time=self._now(),
        )

    async def close_position(self, instrument: str) -> OrderResult:
        holding = self._holdings.get(instrument)
        if holding is None:
            return OrderResult(order_id=self._next_id(), filled=False, time=self._now())
        return await self.place_order(
            Order(instrument=instrument, units=-holding.units, type=OrderType.MARKET)
        )

    def _match(self, order: Order, quote: Price) -> Decimal | None:
        if order.type is OrderType.MARKET:
            return quote.ask if order.units > 0 else quote.bid
        if order.units > 0 and quote.ask <= order.price:
            return order.price
        if order.units < 0 and quote.bid >= order.price:
            return order.price
        return None

    def _apply_fill(self, instrument: str, units: Decimal, price: Decimal) -> Decimal:
        holding = self._holdings.get(instrument)
        old_units = holding.units if holding else Decimal(0)
        old_avg = holding.avg_price if holding else Decimal(0)
        new_units = old_units + units
        realized = Decimal(0)
        if old_units == 0 or (old_units > 0) == (units > 0):
            new_avg = (
                (old_avg * abs(old_units) + price * abs(units)) / abs(new_units)
                if new_units != 0
                else Decimal(0)
            )
        else:
            closing = min(abs(units), abs(old_units))
            direction = Decimal(1) if old_units > 0 else Decimal(-1)
            realized = (price - old_avg) * closing * direction
            new_avg = old_avg if abs(units) <= abs(old_units) else price
        self._balance += realized
        if new_units == 0:
            self._holdings.pop(instrument, None)
            self._brackets.pop(instrument, None)
        else:
            self._holdings[instrument] = _Holding(
                units=new_units, avg_price=new_avg.quantize(_PRICE_Q, ROUND_HALF_UP)
            )
        return realized

    def _set_bracket(self, order: Order) -> None:
        if order.instrument not in self._holdings:
            self._brackets.pop(order.instrument, None)
        elif order.stop_loss is not None or order.take_profit is not None:
            self._brackets[order.instrument] = (order.stop_loss, order.take_profit)

    def _check_brackets(self, instrument: str) -> None:
        bracket = self._brackets.get(instrument)
        holding = self._holdings.get(instrument)
        if bracket is None or holding is None:
            return
        stop_loss, take_profit = bracket
        quote = self._quote(instrument)
        if holding.units > 0:
            price = quote.bid
            hit = (stop_loss is not None and price <= stop_loss) or (
                take_profit is not None and price >= take_profit
            )
        else:
            price = quote.ask
            hit = (stop_loss is not None and price >= stop_loss) or (
                take_profit is not None and price <= take_profit
            )
        if hit:
            self._apply_fill(instrument, -holding.units, price)

    def _advance(self, instrument: str) -> None:
        current = float(self._mids[instrument])
        moved = current * self._gbm_factor()
        self._mids[instrument] = Decimal(str(moved)).quantize(_PRICE_Q, ROUND_HALF_UP)

    def _simulate(self, start: float, n: int) -> list[float]:
        series = []
        value = start
        for _ in range(n):
            series.append(value)
            value *= self._gbm_factor()
        return series

    def _gbm_factor(self) -> float:
        shock = self._rng.gauss(0.0, 1.0)
        return exp((self._drift - 0.5 * self._vol**2) + self._vol * sqrt(1.0) * shock)

    def _quote(self, instrument: str) -> Price:
        mid = self._mids[instrument]
        half = self._spread / 2
        return Price(
            instrument=instrument,
            time=self._now(),
            bid=(mid - half).quantize(_PRICE_Q, ROUND_HALF_UP),
            ask=(mid + half).quantize(_PRICE_Q, ROUND_HALF_UP),
        )

    def _require(self, instrument: str) -> None:
        if instrument not in self._mids:
            raise ValueError(f"unknown instrument: {instrument!r}")

    def _next_id(self) -> str:
        self._order_seq += 1
        return f"sim-{self._order_seq}"

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)
