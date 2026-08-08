"""FastAPI app: run backtests and parameter sweeps over HTTP."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from oft.backtest import Backtester, by_return, by_sharpe, sweep
from oft.broker import SimBroker
from oft.risk import FixedFractionalRisk
from oft.strategy import Breakout, RsiStrategy, SmaCrossover, Strategy

app = FastAPI(title="OFT", version="0.1.0")

_STRATEGIES = {"sma": SmaCrossover, "rsi": RsiStrategy, "breakout": Breakout}


class BacktestRequest(BaseModel):
    strategy: str = "sma"
    params: dict[str, Any] = Field(default_factory=lambda: {"fast": 10, "slow": 15})
    bars: int = Field(default=500, gt=0, le=20000)
    seed: int = 11
    volatility: float = 0.001
    risk_per_trade: str = "0.01"


class BacktestResponse(BaseModel):
    strategy: str
    bars: int
    total_return: float
    max_drawdown: float
    sharpe: float
    trades: int
    win_rate: float
    ending_equity: float


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


def _make_strategy(name: str, params: dict) -> Strategy:
    if name not in _STRATEGIES:
        raise ValueError(f"unknown strategy: {name!r}")
    return _STRATEGIES[name](**params)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "strategies": sorted(_STRATEGIES)}


@app.post("/backtest", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest) -> BacktestResponse:
    try:
        strategy = _make_strategy(request.strategy, request.params)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    broker = SimBroker(seed=request.seed, tick_seconds=0, volatility=request.volatility)
    risk = FixedFractionalRisk(risk_per_trade=request.risk_per_trade)
    backtester = Backtester(broker, strategy, "EUR_USD", risk=risk)
    result = await backtester.run(request.bars)
    return BacktestResponse(
        strategy=strategy.name,
        bars=result.bars,
        total_return=float(result.total_return),
        max_drawdown=float(result.max_drawdown),
        sharpe=result.sharpe,
        trades=result.trades,
        win_rate=result.win_rate,
        ending_equity=float(result.ending_equity),
    )


@app.post("/sweep")
async def run_sweep(request: SweepRequest) -> dict:
    if request.strategy not in _STRATEGIES:
        raise HTTPException(
            status_code=400, detail=f"unknown strategy: {request.strategy!r}"
        )

    def build(params: dict) -> Backtester:
        broker = SimBroker(
            seed=request.seed, tick_seconds=0, volatility=request.volatility
        )
        strategy = _make_strategy(request.strategy, params)
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
