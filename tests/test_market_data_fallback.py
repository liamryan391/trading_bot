from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, exchange_gateway, get_settings, order_event_store
from app.services.exchange import ExchangeError
from app.services.order_store import OrderEventStore


class FailingExchangeGateway:
    async def fetch_ticker(self, exchange_id: str, symbol: str):
        raise ExchangeError("network unavailable")

    async def fetch_tickers(self, symbol: str, exchange_ids: list[str] | None = None):
        raise ExchangeError("network unavailable")

    async def fetch_ohlcv(self, exchange_id: str, symbol: str, timeframe: str = "1h", limit: int = 100):
        raise ExchangeError("network unavailable")


class MarketDataFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.store = OrderEventStore(Path(self.temp_dir.name) / "orders.sqlite3")
        self.settings = Settings(
            demo_market_data_enabled=True,
            order_database_path=Path(self.temp_dir.name) / "orders.sqlite3",
        )
        app.dependency_overrides[get_settings] = lambda: self.settings
        app.dependency_overrides[exchange_gateway] = lambda: FailingExchangeGateway()
        app.dependency_overrides[order_event_store] = lambda: self.store
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.temp_dir.cleanup()

    def test_arbitrage_scan_uses_demo_tickers_when_exchange_apis_fail(self) -> None:
        response = self.client.get(
            "/api/arbitrage/scan",
            params={"symbol": "BTC/USDT", "exchange_ids": "binance,kraken,kucoin"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "demo")
        self.assertIn("Live market data is unavailable", payload["warning"])
        self.assertEqual(len(payload["tickers"]), 3)
        self.assertEqual(payload["tickers"][0]["source"], "demo")

    def test_strategy_signal_uses_demo_candles_when_coinapi_and_exchange_fail(self) -> None:
        response = self.client.post(
            "/api/strategies/signal",
            json={
                "strategy": "trend_following",
                "source": "coinapi",
                "symbol": "BTC/USDT",
                "exchange_id": "binance",
                "coinapi_symbol_id": "BINANCE_SPOT_BTC_USDT",
                "period_id": "1HRS",
                "timeframe": "1h",
                "limit": 100,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["metadata"]["data_source"], "demo")
        self.assertIn("Live market data is unavailable", payload["metadata"]["warning"])


if __name__ == "__main__":
    unittest.main()
