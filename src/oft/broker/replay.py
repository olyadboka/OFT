"""ReplayBroker: replay stored candles through SimBroker's matching engine.

SimBroker's fill / P&L / margin / bracket logic reads prices only from
`self._mids` and `self._quote` — the GBM price source lives solely in
`stream_prices`. ReplayBroker subclasses SimBroker and swaps just that tape: it
walks a fixed list of candles, sets the mid from each bar's close, and yields a
bid/ask quote stamped with the candle's own time. Everything else (orders,
positions, P&L, brackets) is inherited unchanged, so a backtest over stored
history uses the exact same execution engine as a synthetic one.

The candles are passed in already loaded, so this class has no database
dependency and is unit-testable on its own. The `load_replay_broker` factory in
oft.marketdata bridges the CandleStore to this constructor.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import ROUND_HALF_UP

from oft.broker.models import Candle, Price
from oft.broker.sim import _PRICE_Q, SimBroker


class ReplayBroker(SimBroker):
    def __init__(
        self,
        instrument: str,
        candles: list[Candle],
        *,
        balance: str = "100000",
        currency: str = "USD",
        spread: str = "0.00012",
        leverage: int = 30,
        account_id: str = "replay-account",
    ) -> None:
        seed_price = str(candles[0].close) if candles else "1.00000"
        super().__init__(
            balance=balance,
            currency=currency,
            spread=spread,
            leverage=leverage,
            instruments={instrument: seed_price},
            account_id=account_id,
        )
        self._instrument = instrument
        self._candles = list(candles)

    async def stream_prices(
        self, instruments: list[str] | None = None
    ) -> AsyncIterator[Price]:
        half = self._spread / 2
        for candle in self._candles:
            self._mids[self._instrument] = candle.close
            self._check_brackets(self._instrument)
            yield Price(
                instrument=self._instrument,
                time=candle.time,
                bid=(candle.close - half).quantize(_PRICE_Q, ROUND_HALF_UP),
                ask=(candle.close + half).quantize(_PRICE_Q, ROUND_HALF_UP),
            )

    async def get_candles(
        self, instrument: str, granularity: str = "M1", count: int = 500
    ) -> list[Candle]:
        return list(self._candles[-count:]) if count else list(self._candles)
