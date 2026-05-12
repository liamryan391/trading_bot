from __future__ import annotations

from app.domain import Candle, TradeSignal
from app.strategies.trend_following import _as_float, _latest_close


class MeanReversionStrategy:
    name = "mean_reversion"

    def signal(
        self,
        symbol: str,
        candles: list[Candle],
        indicators: dict[str, float | int | str | None],
    ) -> TradeSignal:
        close = _latest_close(candles, indicators)
        lower = _as_float(indicators.get("bb_lower"))
        middle = _as_float(indicators.get("bb_middle"))
        upper = _as_float(indicators.get("bb_upper"))
        rsi = _as_float(indicators.get("rsi_14"))

        if None in (close, lower, middle, upper, rsi):
            return TradeSignal(
                strategy=self.name,
                symbol=symbol,
                action="hold",
                confidence=0.0,
                reason="Not enough Bollinger Band and RSI data for mean reversion analysis.",
            )

        band_width = max(upper - lower, 1e-9)
        if close < lower and rsi < 35:
            distance = min((lower - close) / band_width, 1.0)
            return TradeSignal(
                strategy=self.name,
                symbol=symbol,
                action="buy",
                confidence=0.55 + (distance * 0.35),
                reason="Price is below the lower Bollinger Band while RSI is oversold.",
                metadata={"close": close, "bb_lower": lower, "bb_middle": middle, "rsi_14": rsi},
            )

        if close > upper and rsi > 65:
            distance = min((close - upper) / band_width, 1.0)
            return TradeSignal(
                strategy=self.name,
                symbol=symbol,
                action="sell",
                confidence=0.55 + (distance * 0.35),
                reason="Price is above the upper Bollinger Band while RSI is overbought.",
                metadata={"close": close, "bb_upper": upper, "bb_middle": middle, "rsi_14": rsi},
            )

        return TradeSignal(
            strategy=self.name,
            symbol=symbol,
            action="hold",
            confidence=0.0,
            reason="Price is not stretched far enough from its recent range.",
            metadata={"close": close, "bb_lower": lower, "bb_middle": middle, "bb_upper": upper, "rsi_14": rsi},
        )

