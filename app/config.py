from __future__ import annotations

import json
from decimal import Decimal
from functools import lru_cache
from typing import Any

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"

    coinapi_key: SecretStr | None = Field(default=None, alias="COINAPI_KEY")
    coinapi_base_url: str = "https://rest.coinapi.io"

    exchange_ids: str = "binance,kraken,kucoin"
    exchange_api_keys_json: str = "{}"
    default_symbol: str = "BTC/USDT"
    default_coinapi_symbol_id: str = "BINANCE_SPOT_BTC_USDT"

    paper_trading: bool = True
    enable_live_trading: bool = False
    sandbox_mode: bool = True

    max_order_usd: Decimal = Decimal("25")
    max_daily_loss_usd: Decimal = Decimal("100")
    min_arbitrage_profit_pct: Decimal = Decimal("0.35")
    fee_buffer_pct: Decimal = Decimal("0.10")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def exchange_id_list(self) -> list[str]:
        return [exchange.strip() for exchange in self.exchange_ids.split(",") if exchange.strip()]

    @property
    def exchange_credentials(self) -> dict[str, dict[str, Any]]:
        if not self.exchange_api_keys_json.strip():
            return {}
        try:
            parsed = json.loads(self.exchange_api_keys_json)
        except json.JSONDecodeError as exc:
            raise ValueError("EXCHANGE_API_KEYS_JSON must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("EXCHANGE_API_KEYS_JSON must be a JSON object")
        return parsed

    @property
    def coinapi_key_value(self) -> str | None:
        return self.coinapi_key.get_secret_value() if self.coinapi_key else None

    def public_dict(self) -> dict[str, Any]:
        return {
            "app_env": self.app_env,
            "coinapi_configured": bool(self.coinapi_key_value),
            "coinapi_base_url": self.coinapi_base_url,
            "exchange_ids": self.exchange_id_list,
            "default_symbol": self.default_symbol,
            "default_coinapi_symbol_id": self.default_coinapi_symbol_id,
            "paper_trading": self.paper_trading,
            "enable_live_trading": self.enable_live_trading,
            "sandbox_mode": self.sandbox_mode,
            "max_order_usd": str(self.max_order_usd),
            "max_daily_loss_usd": str(self.max_daily_loss_usd),
            "min_arbitrage_profit_pct": str(self.min_arbitrage_profit_pct),
            "fee_buffer_pct": str(self.fee_buffer_pct),
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

