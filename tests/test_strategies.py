from __future__ import annotations

import unittest
from decimal import Decimal

from app.domain import Candle, Ticker
from app.strategies.arbitrage import ArbitrageStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.trend_following import TrendFollowingStrategy


class StrategyTests(unittest.TestCase):
    def test_arbitrage_finds_cross_exchange_spread(self) -> None:
        strategy = ArbitrageStrategy(min_profit_pct=Decimal("0.20"), fee_buffer_pct=Decimal("0.05"))
        tickers = [
            Ticker(exchange="alpha", symbol="BTC/USDT", bid=100.0, ask=99.0, last=99.5),
            Ticker(exchange="beta", symbol="BTC/USDT", bid=101.0, ask=102.0, last=101.5),
        ]

        opportunities = strategy.scan("BTC/USDT", tickers)

        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0].buy_exchange, "alpha")
        self.assertEqual(opportunities[0].sell_exchange, "beta")
        self.assertGreater(opportunities[0].estimated_net_profit_pct, 0.20)

    def test_trend_following_emits_buy_when_trend_aligns(self) -> None:
        candles = [Candle(None, 100, 122, 99, 120, 10)]
        signal = TrendFollowingStrategy().signal(
            "BTC/USDT",
            candles,
            {
                "latest_close": 120,
                "sma_20": 115,
                "sma_50": 100,
                "macd_hist": 2,
                "rsi_14": 60,
            },
        )

        self.assertEqual(signal.action, "buy")
        self.assertGreater(signal.confidence, 0.5)

    def test_mean_reversion_emits_buy_when_oversold_below_band(self) -> None:
        candles = [Candle(None, 100, 102, 89, 90, 10)]
        signal = MeanReversionStrategy().signal(
            "BTC/USDT",
            candles,
            {
                "latest_close": 90,
                "bb_lower": 95,
                "bb_middle": 105,
                "bb_upper": 115,
                "rsi_14": 28,
            },
        )

        self.assertEqual(signal.action, "buy")
        self.assertGreater(signal.confidence, 0.5)


if __name__ == "__main__":
    unittest.main()

