from __future__ import annotations

from decimal import Decimal

from app.config import Settings


class RiskError(ValueError):
    """Raised when a requested order violates configured risk limits."""


class RiskManager:
    def __init__(self, settings: Settings):
        self.settings = settings

    def validate_order(
        self,
        amount: float,
        reference_price: float | None,
        order_price: float | None = None,
    ) -> None:
        if self.settings.kill_switch_enabled:
            raise RiskError("Kill switch is enabled; all order placement is blocked")
        if amount <= 0:
            raise RiskError("Order amount must be greater than zero")
        if reference_price is None or reference_price <= 0:
            raise RiskError("A positive reference price is required for risk checks")

        notional = Decimal(str(amount)) * Decimal(str(reference_price))
        if notional < self.settings.min_order_usd:
            raise RiskError(
                f"Order notional {notional:.2f} is below MIN_ORDER_USD "
                f"{self.settings.min_order_usd:.2f}"
            )
        if notional > self.settings.max_order_usd:
            raise RiskError(
                f"Order notional {notional:.2f} exceeds MAX_ORDER_USD "
                f"{self.settings.max_order_usd:.2f}"
            )
        if order_price is not None:
            slippage_pct = (
                abs(Decimal(str(order_price)) - Decimal(str(reference_price)))
                / Decimal(str(reference_price))
                * Decimal("100")
            )
            if slippage_pct > self.settings.max_slippage_pct:
                raise RiskError(
                    f"Order price slippage {slippage_pct:.3f}% exceeds MAX_SLIPPAGE_PCT "
                    f"{self.settings.max_slippage_pct:.3f}%"
                )

    def position_size_for_notional(self, notional_usd: Decimal, reference_price: float) -> float:
        if notional_usd > self.settings.max_order_usd:
            raise RiskError(f"Requested notional exceeds MAX_ORDER_USD {self.settings.max_order_usd}")
        if reference_price <= 0:
            raise RiskError("Reference price must be positive")
        return float(notional_usd / Decimal(str(reference_price)))

