from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.domain import Candle
from app.schemas import OrderRequest, StrategySignalRequest
from app.services.coinapi import CoinApiClient, CoinApiError
from app.services.exchange import ExchangeError, ExchangeGateway
from app.services.indicators import HAS_TALIB, IndicatorEngine
from app.services.risk import RiskError, RiskManager
from app.strategies import (
    ArbitrageStrategy,
    DCAStrategy,
    GridTradingStrategy,
    MarketMakingStrategy,
    MeanReversionStrategy,
    TrendFollowingStrategy,
)
from app.strategies.base import IndicatorStrategy

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

app = FastAPI(
    title="Trading Bot API",
    version="0.1.0",
    description=(
        "Crypto market analysis API using CoinAPI, CCXT, TA-Lib-compatible indicators, "
        "and guarded paper/live execution."
    ),
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _json(data: Any) -> Any:
    if is_dataclass(data):
        return jsonable_encoder(asdict(data))
    if isinstance(data, list):
        return [_json(item) for item in data]
    if isinstance(data, dict):
        return {key: _json(value) for key, value in data.items()}
    if isinstance(data, Decimal):
        return float(data)
    if isinstance(data, datetime):
        return data.isoformat()
    return jsonable_encoder(data)


def coinapi_client(settings: Settings = Depends(get_settings)) -> CoinApiClient:
    return CoinApiClient(settings)


def exchange_gateway(settings: Settings = Depends(get_settings)) -> ExchangeGateway:
    return ExchangeGateway(settings)


def indicator_engine() -> IndicatorEngine:
    return IndicatorEngine()


@app.get("/", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/setup-help", include_in_schema=False)
async def setup_help() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/strategy-lab", include_in_schema=False)
async def strategy_lab() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "paper_trading": settings.paper_trading,
        "coinapi_configured": bool(settings.coinapi_key_value),
        "talib_backend": "TA-Lib" if HAS_TALIB else "pandas-fallback",
    }


@app.get("/api/config")
async def config(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    return settings.public_dict()


@app.get("/api/strategies")
async def strategies() -> dict[str, Any]:
    return {
        "strategies": [
            {
                "id": "arbitrage",
                "name": "Arbitrage",
                "kind": "ticker",
                "data_source": "CCXT tickers across configured exchanges",
            },
            {
                "id": "trend_following",
                "name": "Trend Following",
                "kind": "ohlcv",
                "data_source": "CoinAPI or CCXT OHLCV",
            },
            {
                "id": "mean_reversion",
                "name": "Mean Reversion",
                "kind": "ohlcv",
                "data_source": "CoinAPI or CCXT OHLCV",
            },
            {
                "id": "grid_trading",
                "name": "Grid Trading Bot",
                "kind": "ohlcv",
                "data_source": "CoinAPI or CCXT OHLCV",
            },
            {
                "id": "dca",
                "name": "DCA Bot",
                "kind": "ohlcv",
                "data_source": "CoinAPI or CCXT OHLCV",
            },
            {
                "id": "market_making",
                "name": "Market Making Bot",
                "kind": "ohlcv",
                "data_source": "CoinAPI or CCXT OHLCV",
            },
        ]
    }


@app.get("/api/price")
async def price(
    base: str = "BTC",
    quote: str = "USD",
    fallback_exchange_id: str = "binance",
    fallback_symbol: str | None = None,
    client: CoinApiClient = Depends(coinapi_client),
    gateway: ExchangeGateway = Depends(exchange_gateway),
) -> Any:
    try:
        payload = await client.get_exchange_rate(base, quote)
        return {**payload, "source": "coinapi"}
    except CoinApiError as exc:
        symbol = fallback_symbol or _fallback_symbol(base, quote)
        try:
            ticker = await gateway.fetch_ticker(fallback_exchange_id, symbol)
        except ExchangeError as fallback_exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"{_coinapi_user_message(exc)} Exchange fallback also failed on "
                    f"{fallback_exchange_id} {symbol}: {fallback_exc}"
                ),
            ) from fallback_exc

        rate = _ticker_rate(ticker.bid, ticker.ask, ticker.last)
        if rate is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"{_coinapi_user_message(exc)} Exchange fallback returned no usable "
                    f"bid/ask/last price for {fallback_exchange_id} {symbol}."
                ),
            ) from exc

        return {
            "asset_id_base": base.upper(),
            "asset_id_quote": quote.upper(),
            "rate": rate,
            "time": ticker.timestamp,
            "source": "ccxt",
            "exchange": fallback_exchange_id,
            "symbol": symbol,
            "warning": _coinapi_user_message(exc),
        }


@app.get("/api/coinapi/ohlcv")
async def coinapi_ohlcv(
    symbol_id: str = "BINANCE_SPOT_BTC_USDT",
    period_id: str = "1HRS",
    limit: int = Query(default=100, ge=30, le=1000),
    latest: bool = True,
    client: CoinApiClient = Depends(coinapi_client),
) -> Any:
    try:
        candles = (
            await client.get_ohlcv_latest(symbol_id, period_id, limit)
            if latest
            else await client.get_ohlcv_history(symbol_id, period_id, limit=limit)
        )
        return _json(candles)
    except CoinApiError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/exchanges/ticker")
async def exchange_ticker(
    exchange_id: str = "binance",
    symbol: str = "BTC/USDT",
    gateway: ExchangeGateway = Depends(exchange_gateway),
) -> Any:
    try:
        return _json(await gateway.fetch_ticker(exchange_id, symbol))
    except ExchangeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/exchanges/tickers")
async def exchange_tickers(
    symbol: str = "BTC/USDT",
    exchange_ids: str | None = Query(default=None, description="Comma-separated CCXT exchange ids"),
    gateway: ExchangeGateway = Depends(exchange_gateway),
) -> Any:
    ids = [item.strip() for item in exchange_ids.split(",") if item.strip()] if exchange_ids else None
    try:
        return _json(await gateway.fetch_tickers(symbol, ids))
    except ExchangeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/indicators")
async def indicators(
    source: str = Query(default="coinapi", pattern="^(coinapi|exchange)$"),
    symbol: str = "BTC/USDT",
    exchange_id: str = "binance",
    coinapi_symbol_id: str = "BINANCE_SPOT_BTC_USDT",
    period_id: str = "1HRS",
    timeframe: str = "1h",
    limit: int = Query(default=100, ge=30, le=1000),
    client: CoinApiClient = Depends(coinapi_client),
    gateway: ExchangeGateway = Depends(exchange_gateway),
    engine: IndicatorEngine = Depends(indicator_engine),
) -> Any:
    candles, data_source, warning = await _load_candles_with_metadata(
        source=source,
        symbol=symbol,
        exchange_id=exchange_id,
        coinapi_symbol_id=coinapi_symbol_id,
        period_id=period_id,
        timeframe=timeframe,
        limit=limit,
        client=client,
        gateway=gateway,
    )
    try:
        return {
            "symbol": symbol,
            "source": data_source,
            "warning": warning,
            "indicators": engine.calculate(candles),
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/strategies/signal")
async def strategy_signal(
    request: StrategySignalRequest,
    settings: Settings = Depends(get_settings),
    client: CoinApiClient = Depends(coinapi_client),
    gateway: ExchangeGateway = Depends(exchange_gateway),
    engine: IndicatorEngine = Depends(indicator_engine),
) -> Any:
    if request.strategy == "arbitrage":
        ids = (
            [item.strip() for item in request.exchange_ids.split(",") if item.strip()]
            if request.exchange_ids
            else None
        )
        try:
            tickers = await gateway.fetch_tickers(request.symbol, ids)
        except ExchangeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        strategy = ArbitrageStrategy(settings.min_arbitrage_profit_pct, settings.fee_buffer_pct)
        signal = _json(strategy.signal(request.symbol, tickers))
        signal["metadata"] = {
            **signal.get("metadata", {}),
            "data_source": "exchange_tickers",
            "exchanges_scanned": [ticker.exchange for ticker in tickers],
        }
        return signal

    candles, data_source, warning = await _load_candles_with_metadata(
        source=request.source,
        symbol=request.symbol,
        exchange_id=request.exchange_id,
        coinapi_symbol_id=request.coinapi_symbol_id,
        period_id=request.period_id,
        timeframe=request.timeframe,
        limit=request.limit,
        client=client,
        gateway=gateway,
    )
    indicators_payload = engine.calculate(candles)
    strategy = _indicator_strategy(request.strategy)
    signal = _json(strategy.signal(request.symbol, candles, indicators_payload))
    signal["metadata"] = {
        **signal.get("metadata", {}),
        "data_source": data_source,
        "warning": warning,
    }
    return signal


@app.get("/api/arbitrage/scan")
async def arbitrage_scan(
    symbol: str = "BTC/USDT",
    exchange_ids: str | None = Query(default=None, description="Comma-separated CCXT exchange ids"),
    settings: Settings = Depends(get_settings),
    gateway: ExchangeGateway = Depends(exchange_gateway),
) -> Any:
    ids = [item.strip() for item in exchange_ids.split(",") if item.strip()] if exchange_ids else None
    try:
        tickers = await gateway.fetch_tickers(symbol, ids)
    except ExchangeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    strategy = ArbitrageStrategy(settings.min_arbitrage_profit_pct, settings.fee_buffer_pct)
    return _json(
        {
            "signal": strategy.signal(symbol, tickers),
            "opportunities": strategy.scan(symbol, tickers),
            "tickers": tickers,
        }
    )


@app.get("/api/balance/{exchange_id}")
async def balance(exchange_id: str, gateway: ExchangeGateway = Depends(exchange_gateway)) -> Any:
    try:
        raw = await gateway.fetch_balance(exchange_id)
    except ExchangeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "exchange": exchange_id,
        "total": raw.get("total", {}),
        "free": raw.get("free", {}),
        "used": raw.get("used", {}),
    }


@app.post("/api/orders")
async def order(
    request: OrderRequest,
    settings: Settings = Depends(get_settings),
    gateway: ExchangeGateway = Depends(exchange_gateway),
) -> Any:
    risk = RiskManager(settings)
    try:
        risk.validate_order(request.amount, request.reference_price or request.price)
        return await gateway.place_order(
            exchange_id=request.exchange_id,
            symbol=request.symbol,
            side=request.side,
            amount=request.amount,
            order_type=request.order_type,
            price=request.price,
            confirm_live_trading=request.confirm_live_trading,
        )
    except (RiskError, ExchangeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _load_candles(
    *,
    source: str,
    symbol: str,
    exchange_id: str,
    coinapi_symbol_id: str,
    period_id: str,
    timeframe: str,
    limit: int,
    client: CoinApiClient,
    gateway: ExchangeGateway,
) -> list[Candle]:
    try:
        if source == "coinapi":
            return await client.get_ohlcv_latest(coinapi_symbol_id, period_id, limit)
        return await gateway.fetch_ohlcv(exchange_id, symbol, timeframe, limit)
    except CoinApiError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ExchangeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def _load_candles_with_metadata(
    *,
    source: str,
    symbol: str,
    exchange_id: str,
    coinapi_symbol_id: str,
    period_id: str,
    timeframe: str,
    limit: int,
    client: CoinApiClient,
    gateway: ExchangeGateway,
) -> tuple[list[Candle], str, str | None]:
    if source == "coinapi":
        try:
            return await client.get_ohlcv_latest(coinapi_symbol_id, period_id, limit), "coinapi", None
        except CoinApiError as exc:
            warning = _coinapi_user_message(exc)
            try:
                return await gateway.fetch_ohlcv(exchange_id, symbol, timeframe, limit), "exchange", warning
            except ExchangeError as fallback_exc:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        f"{warning} Exchange OHLCV fallback also failed on "
                        f"{exchange_id} {symbol}: {fallback_exc}"
                    ),
                ) from fallback_exc

    try:
        return await gateway.fetch_ohlcv(exchange_id, symbol, timeframe, limit), "exchange", None
    except ExchangeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _indicator_strategy(name: str) -> IndicatorStrategy:
    if name == "trend_following":
        return TrendFollowingStrategy()
    if name == "mean_reversion":
        return MeanReversionStrategy()
    if name == "grid_trading":
        return GridTradingStrategy()
    if name == "dca":
        return DCAStrategy()
    if name == "market_making":
        return MarketMakingStrategy()
    raise HTTPException(status_code=404, detail=f"Unknown strategy: {name}")


def _ticker_rate(bid: float | None, ask: float | None, last: float | None) -> float | None:
    if last and last > 0:
        return last
    if bid and ask and bid > 0 and ask > 0:
        return (bid + ask) / 2
    return bid or ask


def _fallback_symbol(base: str, quote: str) -> str:
    normalized_quote = "USDT" if quote.upper() == "USD" else quote.upper()
    return f"{base.upper()}/{normalized_quote}"


def _coinapi_user_message(exc: CoinApiError) -> str:
    if exc.is_quota_error:
        return (
            "CoinAPI quota is unavailable for this account. Add usage credits, upgrade the "
            "CoinAPI subscription, or use Exchange OHLCV / CCXT fallback data for testing."
        )
    return str(exc)
