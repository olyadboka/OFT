"""Build a ReplayBroker from candles stored in the CandleStore.

This is the only seam that depends on both the persistence layer and the broker
layer, so it lives here rather than inside the DB-free ReplayBroker.
"""

from __future__ import annotations

from datetime import datetime

from oft.broker.replay import ReplayBroker
from oft.persistence.candles import CandleStore


async def load_replay_broker(
    instrument: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 500,
    store: CandleStore | None = None,
    **broker_kwargs: object,
) -> ReplayBroker:
    store = store or CandleStore()
    candles = await store.get_candles(
        instrument, start=start, end=end, limit=limit
    )
    return ReplayBroker(instrument, candles, **broker_kwargs)  # type: ignore[arg-type]
