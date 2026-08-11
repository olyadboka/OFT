"""FastAPI app: run backtests and parameter sweeps over HTTP."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from oft.backtest import Backtester, by_return, by_sharpe, sweep
from oft.broker import ReplayBroker, SimBroker
from oft.marketdata import ingest_synthetic
from oft.persistence import CandleStore, ResultStore
from oft.risk import FixedFractionalRisk
from oft.strategy import STRATEGIES, make_strategy

app = FastAPI(title="OFT", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _store_or_503(action):
    """Run a ResultStore coroutine, mapping any DB failure to HTTP 503."""
    try:
        return await action(ResultStore())
    except (OSError, asyncpg.PostgresError) as exc:
        raise HTTPException(
            status_code=503, detail=f"database unavailable: {exc}") from exc


async def _db_or_503(coro):
    """Await any DB coroutine, mapping connection/query failure to HTTP 503."""
    try:
        return await coro
    except (OSError, asyncpg.PostgresError) as exc:
        raise HTTPException(
            status_code=503, detail=f"database unavailable: {exc}") from exc


class BacktestRequest(BaseModel):
    strategy: str = "sma"
    params: dict[str, Any] = Field(default_factory=lambda: {
                                   "fast": 10, "slow": 15})
    bars: int = Field(default=500, gt=0, le=20000)
    seed: int = 11
    volatility: float = 0.001
    risk_per_trade: str = "0.01"
    persist: bool = False
    source: str = "sim"
    instrument: str = "EUR_USD"


class BacktestResponse(BaseModel):
    strategy: str
    bars: int
    total_return: float
    max_drawdown: float
    sharpe: float
    trades: int
    win_rate: float
    ending_equity: float
    id: int | None = None


class StoredResultResponse(BaseModel):
    id: int
    strategy: str
    params: dict[str, Any]
    bars: int
    total_return: float
    sharpe: float


class IngestRequest(BaseModel):
    instrument: str = "EUR_USD"
    granularity: str = "M1"
    count: int = Field(default=500, gt=0, le=100000)
    seed: int = 11
    start_price: str = "1.10000"


class IngestResponse(BaseModel):
    instrument: str
    ingested: int


class CandleResponse(BaseModel):
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    complete: bool


class SweepRequest(BaseModel):
    strategy: str = "sma"
    grid: dict[str, list[Any]] = Field(
        default_factory=lambda: {"fast": [5, 10], "slow": [15, 20]}
    )
    bars: int = Field(default=300, gt=0, le=20000)
    seed: int = 11
    volatility: float = 0.001
    objective: str = "sharpe"
    top: int = Field(default=5, gt=0, le=50)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "strategies": sorted(STRATEGIES)}


@app.post("/backtest", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest) -> BacktestResponse:
    try:
        strategy = make_strategy(request.strategy, request.params)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if request.source == "stored":
        candles = await _db_or_503(
            CandleStore().get_candles(request.instrument, limit=request.bars)
        )
        if not candles:
            raise HTTPException(
                status_code=400,
                detail=f"no stored candles for {request.instrument!r}",
            )
        broker = ReplayBroker(request.instrument, candles)
        bars = len(candles)
    elif request.source == "sim":
        broker = SimBroker(
            seed=request.seed, tick_seconds=0, volatility=request.volatility,
            instruments={request.instrument: "1.10000"},
        )
        bars = request.bars
    else:
        raise HTTPException(
            status_code=400, detail=f"unknown source: {request.source!r}")
    risk = FixedFractionalRisk(risk_per_trade=request.risk_per_trade)
    backtester = Backtester(broker, strategy, request.instrument, risk=risk)
    result = await backtester.run(bars)

    result_id: int | None = None
    if request.persist:
        result_id = await _store_or_503(
            lambda store: _save(store, strategy.name, request.params, result)
        )

    return BacktestResponse(
        strategy=strategy.name,
        bars=result.bars,
        total_return=float(result.total_return),
        max_drawdown=float(result.max_drawdown),
        sharpe=result.sharpe,
        trades=result.trades,
        win_rate=result.win_rate,
        ending_equity=float(result.ending_equity),
        id=result_id,
    )


async def _save(store: ResultStore, strategy: str, params: dict, result) -> int:
    await store.init_schema()
    return await store.save(strategy, params, result)


@app.post("/sweep")
async def run_sweep(request: SweepRequest) -> dict:
    if request.strategy not in STRATEGIES:
        raise HTTPException(
            status_code=400, detail=f"unknown strategy: {request.strategy!r}"
        )

    def build(params: dict) -> Backtester:
        broker = SimBroker(
            seed=request.seed, tick_seconds=0, volatility=request.volatility
        )
        strategy = make_strategy(request.strategy, params)
        return Backtester(broker, strategy, "EUR_USD", risk=FixedFractionalRisk())

    objective = by_return if request.objective == "return" else by_sharpe
    trials = await sweep(build, request.grid, request.bars, objective=objective)
    return {
        "count": len(trials),
        "top": [
            {
                "params": trial.params,
                "total_return": float(trial.result.total_return),
                "sharpe": trial.result.sharpe,
                "trades": trial.result.trades,
            }
            for trial in trials[: request.top]
        ],
    }


@app.get("/results", response_model=list[StoredResultResponse])
async def list_results(limit: int = 10) -> list[StoredResultResponse]:
    stored = await _store_or_503(lambda store: store.recent(limit=limit))
    return [
        StoredResultResponse(
            id=row.id,
            strategy=row.strategy,
            params=row.params,
            bars=row.bars,
            total_return=float(row.total_return),
            sharpe=row.sharpe,
        )
        for row in stored
    ]


@app.delete("/results/{result_id}", status_code=204)
async def delete_result(result_id: int) -> None:
    await _store_or_503(lambda store: store.delete(result_id))


@app.post("/candles/ingest", response_model=IngestResponse)
async def ingest_candles(request: IngestRequest) -> IngestResponse:
    try:
        ingested = await ingest_synthetic(
            request.instrument,
            granularity=request.granularity,
            count=request.count,
            seed=request.seed,
            start_price=request.start_price,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (OSError, asyncpg.PostgresError) as exc:
        raise HTTPException(
            status_code=503, detail=f"database unavailable: {exc}") from exc
    return IngestResponse(instrument=request.instrument, ingested=ingested)


@app.get("/candles", response_model=list[CandleResponse])
async def list_candles(instrument: str, limit: int = 100) -> list[CandleResponse]:
    candles = await _db_or_503(CandleStore().get_candles(instrument, limit=limit))
    return [
        CandleResponse(
            time=candle.time,
            open=float(candle.open),
            high=float(candle.high),
            low=float(candle.low),
            close=float(candle.close),
            volume=candle.volume,
            complete=candle.complete,
        )
        for candle in candles
    ]
