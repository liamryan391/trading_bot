from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path
from typing import Any


class OrderEventStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def add(self, event: dict[str, Any]) -> dict[str, Any]:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO order_events (
                    created_at,
                    status,
                    exchange_id,
                    symbol,
                    side,
                    amount,
                    order_type,
                    price,
                    reference_price,
                    paper_trading,
                    live_enabled,
                    confirm_live_trading,
                    result_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["created_at"],
                    event["status"],
                    event["exchange_id"],
                    event["symbol"],
                    event["side"],
                    event["amount"],
                    event["order_type"],
                    event.get("price"),
                    event.get("reference_price"),
                    int(event["paper_trading"]),
                    int(event["live_enabled"]),
                    int(event["confirm_live_trading"]),
                    json.dumps(event.get("result", {}), separators=(",", ":")),
                ),
            )
            event_id = cursor.lastrowid
        return {**event, "id": event_id}

    def list_recent(self, limit: int = 25) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    created_at,
                    status,
                    exchange_id,
                    symbol,
                    side,
                    amount,
                    order_type,
                    price,
                    reference_price,
                    paper_trading,
                    live_enabled,
                    confirm_live_trading,
                    result_json
                FROM order_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_row_to_event(row) for row in rows]

    def clear(self) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM order_events")

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS order_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    exchange_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
                    amount REAL NOT NULL,
                    order_type TEXT NOT NULL,
                    price REAL NULL,
                    reference_price REAL NULL,
                    paper_trading INTEGER NOT NULL,
                    live_enabled INTEGER NOT NULL,
                    confirm_live_trading INTEGER NOT NULL,
                    result_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_order_events_created_at
                ON order_events (created_at DESC)
                """
            )


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "status": row["status"],
        "exchange_id": row["exchange_id"],
        "symbol": row["symbol"],
        "side": row["side"],
        "amount": row["amount"],
        "order_type": row["order_type"],
        "price": row["price"],
        "reference_price": row["reference_price"],
        "paper_trading": bool(row["paper_trading"]),
        "live_enabled": bool(row["live_enabled"]),
        "confirm_live_trading": bool(row["confirm_live_trading"]),
        "result": json.loads(row["result_json"]),
    }
