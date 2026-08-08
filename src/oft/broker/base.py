"""Abstract Broker contract: the one boundary between OFT and any price/execution engine."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from oft.broker.models import AccountSummary, Candle, Order, OrderResult, Price


class Broker(ABC):
    @abstractmethod
    async def get_account_summary(self) -> AccountSummary: ...

    @abstractmethod
    async def get_candles(
        self, instrument: str, granularity: str, count: int
    ) -> list[Candle]: ...

    @abstractmethod
    def stream_prices(self, instruments: list[str]) -> AsyncIterator[Price]: ...

    @abstractmethod
    async def place_order(self, order: Order) -> OrderResult: ...

    @abstractmethod
    async def close_position(self, instrument: str) -> OrderResult: ...
