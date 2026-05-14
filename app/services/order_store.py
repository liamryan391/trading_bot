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

    def add_strategy_run(self, run: dict[str, Any]) -> dict[str, Any]:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO strategy_runs (
                    created_at,
                    strategy,
                    symbol,
                    source,
                    action,
                    confidence,
                    reason,
                    input_json,
                    signal_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run["created_at"],
                    run["strategy"],
                    run["symbol"],
                    run.get("source"),
                    run["action"],
                    run["confidence"],
                    run["reason"],
                    json.dumps(run.get("input", {}), separators=(",", ":")),
                    json.dumps(run.get("signal", {}), separators=(",", ":")),
                ),
            )
            run_id = cursor.lastrowid
        return {**run, "id": run_id}

    def add_risk_check(self, check: dict[str, Any]) -> dict[str, Any]:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO risk_checks (
                    created_at,
                    status,
                    exchange_id,
                    symbol,
                    side,
                    amount,
                    reference_price,
                    notional,
                    max_order_usd,
                    max_daily_loss_usd,
                    reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    check["created_at"],
                    check["status"],
                    check["exchange_id"],
                    check["symbol"],
                    check["side"],
                    check["amount"],
                    check.get("reference_price"),
                    check.get("notional"),
                    check["max_order_usd"],
                    check["max_daily_loss_usd"],
                    check["reason"],
                ),
            )
            check_id = cursor.lastrowid
        return {**check, "id": check_id}

    def add_market_snapshots(self, snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        stored: list[dict[str, Any]] = []
        with self._connection() as connection:
            for snapshot in snapshots:
                cursor = connection.execute(
                    """
                    INSERT INTO market_snapshots (
                        created_at,
                        exchange_id,
                        symbol,
                        bid,
                        ask,
                        last,
                        exchange_timestamp
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot["created_at"],
                        snapshot["exchange_id"],
                        snapshot["symbol"],
                        snapshot.get("bid"),
                        snapshot.get("ask"),
                        snapshot.get("last"),
                        snapshot.get("exchange_timestamp"),
                    ),
                )
                stored.append({**snapshot, "id": cursor.lastrowid})
        return stored

    def upsert_balance(self, balance: dict[str, Any]) -> dict[str, Any]:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO positions_balances (
                    updated_at,
                    exchange_id,
                    asset,
                    total,
                    free,
                    used
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(exchange_id, asset) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    total = excluded.total,
                    free = excluded.free,
                    used = excluded.used
                """,
                (
                    balance["updated_at"],
                    balance["exchange_id"],
                    balance["asset"],
                    balance.get("total"),
                    balance.get("free"),
                    balance.get("used"),
                ),
            )
        return balance

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

    def list_strategy_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    created_at,
                    strategy,
                    symbol,
                    source,
                    action,
                    confidence,
                    reason,
                    input_json,
                    signal_json
                FROM strategy_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_row_to_strategy_run(row) for row in rows]

    def list_risk_checks(self, limit: int = 10) -> list[dict[str, Any]]:
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
                    reference_price,
                    notional,
                    max_order_usd,
                    max_daily_loss_usd,
                    reason
                FROM risk_checks
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_row_to_risk_check(row) for row in rows]

    def list_market_snapshots(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    created_at,
                    exchange_id,
                    symbol,
                    bid,
                    ask,
                    last,
                    exchange_timestamp
                FROM market_snapshots
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_row_to_market_snapshot(row) for row in rows]

    def list_balances(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    updated_at,
                    exchange_id,
                    asset,
                    total,
                    free,
                    used
                FROM positions_balances
                ORDER BY updated_at DESC, exchange_id, asset
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_row_to_balance(row) for row in rows]

    def health(self) -> dict[str, Any]:
        try:
            with self._connection() as connection:
                connection.execute("SELECT 1").fetchone()
            return {"connected": True, "path": str(self.database_path)}
        except sqlite3.Error as exc:
            return {"connected": False, "path": str(self.database_path), "error": str(exc)}

    def clear(self) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM order_events")
            connection.execute("DELETE FROM strategy_runs")
            connection.execute("DELETE FROM risk_checks")
            connection.execute("DELETE FROM market_snapshots")
            connection.execute("DELETE FROM positions_balances")

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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    source TEXT NULL,
                    action TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    reason TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    signal_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_strategy_runs_created_at
                ON strategy_runs (created_at DESC)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS risk_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    exchange_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
                    amount REAL NOT NULL,
                    reference_price REAL NULL,
                    notional REAL NULL,
                    max_order_usd REAL NOT NULL,
                    max_daily_loss_usd REAL NOT NULL,
                    reason TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_risk_checks_created_at
                ON risk_checks (created_at DESC)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS market_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    exchange_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    bid REAL NULL,
                    ask REAL NULL,
                    last REAL NULL,
                    exchange_timestamp TEXT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_market_snapshots_symbol_created_at
                ON market_snapshots (symbol, created_at DESC)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS positions_balances (
                    exchange_id TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    total REAL NULL,
                    free REAL NULL,
                    used REAL NULL,
                    PRIMARY KEY (exchange_id, asset)
                )
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


def _row_to_strategy_run(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "strategy": row["strategy"],
        "symbol": row["symbol"],
        "source": row["source"],
        "action": row["action"],
        "confidence": row["confidence"],
        "reason": row["reason"],
        "input": json.loads(row["input_json"]),
        "signal": json.loads(row["signal_json"]),
    }


def _row_to_risk_check(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "status": row["status"],
        "exchange_id": row["exchange_id"],
        "symbol": row["symbol"],
        "side": row["side"],
        "amount": row["amount"],
        "reference_price": row["reference_price"],
        "notional": row["notional"],
        "max_order_usd": row["max_order_usd"],
        "max_daily_loss_usd": row["max_daily_loss_usd"],
        "reason": row["reason"],
    }


def _row_to_market_snapshot(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "exchange_id": row["exchange_id"],
        "symbol": row["symbol"],
        "bid": row["bid"],
        "ask": row["ask"],
        "last": row["last"],
        "exchange_timestamp": row["exchange_timestamp"],
    }


def _row_to_balance(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "updated_at": row["updated_at"],
        "exchange_id": row["exchange_id"],
        "asset": row["asset"],
        "total": row["total"],
        "free": row["free"],
        "used": row["used"],
    }
