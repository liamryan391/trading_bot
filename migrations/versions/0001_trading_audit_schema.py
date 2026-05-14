"""trading audit schema

Revision ID: 0001_trading_audit_schema
Revises:
Create Date: 2026-05-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_trading_audit_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("strategy", sa.String(length=80), nullable=False),
        sa.Column("symbol", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Numeric(10, 6), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("input_json", sa.Text(), nullable=False),
        sa.Column("signal_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_strategy_runs_created_at", "strategy_runs", ["created_at"])

    op.create_table(
        "risk_checks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("exchange_id", sa.String(length=80), nullable=False),
        sa.Column("symbol", sa.String(length=80), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.Numeric(28, 12), nullable=False),
        sa.Column("reference_price", sa.Numeric(28, 12), nullable=True),
        sa.Column("notional", sa.Numeric(28, 12), nullable=True),
        sa.Column("max_order_usd", sa.Numeric(28, 12), nullable=False),
        sa.Column("max_daily_loss_usd", sa.Numeric(28, 12), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_risk_checks_side"),
    )
    op.create_index("ix_risk_checks_created_at", "risk_checks", ["created_at"])

    op.create_table(
        "order_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("exchange_id", sa.String(length=80), nullable=False),
        sa.Column("symbol", sa.String(length=80), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.Numeric(28, 12), nullable=False),
        sa.Column("order_type", sa.String(length=40), nullable=False),
        sa.Column("price", sa.Numeric(28, 12), nullable=True),
        sa.Column("reference_price", sa.Numeric(28, 12), nullable=True),
        sa.Column("paper_trading", sa.Boolean(), nullable=False),
        sa.Column("live_enabled", sa.Boolean(), nullable=False),
        sa.Column("confirm_live_trading", sa.Boolean(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_order_events_side"),
    )
    op.create_index("ix_order_events_created_at", "order_events", ["created_at"])
    op.create_index("ix_order_events_symbol_status", "order_events", ["symbol", "status", "created_at"])

    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exchange_id", sa.String(length=80), nullable=False),
        sa.Column("symbol", sa.String(length=80), nullable=False),
        sa.Column("bid", sa.Numeric(28, 12), nullable=True),
        sa.Column("ask", sa.Numeric(28, 12), nullable=True),
        sa.Column("last", sa.Numeric(28, 12), nullable=True),
        sa.Column("exchange_timestamp", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_market_snapshots_symbol_created_at",
        "market_snapshots",
        ["symbol", "created_at"],
    )

    op.create_table(
        "positions_balances",
        sa.Column("exchange_id", sa.String(length=80), nullable=False),
        sa.Column("asset", sa.String(length=40), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total", sa.Numeric(28, 12), nullable=True),
        sa.Column("free", sa.Numeric(28, 12), nullable=True),
        sa.Column("used", sa.Numeric(28, 12), nullable=True),
        sa.PrimaryKeyConstraint("exchange_id", "asset", name="pk_positions_balances"),
    )


def downgrade() -> None:
    op.drop_table("positions_balances")
    op.drop_index("ix_market_snapshots_symbol_created_at", table_name="market_snapshots")
    op.drop_table("market_snapshots")
    op.drop_index("ix_order_events_symbol_status", table_name="order_events")
    op.drop_index("ix_order_events_created_at", table_name="order_events")
    op.drop_table("order_events")
    op.drop_index("ix_risk_checks_created_at", table_name="risk_checks")
    op.drop_table("risk_checks")
    op.drop_index("ix_strategy_runs_created_at", table_name="strategy_runs")
    op.drop_table("strategy_runs")
