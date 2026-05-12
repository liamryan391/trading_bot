from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


Action = Literal["buy", "sell", "hold", "arbitrage"]
Side = Literal["buy", "sell"]


@dataclass(frozen=True)
class Candle:
    time_start: datetime | None
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades_count: int | None = None


@dataclass(frozen=True)
class Ticker:
    exchange: str
    symbol: str
    bid: float | None
    ask: float | None
    last: float | None
    timestamp: datetime | None = None


@dataclass(frozen=True)
class TradeSignal:
    strategy: str
    symbol: str
    action: Action
    confidence: float
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ArbitrageOpportunity:
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    gross_profit_pct: float
    estimated_net_profit_pct: float
    metadata: dict[str, Any] = field(default_factory=dict)

