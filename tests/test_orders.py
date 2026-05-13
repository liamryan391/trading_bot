import unittest

from fastapi.testclient import TestClient

from app.main import ORDER_HISTORY, app


class OrderEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        ORDER_HISTORY.clear()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        ORDER_HISTORY.clear()

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


if __name__ == "__main__":
    unittest.main()
