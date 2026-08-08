from decimal import Decimal

import pytest

from oft.broker import Broker, Order, OrderType, SimBroker


def _broker(**overrides):
    config = dict(seed=42, tick_seconds=0)
    config.update(overrides)
    return SimBroker(**config)


async def _collect(broker, instrument, n):
    prices = []
    async for price in broker.stream_prices([instrument]):
        prices.append(price.mid)
        if len(prices) == n:
            break
    return prices


async def test_simbroker_satisfies_broker_interface():
    assert isinstance(_broker(), Broker)


async def test_initial_account_is_flat():
    summary = await _broker().get_account_summary()
    assert summary.balance == Decimal("100000.00")
    assert summary.open_position_count == 0


async def test_market_buy_opens_position_at_ask():
    broker = _broker(spread="0.00010", instruments={"EUR_USD": "1.10000"})
    result = await broker.place_order(
        Order(instrument="EUR_USD", units="1000", type=OrderType.MARKET)
    )
    assert result.filled is True
    assert result.fill_price == Decimal("1.10005")
    summary = await broker.get_account_summary()
    assert summary.open_position_count == 1
    assert summary.margin_used > 0


async def test_unknown_instrument_raises():
    with pytest.raises(ValueError):
        await _broker().place_order(
            Order(instrument="XXX_YYY", units="1", type=OrderType.MARKET)
        )


async def test_stream_is_deterministic_for_same_seed():
    first = await _collect(_broker(seed=7), "EUR_USD", 5)
    second = await _collect(_broker(seed=7), "EUR_USD", 5)
    assert first == second


async def test_different_seeds_diverge():
    first = await _collect(_broker(seed=1), "EUR_USD", 5)
    second = await _collect(_broker(seed=2), "EUR_USD", 5)
    assert first != second


async def test_close_flattens_position():
    broker = _broker()
    await broker.place_order(
        Order(instrument="EUR_USD", units="1000", type=OrderType.MARKET)
    )
    result = await broker.close_position("EUR_USD")
    assert result.filled is True
    summary = await broker.get_account_summary()
    assert summary.open_position_count == 0


async def test_close_with_no_position_does_not_fill():
    result = await _broker().close_position("EUR_USD")
    assert result.filled is False


async def test_profit_realized_when_price_rises():
    broker = SimBroker(
        volatility=0.0,
        drift=0.01,
        spread="0",
        tick_seconds=0,
        instruments={"EUR_USD": "1.00000"},
    )
    await broker.place_order(
        Order(instrument="EUR_USD", units="1000", type=OrderType.MARKET)
    )
    await _collect(broker, "EUR_USD", 5)
    await broker.close_position("EUR_USD")
    summary = await broker.get_account_summary()
    assert summary.balance > Decimal("100000")


async def test_round_trip_is_flat_without_spread_or_movement():
    broker = SimBroker(
        volatility=0.0,
        drift=0.0,
        spread="0",
        tick_seconds=0,
        instruments={"EUR_USD": "1.00000"},
    )
    await broker.place_order(
        Order(instrument="EUR_USD", units="1000", type=OrderType.MARKET)
    )
    await broker.close_position("EUR_USD")
    summary = await broker.get_account_summary()
    assert summary.balance == Decimal("100000.00")


async def test_limit_far_from_market_does_not_fill():
    broker = _broker(instruments={"EUR_USD": "1.10000"})
    result = await broker.place_order(
        Order(instrument="EUR_USD", units="1000", type=OrderType.LIMIT, price="0.50000")
    )
    assert result.filled is False


async def test_marketable_buy_limit_fills():
    broker = _broker(spread="0.00010", instruments={"EUR_USD": "1.10000"})
    result = await broker.place_order(
        Order(instrument="EUR_USD", units="1000", type=OrderType.LIMIT, price="1.20000")
    )
    assert result.filled is True


async def test_get_candles_returns_valid_series():
    candles = await _broker().get_candles("EUR_USD", "M1", 10)
    assert len(candles) == 10
    for candle in candles:
        assert candle.low <= candle.open <= candle.high
        assert candle.low <= candle.close <= candle.high


async def test_get_candles_rejects_unknown_granularity():
    with pytest.raises(ValueError):
        await _broker().get_candles("EUR_USD", "BOGUS", 5)
