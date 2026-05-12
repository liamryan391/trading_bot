from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.domain import Candle, Side, Ticker

try:
    import ccxt  # type: ignore
except ImportError:  # pragma: no cover - exercised only in missing dependency installs
    ccxt = None  # type: ignore


class ExchangeError(RuntimeError):
    """Raised when a CCXT exchange request fails."""


def _parse_ccxt_timestamp(value: int | float | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(float(value) / 1000, tz=UTC)


class ExchangeGateway:
    def __init__(self, settings: Settings):
        if ccxt is None:
            raise ExchangeError("ccxt is not installed. Run `pip install -e .` first.")
        self.settings = settings

    def configured_exchange_ids(self) -> list[str]:
        return self.settings.exchange_id_list

    def _exchange(self, exchange_id: str, sandbox: bool | None = None):
        if exchange_id not in ccxt.exchanges:
            raise ExchangeError(f"Unknown CCXT exchange: {exchange_id}")

        credentials = self.settings.exchange_credentials.get(exchange_id, {})
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class(
            {
                "enableRateLimit": True,
                "timeout": 20000,
                **credentials,
            }
        )
        use_sandbox = self.settings.sandbox_mode if sandbox is None else sandbox
        if use_sandbox and hasattr(exchange, "set_sandbox_mode"):
            try:
                exchange.set_sandbox_mode(True)
            except Exception:
                # Some exchanges expose the method but do not support sandbox for every market.
                pass
        return exchange

    async def fetch_ticker(self, exchange_id: str, symbol: str) -> Ticker:
        return await asyncio.to_thread(self._fetch_ticker_sync, exchange_id, symbol)

    async def fetch_tickers(self, symbol: str, exchange_ids: list[str] | None = None) -> list[Ticker]:
        ids = exchange_ids or self.configured_exchange_ids()
        tasks = [self.fetch_ticker(exchange_id, symbol) for exchange_id in ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        tickers: list[Ticker] = []
        errors: dict[str, str] = {}
        for exchange_id, result in zip(ids, results, strict=True):
            if isinstance(result, Exception):
                errors[exchange_id] = str(result)
            else:
                tickers.append(result)
        if not tickers and errors:
            raise ExchangeError(f"All ticker requests failed: {errors}")
        return tickers

    async def fetch_ohlcv(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> list[Candle]:
        return await asyncio.to_thread(self._fetch_ohlcv_sync, exchange_id, symbol, timeframe, limit)

    async def fetch_balance(self, exchange_id: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._fetch_balance_sync, exchange_id)

    async def place_order(
        self,
        exchange_id: str,
        symbol: str,
        side: Side,
        amount: float,
        order_type: str = "market",
        price: float | None = None,
        confirm_live_trading: bool = False,
    ) -> dict[str, Any]:
        if self.settings.paper_trading or not self.settings.enable_live_trading:
            return {
                "status": "paper",
                "exchange": exchange_id,
                "symbol": symbol,
                "side": side,
                "type": order_type,
                "amount": amount,
                "price": price,
                "message": "Order simulated because live trading is disabled.",
            }
        if not confirm_live_trading:
            raise ExchangeError("Live trading requires confirm_live_trading=true in the request body")
        return await asyncio.to_thread(
            self._place_order_sync,
            exchange_id,
            symbol,
            side,
            amount,
            order_type,
            price,
        )

    def _fetch_ticker_sync(self, exchange_id: str, symbol: str) -> Ticker:
        exchange = self._exchange(exchange_id, sandbox=False)
        try:
            raw = exchange.fetch_ticker(symbol)
        except Exception as exc:  # pragma: no cover - network and exchange dependent
            raise ExchangeError(f"{exchange_id} ticker failed for {symbol}: {exc}") from exc
        return Ticker(
            exchange=exchange_id,
            symbol=symbol,
            bid=_optional_float(raw.get("bid")),
            ask=_optional_float(raw.get("ask")),
            last=_optional_float(raw.get("last")),
            timestamp=_parse_ccxt_timestamp(raw.get("timestamp")),
        )

    def _fetch_ohlcv_sync(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[Candle]:
        exchange = self._exchange(exchange_id, sandbox=False)
        try:
            rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        except Exception as exc:  # pragma: no cover - network and exchange dependent
            raise ExchangeError(f"{exchange_id} OHLCV failed for {symbol}: {exc}") from exc
        return [
            Candle(
                time_start=_parse_ccxt_timestamp(row[0]),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
            )
            for row in rows
        ]

    def _fetch_balance_sync(self, exchange_id: str) -> dict[str, Any]:
        exchange = self._exchange(exchange_id)
        try:
            return exchange.fetch_balance()
        except Exception as exc:  # pragma: no cover - network and credential dependent
            raise ExchangeError(f"{exchange_id} balance request failed: {exc}") from exc

    def _place_order_sync(
        self,
        exchange_id: str,
        symbol: str,
        side: Side,
        amount: float,
        order_type: str,
        price: float | None,
    ) -> dict[str, Any]:
        exchange = self._exchange(exchange_id)
        try:
            return exchange.create_order(symbol, order_type, side, amount, price)
        except Exception as exc:  # pragma: no cover - network and credential dependent
            raise ExchangeError(f"{exchange_id} order failed: {exc}") from exc


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)
