from decimal import Decimal

from oft.backtest import Backtester, BacktestResult, summarize
from oft.broker import SimBroker
from oft.risk import FixedFractionalRisk
from oft.strategy import SmaCrossover


def test_summarize_computes_return_drawdown_and_trades():
    equity = [Decimal("100"), Decimal("110"), Decimal("105"), Decimal("120")]
    balance = [Decimal("100"), Decimal("110"), Decimal("105"), Decimal("120")]
    result = summarize(equity, balance, bars=3)
    assert result.starting_equity == Decimal("100")
    assert result.ending_equity == Decimal("120")
    assert result.total_return == Decimal("0.2")
    assert round(float(result.max_drawdown), 4) == round(5 / 110, 4)
    assert result.wins == 2
    assert result.losses == 1
    assert result.trades == 3


def test_summarize_flat_curve_is_all_zeros():
    equity = [Decimal("100"), Decimal("100"), Decimal("100")]
    result = summarize(equity, equity, bars=2)
    assert result.total_return == Decimal("0")
    assert result.max_drawdown == Decimal("0")
    assert result.sharpe == 0.0
    assert result.volatility == 0.0
    assert result.trades == 0
    assert result.win_rate == 0.0


def test_report_is_a_readable_string():
    result = summarize([Decimal("100"), Decimal("120")], [Decimal("100"), Decimal("120")], bars=1)
    text = result.report()
    assert "total return" in text
    assert "sharpe" in text


async def test_backtester_runs_against_simbroker():
    broker = SimBroker(seed=11, tick_seconds=0, volatility=0.001)
    backtester = Backtester(
        broker,
        SmaCrossover(fast=5, slow=20),
        "EUR_USD",
        risk=FixedFractionalRisk(risk_per_trade="0.005"),
    )
    result = await backtester.run(bars=300)
    assert isinstance(result, BacktestResult)
    assert result.bars == 300
    assert result.starting_equity == Decimal("100000.00")
    assert isinstance(result.sharpe, float)
    assert len(backtester.engine.signals) > 0


async def test_backtest_is_deterministic_for_same_seed():
    def build():
        broker = SimBroker(seed=5, tick_seconds=0, volatility=0.001)
        return Backtester(broker, SmaCrossover(fast=5, slow=20), "EUR_USD", units="1000")

    first = await build().run(bars=200)
    second = await build().run(bars=200)
    assert first == second
