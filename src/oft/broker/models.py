"""
oft.broker.models — the data contracts (DTOs) that cross the Broker boundary.

These are the *nouns* of trading: Price, Candle, Position, AccountSummary,
Order, OrderResult. Every Broker implementation speaks in exactly these types,
so the rest of OFT never depends on any one broker's private wire format.

Design rules honored here:
  * Pydantic v2 BaseModel  -> validation + JSON for the dashboard + schemas.
  * Decimal for money/prices, NEVER float.
  * Enum for closed sets of choices (order type).
  * Value objects are frozen (immutable) — a past price is a fact, not editable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


class _Base(BaseModel):
    """Shared configuration for every DTO in OFT (not exported)."""

    model_config = ConfigDict(
        frozen=True,        # immutable: safe to pass around, hashable, no accidental mutation
        extra="forbid",     # reject unknown fields loudly instead of silently ignoring them
    )


class OrderType(str, Enum):
    """How an order is priced. `str` mixin => serializes as "MARKET"/"LIMIT"."""

    MARKET = "MARKET"   # fill immediately at the current market price
    LIMIT = "LIMIT"     # fill only at `price` or better


class Price(_Base):
    """A single bid/ask quote for one instrument at one instant."""

    instrument: str
    time: datetime
    bid: Decimal = Field(..., gt=0, description="Best price a buyer will pay")
    ask: Decimal = Field(..., gt=0, description="Best price a seller will accept")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mid(self) -> Decimal:
        """Midpoint of the spread — the usual 'the price' for signals."""
        return (self.bid + self.ask) / 2

    @computed_field  # type: ignore[prop-decorator]
    @property
    def spread(self) -> Decimal:
        """Ask minus bid — the round-trip cost baked into every trade."""
        return self.ask - self.bid

    @field_validator("time")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        """Force every timestamp to timezone-aware UTC (naive -> assume UTC)."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class Candle(_Base):
    """One OHLC bar for a fixed time bucket (e.g. one minute)."""

    time: datetime
    open: Decimal = Field(..., gt=0)
    high: Decimal = Field(..., gt=0)
    low: Decimal = Field(..., gt=0)
    close: Decimal = Field(..., gt=0)
    volume: int = Field(..., ge=0)
    complete: bool = True   # False = the current, still-forming bar

    @model_validator(mode="after")
    def _check_ohlc_sane(self) -> "Candle":
        """high must be the top and low the bottom — else the bar is corrupt."""
        if self.high < self.low:
            raise ValueError("high < low")
        if not (self.low <= self.open <= self.high):
            raise ValueError("open outside [low, high]")
        if not (self.low <= self.close <= self.high):
            raise ValueError("close outside [low, high]")
        return self


class Position(_Base):
    """The bot's current exposure in one instrument."""

    instrument: str
    units: Decimal          # SIGNED: positive = long, negative = short, 0 = flat
    avg_price: Decimal = Field(..., gt=0, description="Volume-weighted entry price")
    unrealized_pl: Decimal  # may be negative — no constraint


class AccountSummary(_Base):
    """A snapshot of account health — what the dashboard shows at a glance."""

    account_id: str
    currency: str = Field(..., min_length=3, max_length=3, description="e.g. 'USD'")
    balance: Decimal
    margin_used: Decimal = Field(..., ge=0)
    margin_available: Decimal = Field(..., ge=0)
    open_position_count: int = Field(..., ge=0)


class Order(_Base):
    """A request to change position — the bot's *intent*, before it is filled."""

    instrument: str
    units: Decimal                       # SIGNED: + buy/long, - sell/short
    type: OrderType = OrderType.MARKET
    price: Decimal | None = Field(default=None, gt=0)   # required only for LIMIT

    @field_validator("units")
    @classmethod
    def _units_nonzero(cls, v: Decimal) -> Decimal:
        if v == 0:
            raise ValueError("units cannot be zero — an order must buy or sell something")
        return v

    @model_validator(mode="after")
    def _price_matches_type(self) -> "Order":
        """A LIMIT needs a price; a MARKET must not carry one."""
        if self.type is OrderType.LIMIT and self.price is None:
            raise ValueError("LIMIT order requires a price")
        if self.type is OrderType.MARKET and self.price is not None:
            raise ValueError("MARKET order must not specify a price")
        return self


class OrderResult(_Base):
    """What the broker returns after receiving an order."""

    order_id: str
    filled: bool
    time: datetime
    fill_price: Decimal | None = Field(default=None, gt=0)   # None if not (yet) filled

    @model_validator(mode="after")
    def _filled_has_price(self) -> "OrderResult":
        """If it filled, it filled at *some* price — enforce that invariant."""
        if self.filled and self.fill_price is None:
            raise ValueError("a filled order must have a fill_price")
        return self
