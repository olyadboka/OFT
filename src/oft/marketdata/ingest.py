"""Ingest historical candles into the CandleStore.

The source is synthetic for now (SimBroker) — the same Broker interface a real
data feed would implement later, so this ingest path stays unchanged when a
live source is added.

SimBroker stamps candles against the wall clock, so bars land on random
sub-second times and re-running would insert duplicates. Real market candles
sit on canonical bucket boundaries (an M1 bar at :00), so we re-stamp the
synthetic bars onto an aligned grid. That also makes ingest idempotent: the
same (instrument, time) key upserts instead of piling up duplicates.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from oft.broker.sim import SimBroker
from oft.persistence.candles import CandleStore

_GRAN_SECONDS = {
    "S5": 5,
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "H1": 3600,
    "H4": 14400,
    "D": 86400,
}


def _floor_to_bucket(moment: datetime, step_seconds: int) -> datetime:
    epoch = moment.timestamp()
    floored = (int(epoch) // step_seconds) * step_seconds
    return datetime.fromtimestamp(floored, tz=timezone.utc)


async def ingest_synthetic(
    instrument: str,
    *,
    granularity: str = "M1",
    count: int = 500,
    seed: int | None = None,
    start_price: str = "1.10000",
    end: datetime | None = None,
    store: CandleStore | None = None,
) -> int:
    if granularity not in _GRAN_SECONDS:
        raise ValueError(f"unknown granularity: {granularity!r}")
    broker = SimBroker(instruments={instrument: start_price}, seed=seed)
    candles = await broker.get_candles(instrument, granularity, count)

    step_seconds = _GRAN_SECONDS[granularity]
    step = timedelta(seconds=step_seconds)
    anchor = _floor_to_bucket(end or datetime.now(timezone.utc), step_seconds)
    aligned = [
        candle.model_copy(update={"time": anchor - step * (count - 1 - i)})
        for i, candle in enumerate(candles)
    ]

    store = store or CandleStore()
    await store.init_schema()
    return await store.save_candles(instrument, aligned)
