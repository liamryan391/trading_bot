from __future__ import annotations

from typing import Protocol

from app.domain import Candle, Ticker, TradeSignal


class IndicatorStrategy(Protocol):
    name: str

    def signal(
        self,
        symbol: str,
        candles: list[Candle],
        indicators: dict[str, float | int | str | None],
    ) -> TradeSignal:
        ...


class TickerStrategy(Protocol):
    name: str

    def signal(self, symbol: str, tickers: list[Ticker]) -> TradeSignal:
        ...

