from decimal import Decimal

import pytest
from pydantic import ValidationError

from oft.broker import Order, OrderType, SimBroker


async def _run_until_flat(broker, instrument, max_ticks=500):
    ticks = 0
    async for _ in broker.stream_prices([instrument]):
        summary = await broker.get_account_summary()
        if summary.open_position_count == 0:
            return True
        ticks += 1
        if ticks >= max_ticks:
            return False
    return False


def test_order_accepts_brackets():
    order = Order(
        instrument="X", units="1000", type=OrderType.MARKET,
        stop_loss="0.99000", take_profit="1.02000",
    )
    assert order.stop_loss == Decimal("0.99000")
    assert order.take_profit == Decimal("1.02000")


def test_order_rejects_non_positive_bracket():
    with pytest.raises(ValidationError):
        Order(instrument="X", units="1000", type=OrderType.MARKET, stop_loss="0")


async def test_stop_loss_closes_long_at_a_loss():
    broker = SimBroker(
        volatility=0.0, drift=-0.001, spread="0", tick_seconds=0,
        instruments={"X": "1.00000"},
    )
    await broker.place_order(
        Order(instrument="X", units="1000", type=OrderType.MARKET, stop_loss="0.99000")
    )
    assert await _run_until_flat(broker, "X")
    summary = await broker.get_account_summary()
    assert summary.open_position_count == 0
    assert summary.balance < Decimal("100000")


async def test_take_profit_closes_long_at_a_gain():
    broker = SimBroker(
        volatility=0.0, drift=0.001, spread="0", tick_seconds=0,
        instruments={"X": "1.00000"},
    )
    await broker.place_order(
        Order(instrument="X", units="1000", type=OrderType.MARKET, take_profit="1.01000")
    )
    assert await _run_until_flat(broker, "X")
    summary = await broker.get_account_summary()
    assert summary.balance > Decimal("100000")


async def test_stop_loss_closes_short_at_a_loss():
    broker = SimBroker(
        volatility=0.0, drift=0.001, spread="0", tick_seconds=0,
        instruments={"X": "1.00000"},
    )
    await broker.place_order(
        Order(instrument="X", units="-1000", type=OrderType.MARKET, stop_loss="1.01000")
    )
    assert await _run_until_flat(broker, "X")
    summary = await broker.get_account_summary()
    assert summary.balance < Decimal("100000")


async def test_no_bracket_means_no_auto_close():
    broker = SimBroker(
        volatility=0.0, drift=-0.001, spread="0", tick_seconds=0,
        instruments={"X": "1.00000"},
    )
    await broker.place_order(Order(instrument="X", units="1000", type=OrderType.MARKET))
    assert not await _run_until_flat(broker, "X", max_ticks=50)
