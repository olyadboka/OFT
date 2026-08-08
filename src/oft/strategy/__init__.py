"""oft.strategy — trading logic (decides) and the engine that runs it on a Broker."""

from oft.strategy.base import Signal, Strategy
from oft.strategy.breakout import Breakout
from oft.strategy.crossover import SmaCrossover
from oft.strategy.engine import TradingEngine
from oft.strategy.rsi import RsiStrategy

__all__ = [
    "Signal",
    "Strategy",
    "SmaCrossover",
    "RsiStrategy",
    "Breakout",
    "TradingEngine",
]
