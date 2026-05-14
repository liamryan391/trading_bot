import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from app.main import app, order_event_store
from app.services.order_store import OrderEventStore


class OrderEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.store = OrderEventStore(Path(self.temp_dir.name) / "orders.sqlite3")
        app.dependency_overrides[order_event_store] = lambda: self.store
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.temp_dir.cleanup()

    def test_paper_order_is_recorded_in_history(self) -> None:
        response = self.client.post(
            "/api/orders",
            json={
                "exchange_id": "binance",
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 0.0001,
                "order_type": "market",
                "reference_price": 50000,
                "confirm_live_trading": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "paper")
        self.assertEqual(payload["history_event"]["status"], "paper")

        history = self.client.get("/api/orders/history").json()["orders"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["symbol"], "BTC/USDT")
        self.assertTrue(history[0]["paper_trading"])

        checks = self.client.get("/api/risk/checks").json()["risk_checks"]
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0]["status"], "approved")

        environment = self.client.get("/api/environment/status").json()
        self.assertEqual(environment["mode"], "paper")
        self.assertEqual(environment["last_order_result"]["status"], "paper")
        self.assertTrue(environment["sql_database"]["connected"])

    def test_rejected_order_is_recorded_in_history(self) -> None:
        response = self.client.post(
            "/api/orders",
            json={
                "exchange_id": "binance",
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 1,
                "order_type": "market",
                "reference_price": 1000,
                "confirm_live_trading": False,
            },
        )

        self.assertEqual(response.status_code, 422)
        history = self.client.get("/api/orders/history").json()["orders"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "rejected")

        checks = self.client.get("/api/risk/checks").json()["risk_checks"]
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0]["status"], "rejected")

    def test_sandbox_smoke_test_requires_non_paper_execution(self) -> None:
        response = self.client.post(
            "/api/sandbox/smoke-test",
            json={
                "exchange_id": "binance",
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": 0.0001,
                "order_type": "market",
                "reference_price": 50000,
                "confirm_sandbox_order": True,
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("PAPER_TRADING=false", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
