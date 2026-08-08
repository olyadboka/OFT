"""Fixed-fractional sizing: risk a set fraction of equity per trade, under hard caps."""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal

from oft.broker.models import AccountSummary, Price
from oft.risk.base import RiskDecision, RiskManager
from oft.strategy.base import Signal

_WHOLE = Decimal("1")


class FixedFractionalRisk(RiskManager):
    def __init__(
        self,
        *,
        risk_per_trade: str = "0.01",
        stop_loss: str = "0.0025",
        max_leverage: str = "10",
        max_units: str = "5000000",
        max_drawdown: str = "0.25",
    ) -> None:
        self._risk_per_trade = Decimal(risk_per_trade)
        self._stop_loss = Decimal(stop_loss)
        self._max_leverage = Decimal(max_leverage)
        self._max_units = Decimal(max_units)
        self._max_drawdown = Decimal(max_drawdown)
        self._start_equity: Decimal | None = None

    def evaluate(
        self, signal: Signal, account: AccountSummary, price: Price
    ) -> RiskDecision:
        equity = account.margin_available + account.margin_used
        if self._start_equity is None:
            self._start_equity = equity

        if signal is Signal.CLOSE:
            return RiskDecision(True, Decimal(0), "close")

        floor = self._start_equity * (Decimal(1) - self._max_drawdown)
        if equity <= floor:
            return RiskDecision(False, Decimal(0), "drawdown limit reached")

        by_risk = (equity * self._risk_per_trade) / self._stop_loss
        by_exposure = (equity * self._max_leverage) / price.mid
        units = min(by_risk, by_exposure, self._max_units).quantize(
            _WHOLE, rounding=ROUND_DOWN
        )
        if units <= 0:
            return RiskDecision(False, Decimal(0), "size rounds to zero")

        target = units if signal is Signal.BUY else -units
        return RiskDecision(True, target, f"sized {units} units")
