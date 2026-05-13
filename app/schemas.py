from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class OrderRequest(BaseModel):
    exchange_id: str = Field(examples=["binance"])
    symbol: str = Field(examples=["BTC/USDT"])
    side: Literal["buy", "sell"]
    amount: float = Field(gt=0)
    order_type: str = "market"
    price: float | None = Field(default=None, gt=0)
    reference_price: float | None = Field(default=None, gt=0)
    confirm_live_trading: bool = False


class StrategySignalRequest(BaseModel):
    strategy: Literal[
        "arbitrage",
        "trend_following",
        "mean_reversion",
        "grid_trading",
        "dca",
        "market_making",
    ]
    source: Literal["coinapi", "exchange"] = "coinapi"
    symbol: str = "BTC/USDT"
    exchange_ids: str | None = Field(
        default=None,
        description="Comma-separated CCXT exchange ids for arbitrage",
    )
    exchange_id: str = "binance"
    coinapi_symbol_id: str = "BINANCE_SPOT_BTC_USDT"
    period_id: str = "1HRS"
    timeframe: str = "1h"
    limit: int = Field(default=100, ge=30, le=1000)

