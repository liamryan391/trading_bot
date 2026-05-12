from __future__ import annotations

from decimal import Decimal

from app.config import Settings


class RiskError(ValueError):
    """Raised when a requested order violates configured risk limits."""


class RiskManager:
    def __init__(self, settings: Settings):
        self.settings = settings

    def validate_order(self, amount: float, reference_price: float | None) -> None:
        if amount <= 0:
            raise RiskError("Order amount must be greater than zero")
        if reference_price is None or reference_price <= 0:
            raise RiskError("A positive reference price is required for risk checks")

        notional = Decimal(str(amount)) * Decimal(str(reference_price))
        if notional > self.settings.max_order_usd:
            raise RiskError(
                f"Order notional {notional:.2f} exceeds MAX_ORDER_USD "
                f"{self.settings.max_order_usd:.2f}"
            )

    def position_size_for_notional(self, notional_usd: Decimal, reference_price: float) -> float:
        if notional_usd > self.settings.max_order_usd:
            raise RiskError(f"Requested notional exceeds MAX_ORDER_USD {self.settings.max_order_usd}")
        if reference_price <= 0:
            raise RiskError("Reference price must be positive")
        return float(notional_usd / Decimal(str(reference_price)))

