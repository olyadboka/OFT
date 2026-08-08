"""Parameter sweep: run a backtest per parameter combination and rank the results."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from oft.backtest.metrics import BacktestResult
    from oft.backtest.runner import Backtester


@dataclass(frozen=True)
class SweepTrial:
    params: dict
    result: BacktestResult


def expand_grid(grid: dict) -> list[dict]:
    keys = list(grid)
    return [
        dict(zip(keys, combo))
        for combo in itertools.product(*(grid[key] for key in keys))
    ]


def by_sharpe(result: BacktestResult) -> float:
    return result.sharpe


def by_return(result: BacktestResult) -> float:
    return float(result.total_return)


async def sweep(
    build: Callable[[dict], Backtester],
    grid: dict,
    bars: int,
    objective: Callable[[BacktestResult], float] = by_sharpe,
) -> list[SweepTrial]:
    trials: list[SweepTrial] = []
    for params in expand_grid(grid):
        try:
            backtester = build(params)
        except (ValueError, KeyError):
            continue
        result = await backtester.run(bars)
        trials.append(SweepTrial(params=params, result=result))
    trials.sort(key=lambda trial: objective(trial.result), reverse=True)
    return trials
