"""oft.backtest — replay strategies through the engine and compute performance metrics."""

from oft.backtest.metrics import BacktestResult, summarize
from oft.backtest.runner import Backtester

__all__ = [
    "BacktestResult",
    "Backtester",
    "summarize",
]
