from decimal import Decimal

import pytest

from oft.backtest import Backtester, summarize
from oft.broker import SimBroker
from oft.persistence import ResultStore, StoredResult
from oft.risk import FixedFractionalRisk
from oft.strategy import SmaCrossover


async def _store_or_skip():
    store = ResultStore()
    try:
        await store.init_schema()
    except Exception as exc:  # noqa: BLE001 - any connection failure => skip
        pytest.skip(f"database not available: {exc}")
    return store


def _sample_result():
    curve = [Decimal("100000"), Decimal("100670"), Decimal("100500")]
    return summarize(curve, curve, bars=500)


async def test_save_and_recent_roundtrip():
    store = await _store_or_skip()
    result = _sample_result()
    result_id = await store.save("sma-crossover(10/15)", {"fast": 10, "slow": 15}, result)
    try:
        recent = await store.recent(limit=10)
        assert any(row.id == result_id for row in recent)
        row = next(r for r in recent if r.id == result_id)
        assert isinstance(row, StoredResult)
        assert row.strategy == "sma-crossover(10/15)"
        assert row.params == {"fast": 10, "slow": 15}
        assert row.bars == 500
        assert row.total_return == result.total_return
    finally:
        await store.delete(result_id)


async def test_persist_a_real_backtest():
    store = await _store_or_skip()
    broker = SimBroker(seed=11, tick_seconds=0, volatility=0.001)
    backtester = Backtester(
        broker, SmaCrossover(10, 15), "EUR_USD", risk=FixedFractionalRisk()
    )
    result = await backtester.run(bars=200)
    result_id = await store.save("sma", {"fast": 10, "slow": 15}, result)
    try:
        recent = await store.recent()
        assert any(row.id == result_id for row in recent)
    finally:
        await store.delete(result_id)
