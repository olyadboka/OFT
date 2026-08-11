from datetime import datetime, timedelta, timezone
from decimal import Decimal

from oft.broker import ReplayBroker
from oft.broker.models import Candle, Order, OrderType

_START = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)


def _candles(prices):
    out = []
    for i, price in enumerate(prices):
        d = Decimal(price)
        out.append(
            Candle(
                time=_START + timedelta(minutes=i),
                open=d,
                high=d,
                low=d,
                close=d,
                volume=100,
            )
        )
    return out


async def test_stream_yields_one_price_per_candle_in_order():
    candles = _candles(["1.10000", "1.11000", "1.12000"])
    broker = ReplayBroker("EUR_USD", candles, spread="0")
    prices = [price async for price in broker.stream_prices(["EUR_USD"])]
    assert len(prices) == 3
    assert [p.time for p in prices] == [c.time for c in candles]
    assert [p.mid for p in prices] == [
        Decimal("1.10000"),
        Decimal("1.11000"),
        Decimal("1.12000"),
    ]


async def test_spread_applied_around_close():
    broker = ReplayBroker("EUR_USD", _candles(["1.20000"]), spread="0.00020")
    price = [p async for p in broker.stream_prices(["EUR_USD"])][0]
    assert price.bid == Decimal("1.19990")
    assert price.ask == Decimal("1.20010")


async def test_roundtrip_pnl_uses_inherited_engine():
    broker = ReplayBroker(
        "EUR_USD", _candles(["1.10000", "1.11000", "1.12000"]), spread="0", leverage=30
    )
    stream = broker.stream_prices(["EUR_USD"])
    await stream.__anext__()  # mid -> 1.10000
    await broker.place_order(
        Order(instrument="EUR_USD", units=Decimal(1000), type=OrderType.MARKET)
    )
    async for _ in stream:  # advance the tape to 1.12000
        pass
    await broker.close_position("EUR_USD")
    account = await broker.get_account_summary()
    assert account.balance == Decimal("100020.00")  # +0.02000 * 1000
    assert account.open_position_count == 0


async def test_take_profit_auto_closes_during_replay():
    broker = ReplayBroker(
        "EUR_USD", _candles(["1.10000", "1.11000", "1.12000"]), spread="0"
    )
    stream = broker.stream_prices(["EUR_USD"])
    await stream.__anext__()  # mid -> 1.10000
    await broker.place_order(
        Order(
            instrument="EUR_USD",
            units=Decimal(1000),
            type=OrderType.MARKET,
            take_profit=Decimal("1.10500"),
        )
    )
    async for _ in stream:  # TP breached at the 1.11000 bar, closes early
        pass
    account = await broker.get_account_summary()
    assert account.open_position_count == 0
    assert account.balance == Decimal("100010.00")  # closed at 1.11000, +0.01 * 1000


async def test_get_candles_returns_the_stored_tape():
    candles = _candles(["1.10000", "1.11000"])
    broker = ReplayBroker("EUR_USD", candles)
    assert await broker.get_candles("EUR_USD", "M1", 10) == candles


async def test_empty_tape_streams_nothing_but_still_constructs():
    broker = ReplayBroker("EUR_USD", [])
    prices = [p async for p in broker.stream_prices(["EUR_USD"])]
    assert prices == []
    account = await broker.get_account_summary()
    assert account.open_position_count == 0
