from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.config import Settings
from app.domain import Candle


class CoinApiError(RuntimeError):
    """Raised when CoinAPI cannot return usable market data."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        payload: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}

    @property
    def is_quota_error(self) -> bool:
        detail = " ".join(str(value) for value in self.payload.values()).lower()
        return self.status_code in {402, 403, 429} and (
            "quota" in detail or "usage credit" in detail or "subscription" in detail
        )


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


class CoinApiClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def _headers(self) -> dict[str, str]:
        api_key = self.settings.coinapi_key_value
        if not api_key:
            raise CoinApiError("COINAPI_KEY is not configured")
        return {"X-CoinAPI-Key": api_key}

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.settings.coinapi_base_url.rstrip('/')}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params=params, headers=self._headers)
        payload = _response_payload(response)
        error_payload = payload if isinstance(payload, dict) else {}
        if response.status_code == 429:
            raise CoinApiError("CoinAPI rate limit reached", response.status_code, error_payload)
        if response.status_code >= 400:
            detail = error_payload.get("detail") or error_payload.get("error") or response.text
            raise CoinApiError(
                f"CoinAPI request failed: {response.status_code}: {detail}",
                response.status_code,
                error_payload,
            )
        return payload

    async def get_exchange_rate(self, base_asset: str, quote_asset: str) -> dict[str, Any]:
        base = base_asset.upper()
        quote = quote_asset.upper()
        return await self._get(f"/v1/exchangerate/{base}/{quote}")

    async def get_ohlcv_history(
        self,
        symbol_id: str,
        period_id: str = "1HRS",
        time_start: datetime | None = None,
        time_end: datetime | None = None,
        limit: int = 100,
    ) -> list[Candle]:
        start = time_start or datetime.now(tz=UTC) - timedelta(hours=limit)
        params: dict[str, Any] = {
            "period_id": period_id,
            "time_start": start.isoformat().replace("+00:00", "Z"),
            "limit": limit,
        }
        if time_end:
            params["time_end"] = time_end.isoformat().replace("+00:00", "Z")
        data = await self._get(f"/v1/ohlcv/{symbol_id}/history", params=params)
        return [self._candle_from_coinapi(item) for item in data]

    async def get_ohlcv_latest(
        self,
        symbol_id: str,
        period_id: str = "1HRS",
        limit: int = 100,
    ) -> list[Candle]:
        params = {"period_id": period_id, "limit": limit}
        data = await self._get(f"/v1/ohlcv/{symbol_id}/latest", params=params)
        candles = [self._candle_from_coinapi(item) for item in data]
        return sorted(candles, key=lambda candle: candle.time_start or datetime.min.replace(tzinfo=UTC))

    @staticmethod
    def _candle_from_coinapi(item: dict[str, Any]) -> Candle:
        return Candle(
            time_start=_parse_time(item.get("time_period_start")),
            open=float(item["price_open"]),
            high=float(item["price_high"]),
            low=float(item["price_low"]),
            close=float(item["price_close"]),
            volume=float(item.get("volume_traded") or 0),
            trades_count=item.get("trades_count"),
        )


def _response_payload(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {}
