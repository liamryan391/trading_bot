from __future__ import annotations

from decimal import Decimal

from app.domain import ArbitrageOpportunity, Ticker, TradeSignal


class ArbitrageStrategy:
    name = "arbitrage"

    def __init__(self, min_profit_pct: Decimal, fee_buffer_pct: Decimal):
        self.min_profit_pct = float(min_profit_pct)
        self.fee_buffer_pct = float(fee_buffer_pct)

    def scan(self, symbol: str, tickers: list[Ticker]) -> list[ArbitrageOpportunity]:
        valid = [ticker for ticker in tickers if ticker.bid and ticker.ask and ticker.bid > 0 and ticker.ask > 0]
        opportunities: list[ArbitrageOpportunity] = []

        for buy in valid:
            for sell in valid:
                if buy.exchange == sell.exchange:
                    continue
                gross_profit_pct = ((sell.bid - buy.ask) / buy.ask) * 100
                estimated_net_profit_pct = gross_profit_pct - (2 * self.fee_buffer_pct)
                if estimated_net_profit_pct >= self.min_profit_pct:
                    opportunities.append(
                        ArbitrageOpportunity(
                            symbol=symbol,
                            buy_exchange=buy.exchange,
                            sell_exchange=sell.exchange,
                            buy_price=buy.ask,
                            sell_price=sell.bid,
                            gross_profit_pct=gross_profit_pct,
                            estimated_net_profit_pct=estimated_net_profit_pct,
                            metadata={
                                "fee_buffer_pct_each_side": self.fee_buffer_pct,
                                "buy_timestamp": buy.timestamp,
                                "sell_timestamp": sell.timestamp,
                            },
                        )
                    )

        return sorted(opportunities, key=lambda item: item.estimated_net_profit_pct, reverse=True)

    def signal(self, symbol: str, tickers: list[Ticker]) -> TradeSignal:
        opportunities = self.scan(symbol, tickers)
        if not opportunities:
            return TradeSignal(
                strategy=self.name,
                symbol=symbol,
                action="hold",
                confidence=0.0,
                reason="No cross-exchange spread cleared the configured fee and profit threshold.",
                metadata={"tickers_seen": len(tickers)},
            )

        best = opportunities[0]
        confidence = min(max(best.estimated_net_profit_pct / (self.min_profit_pct * 2), 0.1), 1.0)
        return TradeSignal(
            strategy=self.name,
            symbol=symbol,
            action="arbitrage",
            confidence=confidence,
            reason=(
                f"Buy on {best.buy_exchange} at {best.buy_price:.8f} and sell on "
                f"{best.sell_exchange} at {best.sell_price:.8f}; estimated net spread "
                f"{best.estimated_net_profit_pct:.3f}%."
            ),
            metadata={"best_opportunity": best, "opportunity_count": len(opportunities)},
        )

