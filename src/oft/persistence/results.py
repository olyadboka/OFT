"""ResultStore: persist and query backtest results in PostgreSQL/TimescaleDB."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

import asyncpg

from oft.persistence.config import database_url

if TYPE_CHECKING:
    from oft.backtest.metrics import BacktestResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS backtest_results (
    id            BIGSERIAL PRIMARY KEY,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    strategy      TEXT NOT NULL,
    params        JSONB NOT NULL,
    bars          INTEGER NOT NULL,
    total_return  NUMERIC NOT NULL,
    max_drawdown  NUMERIC NOT NULL,
    sharpe        DOUBLE PRECISION NOT NULL,
    trades        INTEGER NOT NULL,
    win_rate      DOUBLE PRECISION NOT NULL,
    ending_equity NUMERIC NOT NULL
);
"""


@dataclass(frozen=True)
class StoredResult:
    id: int
    strategy: str
    params: dict
    bars: int
    total_return: Decimal
    sharpe: float


class ResultStore:
    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or database_url()

    async def init_schema(self) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(_SCHEMA)
        finally:
            await conn.close()

    async def save(self, strategy: str, params: dict, result: BacktestResult) -> int:
        conn = await asyncpg.connect(self._dsn)
        try:
            return await conn.fetchval(
                """
                INSERT INTO backtest_results (
                    strategy, params, bars, total_return, max_drawdown,
                    sharpe, trades, win_rate, ending_equity
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
                """,
                strategy,
                json.dumps(params),
                result.bars,
                result.total_return,
                result.max_drawdown,
                result.sharpe,
                result.trades,
                result.win_rate,
                result.ending_equity,
            )
        finally:
            await conn.close()

    async def recent(self, limit: int = 10) -> list[StoredResult]:
        conn = await asyncpg.connect(self._dsn)
        try:
            rows = await conn.fetch(
                """
                SELECT id, strategy, params, bars, total_return, sharpe
                FROM backtest_results
                ORDER BY created_at DESC, id DESC
                LIMIT $1
                """,
                limit,
            )
        finally:
            await conn.close()
        return [
            StoredResult(
                id=row["id"],
                strategy=row["strategy"],
                params=json.loads(row["params"]),
                bars=row["bars"],
                total_return=row["total_return"],
                sharpe=row["sharpe"],
            )
            for row in rows
        ]

    async def delete(self, result_id: int) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute("DELETE FROM backtest_results WHERE id = $1", result_id)
        finally:
            await conn.close()
