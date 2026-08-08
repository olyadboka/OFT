"""Strategy registry: build a strategy by name from a params dict."""

from __future__ import annotations

from oft.strategy.base import Strategy
from oft.strategy.breakout import Breakout
from oft.strategy.crossover import SmaCrossover
from oft.strategy.rsi import RsiStrategy

STRATEGIES = {
    "sma": SmaCrossover,
    "rsi": RsiStrategy,
    "breakout": Breakout,
}


def make_strategy(name: str, params: dict) -> Strategy:
    if name not in STRATEGIES:
        raise ValueError(f"unknown strategy: {name!r}")
    return STRATEGIES[name](**params)
