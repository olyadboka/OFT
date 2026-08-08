from decimal import Decimal

import pytest

from oft.broker import Broker, OrderResult, Price, SimBroker
from oft.strategy import Signal, SmaCrossover, Strategy, TradingEngine


def _price(mid):
    return Price(instrument="X", time="2026-08-08T12:00:00", bid=str(mid), ask=str(mid))


class _RecordingBroker(Broker):
    def __init__(self, mids):
        self._mids = [Decimal(str(m)) for m in mids]
        self.orders = []
        self.closes = []

    async def get_account_summary(self):
        raise NotImplementedError

    async def get_candles(self, instrument, granularity, count):
        raise NotImplementedError

    async def stream_prices(self, instruments):
        for mid in self._mids:
            yield _price(mid)

    async def place_order(self, order):
        self.orders.append(order)
        return OrderResult(
            order_id="rec", filled=True, fill_price=Decimal("1"), time="2026-08-08T12:00:00"
        )

    async def close_position(self, instrument):
        self.closes.append(instrument)
        return OrderResult(order_id="rec", filled=False, time="2026-08-08T12:00:00")


def test_crossover_requires_fast_shorter_than_slow():
    with pytest.raises(ValueError):
        SmaCrossover(fast=5, slow=5)


def test_crossover_holds_until_warmed_up():
    strat = SmaCrossover(fast=2, slow=3)
    assert strat.on_price(_price(1)) is Signal.HOLD
    assert strat.on_price(_price(1)) is Signal.HOLD


def test_crossover_emits_buy_then_sell():
    strat = SmaCrossover(fast=2, slow=3)
    signals = [strat.on_price(_price(m)) for m in [1, 1, 1, 2, 3, 2, 1]]
    non_hold = [s for s in signals if s is not Signal.HOLD]
    assert non_hold == [Signal.BUY, Signal.SELL]


def test_strategy_is_a_strategy_with_a_name():
    strat = SmaCrossover(fast=2, slow=5)
    assert isinstance(strat, Strategy)
    assert "sma-crossover" in strat.name


async def test_engine_executes_signals_on_any_broker():
    broker = _RecordingBroker([1, 1, 1, 2, 3, 2, 1])
    engine = TradingEngine(broker, SmaCrossover(fast=2, slow=3), "X", units="1000")
    await engine.run()
    assert engine.signals == [Signal.BUY, Signal.SELL]
    assert [o.units for o in broker.orders] == [Decimal("1000"), Decimal("-1000")]
    assert broker.closes == ["X", "X"]


async def test_engine_holds_when_no_crossover():
    broker = _RecordingBroker([1, 1, 1, 1, 1])
    engine = TradingEngine(broker, SmaCrossover(fast=2, slow=3), "X")
    await engine.run()
    assert engine.signals == []
    assert broker.orders == []


async def test_engine_respects_max_ticks():
    broker = SimBroker(seed=3, tick_seconds=0)
    engine = TradingEngine(broker, SmaCrossover(fast=3, slow=8), "EUR_USD", units="1000")
    await engine.run(max_ticks=50)
    assert isinstance(engine.signals, list)
