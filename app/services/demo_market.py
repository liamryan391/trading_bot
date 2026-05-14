from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from app.domain import Candle, Ticker


BASE_PRICES = {
    "BTC/USDT": 65000.0,
    "BTC/USD": 65000.0,
    "ETH/USDT": 3200.0,
    "ETH/USD": 3200.0,
    "SOL/USDT": 150.0,
    "SOL/USD": 150.0,
}


def demo_tickers(symbol: str, exchange_ids: list[str] | None = None) -> list[Ticker]:
    exchanges = exchange_ids or ["binance", "kraken", "kucoin"]
    base_price = _base_price(symbol)
    now = datetime.now(UTC)
    count = max(len(exchanges), 1)
    tickers: list[Ticker] = []

    for index, exchange_id in enumerate(exchanges):
        # Spread exchanges far enough apart that the arbitrage panel can demonstrate its flow.
        relative_position = index - ((count - 1) / 2)
        mid = base_price * (1 + (relative_position * 0.004))
        spread = base_price * (0.0008 + (index * 0.0001))
        tickers.append(
            Ticker(
                exchange=exchange_id,
                symbol=symbol,
                bid=round(mid - (spread / 2), 8),
                ask=round(mid + (spread / 2), 8),
                last=round(mid, 8),
                timestamp=now,
            )
        )

    return tickers


def demo_candles(symbol: str, limit: int = 100, timeframe: str = "1h") -> list[Candle]:
    candle_count = max(limit, 30)
    interval = _timeframe_delta(timeframe)
    base_price = _base_price(symbol)
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    previous_close = base_price * 0.985
    candles: list[Candle] = []

    for index in range(candle_count):
        progress = index / max(candle_count - 1, 1)
        trend = base_price * 0.035 * progress
        wave = math.sin(index / 4.5) * base_price * 0.006
        close = base_price + trend + wave
        open_price = previous_close
        high = max(open_price, close) + (base_price * (0.0015 + 0.0005 * abs(math.cos(index))))
        low = min(open_price, close) - (base_price * (0.0015 + 0.0005 * abs(math.sin(index))))
        volume = 900 + (math.sin(index / 3) + 1) * 220 + (index % 7) * 18
        candles.append(
            Candle(
                time_start=now - (interval * (candle_count - index)),
                open=round(open_price, 8),
                high=round(high, 8),
                low=round(low, 8),
                close=round(close, 8),
                volume=round(volume, 4),
            )
        )
        previous_close = close

    return candles


def _base_price(symbol: str) -> float:
    normalized = symbol.upper().replace("-", "/")
    if normalized in BASE_PRICES:
        return BASE_PRICES[normalized]
    return 100.0 + (sum(ord(character) for character in normalized) % 5000)


def _timeframe_delta(timeframe: str) -> timedelta:
    value = timeframe.strip().lower()
    if value.endswith("m") and value[:-1].isdigit():
        return timedelta(minutes=int(value[:-1]))
    if value.endswith("h") and value[:-1].isdigit():
        return timedelta(hours=int(value[:-1]))
    if value.endswith("d") and value[:-1].isdigit():
        return timedelta(days=int(value[:-1]))
    return timedelta(hours=1)
