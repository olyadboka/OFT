from datetime import timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from oft.broker import (
    AccountSummary,
    Candle,
    Order,
    OrderResult,
    OrderType,
    Position,
    Price,
)


def _price(**overrides):
    data = dict(instrument="EUR_USD", time="2026-08-08T12:00:00", bid="1.10", ask="1.12")
    data.update(overrides)
    return Price(**data)


def _candle(**overrides):
    data = dict(
        time="2026-08-08T12:00:00",
        open="1.10",
        high="1.12",
        low="1.09",
        close="1.11",
        volume=100,
    )
    data.update(overrides)
    return Candle(**data)


def test_price_coerces_strings_to_decimal():
    p = _price(bid="1.10")
    assert p.bid == Decimal("1.10")
    assert isinstance(p.bid, Decimal)


def test_price_computes_mid_and_spread():
    p = _price(bid="1.10", ask="1.12")
    assert p.mid == Decimal("1.11")
    assert p.spread == Decimal("0.02")


def test_price_normalizes_naive_time_to_utc():
    p = _price(time="2026-08-08T12:00:00")
    assert p.time.tzinfo == timezone.utc


def test_price_is_frozen():
    p = _price()
    with pytest.raises(ValidationError):
        p.bid = Decimal("2")


def test_price_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        _price(bidd="1.10")


def test_price_rejects_non_positive():
    with pytest.raises(ValidationError):
        _price(bid="0")


def test_price_dump_includes_computed_fields():
    data = _price().model_dump()
    assert "mid" in data
    assert "spread" in data


def test_ordertype_behaves_like_string():
    assert OrderType.MARKET.value == "MARKET"
    assert OrderType.MARKET == "MARKET"


def test_order_rejects_zero_units():
    with pytest.raises(ValidationError):
        Order(instrument="EUR_USD", units="0")


def test_limit_order_requires_price():
    with pytest.raises(ValidationError):
        Order(instrument="EUR_USD", units="100", type=OrderType.LIMIT)


def test_market_order_forbids_price():
    with pytest.raises(ValidationError):
        Order(instrument="EUR_USD", units="100", type=OrderType.MARKET, price="1.10")


def test_valid_limit_order():
    order = Order(instrument="EUR_USD", units="-50", type=OrderType.LIMIT, price="1.09")
    assert order.units == Decimal("-50")
    assert order.price == Decimal("1.09")


def test_candle_accepts_sane_ohlc():
    assert _candle().complete is True


def test_candle_rejects_high_below_low():
    with pytest.raises(ValidationError):
        _candle(high="1.05", low="1.09")


def test_candle_rejects_open_outside_range():
    with pytest.raises(ValidationError):
        _candle(open="1.20")


def test_position_allows_negative_units_and_pnl():
    pos = Position(instrument="EUR_USD", units="-100", avg_price="1.10", unrealized_pl="-5.5")
    assert pos.units == Decimal("-100")
    assert pos.unrealized_pl == Decimal("-5.5")


def test_account_summary_rejects_bad_currency():
    with pytest.raises(ValidationError):
        AccountSummary(
            account_id="a",
            currency="DOLLAR",
            balance="100",
            margin_used="0",
            margin_available="100",
            open_position_count=0,
        )


def test_orderresult_filled_requires_fill_price():
    with pytest.raises(ValidationError):
        OrderResult(order_id="x", filled=True, time="2026-08-08T12:00:00")


def test_orderresult_unfilled_allows_no_price():
    result = OrderResult(order_id="x", filled=False, time="2026-08-08T12:00:00")
    assert result.fill_price is None
