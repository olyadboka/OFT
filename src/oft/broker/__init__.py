"""
oft.broker — the trading-engine boundary of OFT.

This package defines the *interface* every strategy, risk manager, and dashboard
endpoint talks to (`Broker`), plus the concrete engines that satisfy it
(`SimBroker` now, maybe `OandaClient` later).

Rule of the codebase: nothing outside this package imports a *concrete* engine
directly. Everyone depends on `Broker` and receives the concrete one at startup.
That is what makes sim <-> live a one-line swap.

Public API — re-exported here so callers write `from oft.broker import Broker`
instead of reaching into submodules. Uncomment each line as you build it:
"""

from oft.broker.base import Broker
from oft.broker.models import (
    AccountSummary,
    Candle,
    Order,
    OrderResult,
    OrderType,
    Position,
    Price,
)
from oft.broker.replay import ReplayBroker
from oft.broker.sim import SimBroker

__all__ = [
    "Broker",
    "SimBroker",
    "ReplayBroker",
    "AccountSummary",
    "Candle",
    "Order",
    "OrderResult",
    "OrderType",
    "Position",
    "Price",
]
