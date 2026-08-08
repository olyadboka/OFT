"""Risk contract: size and vet a strategy signal before it becomes an order."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oft.broker.models import AccountSummary, Price
    from oft.strategy.base import Signal


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    target_units: Decimal
    reason: str


class RiskManager(ABC):
    @abstractmethod
    def evaluate(
        self, signal: Signal, account: AccountSummary, price: Price
    ) -> RiskDecision: ...
