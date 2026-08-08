"""
oft.broker.base — the abstract Broker contract.

`Broker` is the single boundary between OFT's brains (strategy, risk, dashboard)
and whatever actually holds prices and fills orders. Program to THIS, never to a
concrete engine, and swapping sim <-> live becomes one line (Dependency
Inversion Principle).

Note the shapes:
  * get_account_summary / get_candles / place_order / close_position
        -> request/response: `async def` returning a single value.
  * stream_prices
        -> one call, many values over time: an async *generator*
           (`async def` + `yield`), consumed with `async for`. It is NOT
           awaited like the others. This asymmetry is the thing to understand.

TODO — you write this (see the spec):
  class Broker(ABC):
      async def get_account_summary(self) -> AccountSummary: ...
      async def get_candles(self, instrument, granularity, count) -> list[Candle]: ...
      def stream_prices(self, instruments) -> AsyncIterator[Price]: ...
      async def place_order(self, order: Order) -> OrderResult: ...
      async def close_position(self, instrument: str) -> OrderResult: ...
"""

# from abc import ABC, abstractmethod
# from collections.abc import AsyncIterator
#
# from oft.broker.models import AccountSummary, Candle, Order, OrderResult, Price
