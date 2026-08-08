import pytest

from oft.broker.models import Price
from oft.strategy import Breakout, RsiStrategy, Signal, Strategy


def _price(mid):
    return Price(instrument="X", time="2026-08-08T12:00:00", bid=str(mid), ask=str(mid))


def _signals(strategy, mids):
    return [strategy.on_price(_price(m)) for m in mids]


def test_rsi_rejects_bad_parameters():
    with pytest.raises(ValueError):
        RsiStrategy(window=1)
    with pytest.raises(ValueError):
        RsiStrategy(oversold=70, overbought=30)


def test_rsi_is_a_named_strategy():
    strat = RsiStrategy(window=14)
    assert isinstance(strat, Strategy)
    assert "rsi" in strat.name


def test_rsi_holds_until_warmed_up():
    strat = RsiStrategy(window=5)
    assert strat.on_price(_price(1)) is Signal.HOLD
    assert strat.on_price(_price(2)) is Signal.HOLD


def test_rsi_sells_on_overbought_cross():
    strat = RsiStrategy(window=2, oversold=30, overbought=70)
    signals = _signals(strat, [10, 8, 6, 9, 12])
    assert Signal.SELL in signals


def test_rsi_buys_on_oversold_cross():
    strat = RsiStrategy(window=2, oversold=30, overbought=70)
    signals = _signals(strat, [10, 12, 14, 11, 8])
    assert Signal.BUY in signals


def test_breakout_rejects_bad_window():
    with pytest.raises(ValueError):
        Breakout(window=1)


def test_breakout_is_a_named_strategy():
    strat = Breakout(window=20)
    assert isinstance(strat, Strategy)
    assert "breakout" in strat.name


def test_breakout_buys_on_new_high():
    strat = Breakout(window=3)
    signals = _signals(strat, [1, 1, 1, 2])
    assert signals[-1] is Signal.BUY


def test_breakout_sells_on_new_low():
    strat = Breakout(window=3)
    signals = _signals(strat, [5, 5, 5, 3])
    assert signals[-1] is Signal.SELL


def test_breakout_holds_inside_range():
    strat = Breakout(window=3)
    signals = _signals(strat, [5, 6, 4, 5])
    assert signals[-1] is Signal.HOLD
