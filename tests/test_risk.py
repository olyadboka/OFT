from decimal import Decimal

from oft.broker import SimBroker
from oft.broker.models import AccountSummary, Price
from oft.risk import FixedFractionalRisk, RiskManager
from oft.strategy import SmaCrossover, Signal, TradingEngine


def _account(balance="100000", margin_used="0"):
    return AccountSummary(
        account_id="sim",
        currency="USD",
        balance=balance,
        margin_used=margin_used,
        margin_available=balance,
        open_position_count=0,
    )


def _price(mid="1.10000"):
    return Price(instrument="EUR_USD", time="2026-08-08T12:00:00", bid=mid, ask=mid)


def _risk(**overrides):
    config = dict(
        risk_per_trade="0.01",
        stop_loss="0.0025",
        max_leverage="100",
        max_units="99999999",
    )
    config.update(overrides)
    return FixedFractionalRisk(**config)


def test_is_a_risk_manager():
    assert isinstance(FixedFractionalRisk(), RiskManager)


def test_buy_is_sized_from_risk_fraction():
    decision = _risk().evaluate(Signal.BUY, _account(), _price())
    assert decision.approved
    assert decision.target_units == Decimal("400000")


def test_sell_is_sized_negative():
    decision = _risk().evaluate(Signal.SELL, _account(), _price())
    assert decision.target_units == Decimal("-400000")


def test_max_units_caps_size():
    decision = _risk(risk_per_trade="0.5", stop_loss="0.0001", max_units="1000").evaluate(
        Signal.BUY, _account(), _price()
    )
    assert decision.target_units == Decimal("1000")


def test_leverage_caps_exposure():
    decision = _risk(risk_per_trade="1", stop_loss="0.00001", max_leverage="2").evaluate(
        Signal.BUY, _account(), _price("1.00000")
    )
    assert decision.target_units == Decimal("200000")


def test_close_is_always_approved_and_flat():
    decision = _risk().evaluate(Signal.CLOSE, _account(), _price())
    assert decision.approved
    assert decision.target_units == Decimal("0")


def test_drawdown_kill_switch_blocks_new_trades():
    risk = _risk(max_drawdown="0.10")
    risk.evaluate(Signal.BUY, _account("100000"), _price())
    decision = risk.evaluate(Signal.BUY, _account("85000"), _price())
    assert not decision.approved
    assert "drawdown" in decision.reason


def test_drawdown_still_allows_closing():
    risk = _risk(max_drawdown="0.10")
    risk.evaluate(Signal.BUY, _account("100000"), _price())
    decision = risk.evaluate(Signal.CLOSE, _account("80000"), _price())
    assert decision.approved
    assert decision.target_units == Decimal("0")


def test_size_that_rounds_to_zero_is_rejected():
    decision = _risk(risk_per_trade="0.0000001", stop_loss="1").evaluate(
        Signal.BUY, _account(), _price()
    )
    assert not decision.approved
    assert "zero" in decision.reason


async def test_engine_records_a_decision_per_signal():
    broker = SimBroker(seed=11, tick_seconds=0, volatility=0.001)
    engine = TradingEngine(
        broker, SmaCrossover(fast=5, slow=20), "EUR_USD", risk=_risk()
    )
    await engine.run(max_ticks=300)
    assert len(engine.decisions) == len(engine.signals)
    assert len(engine.signals) > 0
