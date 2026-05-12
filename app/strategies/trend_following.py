from __future__ import annotations

from app.domain import Candle, TradeSignal


class TrendFollowingStrategy:
    name = "trend_following"

    def signal(
        self,
        symbol: str,
        candles: list[Candle],
        indicators: dict[str, float | int | str | None],
    ) -> TradeSignal:
        close = _latest_close(candles, indicators)
        sma_20 = _as_float(indicators.get("sma_20"))
        sma_50 = _as_float(indicators.get("sma_50"))
        macd_hist = _as_float(indicators.get("macd_hist"))
        rsi = _as_float(indicators.get("rsi_14"))

        if None in (close, sma_20, sma_50, macd_hist):
            return self._hold(symbol, "Not enough indicator data for trend confirmation.")

        bullish = close > sma_50 and sma_20 > sma_50 and macd_hist > 0
        bearish = close < sma_50 and sma_20 < sma_50 and macd_hist < 0

        if bullish and (rsi is None or rsi < 72):
            confidence = _clamp(0.55 + abs((sma_20 - sma_50) / sma_50), 0.55, 0.92)
            return TradeSignal(
                strategy=self.name,
                symbol=symbol,
                action="buy",
                confidence=confidence,
                reason="Price, moving averages, and MACD histogram agree with an upward trend.",
                metadata={"close": close, "sma_20": sma_20, "sma_50": sma_50, "macd_hist": macd_hist, "rsi_14": rsi},
            )

        if bearish and (rsi is None or rsi > 28):
            confidence = _clamp(0.55 + abs((sma_20 - sma_50) / sma_50), 0.55, 0.92)
            return TradeSignal(
                strategy=self.name,
                symbol=symbol,
                action="sell",
                confidence=confidence,
                reason="Price, moving averages, and MACD histogram agree with a downward trend.",
                metadata={"close": close, "sma_20": sma_20, "sma_50": sma_50, "macd_hist": macd_hist, "rsi_14": rsi},
            )

        return self._hold(symbol, "Trend indicators are mixed or overextended.")

    def _hold(self, symbol: str, reason: str) -> TradeSignal:
        return TradeSignal(strategy=self.name, symbol=symbol, action="hold", confidence=0.0, reason=reason)


def _latest_close(candles: list[Candle], indicators: dict[str, float | int | str | None]) -> float | None:
    value = _as_float(indicators.get("latest_close"))
    if value is not None:
        return value
    return candles[-1].close if candles else None


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))

