from __future__ import annotations

from app.domain import Candle, TradeSignal
from app.strategies.trend_following import _as_float, _clamp, _latest_close


class GridTradingStrategy:
    name = "grid_trading"

    def signal(
        self,
        symbol: str,
        candles: list[Candle],
        indicators: dict[str, float | int | str | None],
    ) -> TradeSignal:
        close = _latest_close(candles, indicators)
        atr = _as_float(indicators.get("atr_14"))

        if close is None:
            return TradeSignal(
                strategy=self.name,
                symbol=symbol,
                action="hold",
                confidence=0.0,
                reason="Not enough price data to build a grid.",
            )

        spacing = _grid_spacing(close, atr)
        lower_buy = close - spacing
        upper_sell = close + spacing
        confidence = _clamp(spacing / close * 120, 0.35, 0.75)

        return TradeSignal(
            strategy=self.name,
            symbol=symbol,
            action="hold",
            confidence=confidence,
            reason=(
                "Grid bot prepared passive buy and sell levels around the current price. "
                "No market order is suggested until price reaches a configured grid level."
            ),
            metadata={
                "center_price": close,
                "grid_spacing": spacing,
                "nearest_buy_level": lower_buy,
                "nearest_sell_level": upper_sell,
                "suggested_grid_levels": [
                    round(close - (spacing * 2), 8),
                    round(lower_buy, 8),
                    round(close, 8),
                    round(upper_sell, 8),
                    round(close + (spacing * 2), 8),
                ],
                "atr_14": atr,
            },
        )


class DCAStrategy:
    name = "dca"

    def signal(
        self,
        symbol: str,
        candles: list[Candle],
        indicators: dict[str, float | int | str | None],
    ) -> TradeSignal:
        close = _latest_close(candles, indicators)
        sma_20 = _as_float(indicators.get("sma_20"))
        rsi = _as_float(indicators.get("rsi_14"))

        if close is None:
            return TradeSignal(
                strategy=self.name,
                symbol=symbol,
                action="hold",
                confidence=0.0,
                reason="Not enough price data to evaluate a DCA entry.",
            )

        if rsi is not None and rsi >= 72:
            return TradeSignal(
                strategy=self.name,
                symbol=symbol,
                action="hold",
                confidence=0.25,
                reason="DCA paused because RSI suggests the market is overheated.",
                metadata={"close": close, "sma_20": sma_20, "rsi_14": rsi},
            )

        discount = ((sma_20 - close) / sma_20) if sma_20 else 0.0
        oversold_bonus = 0.1 if rsi is not None and rsi < 45 else 0.0
        confidence = _clamp(0.45 + max(discount, 0) + oversold_bonus, 0.4, 0.85)
        return TradeSignal(
            strategy=self.name,
            symbol=symbol,
            action="buy",
            confidence=confidence,
            reason=(
                "DCA bot can place the next scheduled accumulation order within the "
                "configured risk cap."
            ),
            metadata={
                "close": close,
                "sma_20": sma_20,
                "rsi_14": rsi,
                "discount_to_sma_20": discount,
            },
        )


class MarketMakingStrategy:
    name = "market_making"

    def signal(
        self,
        symbol: str,
        candles: list[Candle],
        indicators: dict[str, float | int | str | None],
    ) -> TradeSignal:
        close = _latest_close(candles, indicators)
        atr = _as_float(indicators.get("atr_14"))

        if close is None:
            return TradeSignal(
                strategy=self.name,
                symbol=symbol,
                action="hold",
                confidence=0.0,
                reason="Not enough price data to quote a market-making spread.",
            )

        half_spread = max((atr or 0) * 0.15, close * 0.001)
        bid_quote = close - half_spread
        ask_quote = close + half_spread
        spread_pct = ((ask_quote - bid_quote) / close) * 100

        return TradeSignal(
            strategy=self.name,
            symbol=symbol,
            action="hold",
            confidence=_clamp(0.5 + min(spread_pct / 10, 0.25), 0.45, 0.8),
            reason=(
                "Market-making bot prepared passive bid and ask quotes around fair value. "
                "Inventory limits and exchange order-book depth should be checked before live use."
            ),
            metadata={
                "fair_value": close,
                "suggested_bid": bid_quote,
                "suggested_ask": ask_quote,
                "quoted_spread_pct": spread_pct,
                "atr_14": atr,
            },
        )


def _grid_spacing(close: float, atr: float | None) -> float:
    if atr and atr > 0:
        return max(atr * 0.5, close * 0.0025)
    return close * 0.005
