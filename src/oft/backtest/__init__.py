"""oft.backtest — replay strategies through the engine and compute performance metrics."""

from oft.backtest.metrics import BacktestResult, summarize
from oft.backtest.runner import Backtester
from oft.backtest.sweep import SweepTrial, by_return, by_sharpe, expand_grid, sweep

__all__ = [
    "BacktestResult",
    "Backtester",
    "summarize",
    "SweepTrial",
    "sweep",
    "expand_grid",
    "by_sharpe",
    "by_return",
]
