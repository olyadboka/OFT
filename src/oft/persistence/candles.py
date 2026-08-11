"""CandleStore: persist and query OHLC candles in a TimescaleDB hypertable."""

from __future__ import annotations

from datetime import datetime

import asyncpg

from oft.broker.models import Candle
from oft.persistence.config import database_url

_TABLE = """
CREATE TABLE IF NOT EXISTS candles (
    instrument TEXT        NOT NULL,
    time       TIMESTAMPTZ NOT NULL,
    open       NUMERIC     NOT NULL,
    high       NUMERIC     NOT NULL,
    low        NUMERIC     NOT NULL,
    close      NUMERIC     NOT NULL,
    volume     BIGINT      NOT NULL,
    complete   BOOLEAN     NOT NULL DEFAULT TRUE,
    PRIMARY KEY (instrument, time)
);
"""

_HYPERTABLE = "SELECT create_hypertable('candles', 'time', if_not_exists => TRUE);"

_UPSERT = """
INSERT INTO candles (instrument, time, open, high, low, close, volume, complete)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (instrument, time) DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    volume = EXCLUDED.volume,
    complete = EXCLUDED.complete
"""


class CandleStore:
    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or database_url()

    async def init_schema(self) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(_TABLE)
            await conn.execute(_HYPERTABLE)
        finally:
            await conn.close()

    async def save_candles(self, instrument: str, candles: list[Candle]) -> int:
        if not candles:
            return 0
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.executemany(
                _UPSERT,
                [
                    (
                        instrument,
                        c.time,
                        c.open,
                        c.high,
                        c.low,
                        c.close,
                        c.volume,
                        c.complete,
                    )
                    for c in candles
                ],
            )
        finally:
            await conn.close()
        return len(candles)

    async def get_candles(
        self,
        instrument: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[Candle]:
        conn = await asyncpg.connect(self._dsn)
        try:
            rows = await conn.fetch(
                """
                SELECT time, open, high, low, close, volume, complete
                FROM candles
                WHERE instrument = $1
                  AND ($2::timestamptz IS NULL OR time >= $2)
                  AND ($3::timestamptz IS NULL OR time <= $3)
                ORDER BY time ASC
                LIMIT $4
                """,
                instrument,
                start,
                end,
                limit,
            )
        finally:
            await conn.close()
        return [
            Candle(
                time=row["time"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
                complete=row["complete"],
            )
            for row in rows
        ]

    async def count(self, instrument: str) -> int:
        conn = await asyncpg.connect(self._dsn)
        try:
            return await conn.fetchval(
                "SELECT count(*) FROM candles WHERE instrument = $1", instrument
            )
        finally:
            await conn.close()
