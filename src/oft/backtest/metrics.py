"""Backtest metrics: turn an equity curve into performance statistics."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BacktestResult:
    bars: int
    starting_equity: Decimal
    ending_equity: Decimal
    total_return: Decimal
    max_drawdown: Decimal
    volatility: float
    sharpe: float
    trades: int
    wins: int
    losses: int
    win_rate: float

    def report(self) -> str:
        return "\n".join(
            [
                f"bars            {self.bars}",
                f"starting equity {self.starting_equity:.2f}",
                f"ending equity   {self.ending_equity:.2f}",
                f"total return    {self.total_return:.2%}",
                f"max drawdown    {self.max_drawdown:.2%}",
                f"volatility      {self.volatility:.6f}",
                f"sharpe          {self.sharpe:.4f}",
                f"trades          {self.trades} (W {self.wins} / L {self.losses})",
                f"win rate        {self.win_rate:.2%}",
            ]
        )


def summarize(
    equity: list[Decimal], balance: list[Decimal], bars: int
) -> BacktestResult:
    starting = equity[0]
    ending = equity[-1]
    total_return = (ending - starting) / starting if starting else Decimal(0)
    returns = _returns(equity)
    volatility = statistics.pstdev(returns) if returns else 0.0
    mean_return = statistics.fmean(returns) if returns else 0.0
    sharpe = mean_return / volatility if volatility else 0.0
    wins, losses = _outcomes(balance)
    trades = wins + losses
    win_rate = wins / trades if trades else 0.0
    return BacktestResult(
        bars=bars,
        starting_equity=starting,
        ending_equity=ending,
        total_return=total_return,
        max_drawdown=_max_drawdown(equity),
        volatility=volatility,
        sharpe=sharpe,
        trades=trades,
        wins=wins,
        losses=losses,
        win_rate=win_rate,
    )


def _returns(equity: list[Decimal]) -> list[float]:
    changes = []
    for prev, curr in zip(equity, equity[1:]):
        if prev != 0:
            changes.append(float(curr / prev) - 1.0)
    return changes


def _max_drawdown(equity: list[Decimal]) -> Decimal:
    peak = equity[0]
    worst = Decimal(0)
    for value in equity:
        if value > peak:
            peak = value
        if peak > 0:
            drawdown = (peak - value) / peak
            if drawdown > worst:
                worst = drawdown
    return worst


def _outcomes(balance: list[Decimal]) -> tuple[int, int]:
    wins = losses = 0
    for prev, curr in zip(balance, balance[1:]):
        change = curr - prev
        if change > 0:
            wins += 1
        elif change < 0:
            losses += 1
    return wins, losses
