from datetime import datetime, timedelta, timezone
from decimal import Decimal

import asyncpg
import pytest

from oft.broker.models import Candle
from oft.marketdata import ingest_synthetic, load_replay_broker
from oft.persistence import CandleStore
from oft.persistence.config import database_url


async def _store_or_skip():
    store = CandleStore()
    try:
        await store.init_schema()
    except Exception as exc:  # noqa: BLE001 - any connection failure => skip
        pytest.skip(f"database not available: {exc}")
    return store


async def _wipe(instrument):
    conn = await asyncpg.connect(database_url())
    try:
        await conn.execute("DELETE FROM candles WHERE instrument = $1", instrument)
    finally:
        await conn.close()


def _candles(prices, start):
    return [
        Candle(
            time=start + timedelta(minutes=i),
            open=Decimal(price),
            high=Decimal(price),
            low=Decimal(price),
            close=Decimal(price),
            volume=100 + i,
        )
        for i, price in enumerate(prices)
    ]


async def test_save_and_get_roundtrip():
    store = await _store_or_skip()
    instrument = "TEST_C_ROUNDTRIP"
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = _candles(["1.10000", "1.10100", "1.10200"], start)
    await _wipe(instrument)
    try:
        assert await store.save_candles(instrument, candles) == 3
        got = await store.get_candles(instrument, limit=10)
        assert [c.time for c in got] == [c.time for c in candles]  # ascending
        assert [c.close for c in got] == [Decimal(p) for p in
                                          ("1.10000", "1.10100", "1.10200")]
        assert got[0].volume == 100
    finally:
        await _wipe(instrument)


async def test_upsert_overwrites_same_bucket():
    store = await _store_or_skip()
    instrument = "TEST_C_UPSERT"
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    await _wipe(instrument)
    try:
        await store.save_candles(instrument, _candles(["1.10000", "1.10100"], start))
        # same times, different close -> update in place, no new rows
        await store.save_candles(instrument, _candles(["1.19999", "1.18888"], start))
        assert await store.count(instrument) == 2
        got = await store.get_candles(instrument, limit=10)
        assert [c.close for c in got] == [Decimal("1.19999"), Decimal("1.18888")]
    finally:
        await _wipe(instrument)


async def test_range_filter():
    store = await _store_or_skip()
    instrument = "TEST_C_RANGE"
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    await _wipe(instrument)
    try:
        await store.save_candles(
            instrument, _candles(["1.1", "1.2", "1.3", "1.4", "1.5"], start)
        )
        got = await store.get_candles(
            instrument, start=start + timedelta(minutes=2), limit=10
        )
        assert len(got) == 3
        assert got[0].time == start + timedelta(minutes=2)
    finally:
        await _wipe(instrument)


async def test_empty_save_is_a_noop():
    store = await _store_or_skip()
    assert await store.save_candles("TEST_C_EMPTY", []) == 0


async def test_ingest_synthetic_persists_and_bucket_aligns():
    await _store_or_skip()
    instrument = "TEST_C_INGEST"
    end = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
    await _wipe(instrument)
    try:
        n = await ingest_synthetic(
            instrument, granularity="M1", count=100, seed=7, end=end
        )
        assert n == 100
        store = CandleStore()
        assert await store.count(instrument) == 100
        got = await store.get_candles(instrument, limit=100)
        assert all(c.time.second == 0 and c.time.microsecond == 0 for c in got)
        assert got[-1].time == end
        # re-ingest identical params -> idempotent (upsert, not duplicate)
        await ingest_synthetic(instrument, granularity="M1", count=100, seed=7, end=end)
        assert await store.count(instrument) == 100
    finally:
        await _wipe(instrument)


async def test_load_replay_broker_from_store():
    await _store_or_skip()
    instrument = "TEST_C_REPLAY"
    end = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
    await _wipe(instrument)
    try:
        await ingest_synthetic(
            instrument, granularity="M1", count=50, seed=3, end=end
        )
        broker = await load_replay_broker(instrument, limit=50)
        prices = [p async for p in broker.stream_prices([instrument])]
        assert len(prices) == 50
        assert prices[-1].time == end
    finally:
        await _wipe(instrument)
