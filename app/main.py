from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.domain import Candle
from app.schemas import OrderRequest, SandboxSmokeTestRequest, StrategySignalRequest
from app.services.coinapi import CoinApiClient, CoinApiError
from app.services.exchange import ExchangeError, ExchangeGateway
from app.services.indicators import HAS_TALIB, IndicatorEngine
from app.services.order_store import OrderEventStore
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


def order_event_store(settings: Settings = Depends(get_settings)) -> OrderEventStore:
    return OrderEventStore(settings.order_database_path)


@app.get("/", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/setup-help", include_in_schema=False)
async def setup_help() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/setup-help/auto-trader", include_in_schema=False)
async def auto_trader_guide() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/strategy-lab", include_in_schema=False)
async def strategy_lab() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/execution-control", include_in_schema=False)
async def execution_control() -> FileResponse:
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


@app.get("/api/environment/status")
async def environment_status(
    settings: Settings = Depends(get_settings),
    store: OrderEventStore = Depends(order_event_store),
) -> dict[str, Any]:
    strategy_runs = store.list_strategy_runs(limit=1)
    risk_checks = store.list_risk_checks(limit=1)
    order_events = store.list_recent(limit=1)
    credentials = settings.exchange_credentials
    return {
        "mode": _execution_mode(settings),
        "paper_trading": settings.paper_trading,
        "sandbox_mode": settings.sandbox_mode,
        "live_enabled": settings.enable_live_trading,
        "kill_switch_enabled": settings.kill_switch_enabled,
        "exchange_connected": bool(settings.exchange_id_list),
        "configured_exchanges": settings.exchange_id_list,
        "testnet_keys_present": settings.sandbox_mode and any(credentials.values()),
        "sql_database": store.health(),
        "last_strategy_run": strategy_runs[0] if strategy_runs else None,
        "last_risk_decision": risk_checks[0] if risk_checks else None,
        "last_order_result": order_events[0] if order_events else None,
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
    store: OrderEventStore = Depends(order_event_store),
) -> Any:
    ids = [item.strip() for item in exchange_ids.split(",") if item.strip()] if exchange_ids else None
    try:
        tickers = _json(await gateway.fetch_tickers(symbol, ids))
        _record_market_snapshots(tickers, store)
        return tickers
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
    store: OrderEventStore = Depends(order_event_store),
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
        _record_strategy_run(request, signal, store)
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
    _record_strategy_run(request, signal, store)
    return signal


@app.get("/api/arbitrage/scan")
async def arbitrage_scan(
    symbol: str = "BTC/USDT",
    exchange_ids: str | None = Query(default=None, description="Comma-separated CCXT exchange ids"),
    settings: Settings = Depends(get_settings),
    gateway: ExchangeGateway = Depends(exchange_gateway),
    store: OrderEventStore = Depends(order_event_store),
) -> Any:
    ids = [item.strip() for item in exchange_ids.split(",") if item.strip()] if exchange_ids else None
    try:
        tickers = await gateway.fetch_tickers(symbol, ids)
    except ExchangeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    _record_market_snapshots(_json(tickers), store)

    strategy = ArbitrageStrategy(settings.min_arbitrage_profit_pct, settings.fee_buffer_pct)
    return _json(
        {
            "signal": strategy.signal(symbol, tickers),
            "opportunities": strategy.scan(symbol, tickers),
            "tickers": tickers,
        }
    )


@app.get("/api/balance/{exchange_id}")
async def balance(
    exchange_id: str,
    gateway: ExchangeGateway = Depends(exchange_gateway),
    store: OrderEventStore = Depends(order_event_store),
) -> Any:
    try:
        raw = await gateway.fetch_balance(exchange_id)
    except ExchangeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    _record_balances(exchange_id, raw, store)
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
    store: OrderEventStore = Depends(order_event_store),
) -> Any:
    risk = RiskManager(settings)
    try:
        risk.validate_order(request.amount, request.reference_price or request.price, request.price)
        _record_risk_check(request, "approved", "Risk checks passed", settings, store)
        result = await gateway.place_order(
            exchange_id=request.exchange_id,
            symbol=request.symbol,
            side=request.side,
            amount=request.amount,
            order_type=request.order_type,
            price=request.price,
            confirm_live_trading=request.confirm_live_trading,
        )
        event = _record_order_event(request, result, settings, store)
        return {**_json(result), "history_event": event}
    except RiskError as exc:
        _record_risk_check(request, "rejected", str(exc), settings, store)
        _record_order_event(request, {"status": "rejected", "message": str(exc)}, settings, store)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ExchangeError as exc:
        _record_order_event(request, {"status": "failed", "message": str(exc)}, settings, store)
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/sandbox/smoke-test")
async def sandbox_smoke_test(
    request: SandboxSmokeTestRequest,
    settings: Settings = Depends(get_settings),
    gateway: ExchangeGateway = Depends(exchange_gateway),
    store: OrderEventStore = Depends(order_event_store),
) -> Any:
    if not settings.sandbox_mode:
        raise HTTPException(status_code=422, detail="SANDBOX_MODE must be true for a sandbox smoke test")
    if settings.paper_trading:
        raise HTTPException(status_code=422, detail="Set PAPER_TRADING=false to send a sandbox testnet order")
    if not settings.enable_live_trading:
        raise HTTPException(status_code=422, detail="Set ENABLE_LIVE_TRADING=true to send a sandbox testnet order")
    if not request.confirm_sandbox_order:
        raise HTTPException(status_code=422, detail="Sandbox smoke test requires confirm_sandbox_order=true")
    if request.exchange_id not in settings.exchange_credentials:
        raise HTTPException(status_code=422, detail=f"Missing testnet API credentials for {request.exchange_id}")

    order_request = OrderRequest(
        exchange_id=request.exchange_id,
        symbol=request.symbol,
        side=request.side,
        amount=request.amount,
        order_type=request.order_type,
        price=request.price,
        reference_price=request.reference_price,
        confirm_live_trading=True,
    )
    risk = RiskManager(settings)
    try:
        risk.validate_order(order_request.amount, order_request.reference_price, order_request.price)
        _record_risk_check(order_request, "approved", "Sandbox smoke-test risk checks passed", settings, store)
        result = await gateway.place_order(
            exchange_id=order_request.exchange_id,
            symbol=order_request.symbol,
            side=order_request.side,
            amount=order_request.amount,
            order_type=order_request.order_type,
            price=order_request.price,
            confirm_live_trading=True,
        )
        event = _record_order_event(order_request, result, settings, store)
        return {
            "status": "submitted_to_sandbox",
            "message": "Sandbox testnet order submitted. Verify the result in order history and on the testnet account.",
            "result": _json(result),
            "history_event": event,
        }
    except RiskError as exc:
        _record_risk_check(order_request, "rejected", str(exc), settings, store)
        _record_order_event(order_request, {"status": "rejected", "message": str(exc)}, settings, store)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ExchangeError as exc:
        _record_order_event(order_request, {"status": "failed", "message": str(exc)}, settings, store)
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/orders/history")
async def order_history(
    limit: int = Query(default=25, ge=1, le=100),
    store: OrderEventStore = Depends(order_event_store),
) -> Any:
    return {"orders": store.list_recent(limit)}


@app.get("/api/risk/checks")
async def risk_check_history(
    limit: int = Query(default=25, ge=1, le=100),
    store: OrderEventStore = Depends(order_event_store),
) -> Any:
    return {"risk_checks": store.list_risk_checks(limit)}


@app.get("/api/strategies/runs")
async def strategy_run_history(
    limit: int = Query(default=25, ge=1, le=100),
    store: OrderEventStore = Depends(order_event_store),
) -> Any:
    return {"strategy_runs": store.list_strategy_runs(limit)}


@app.get("/api/market/snapshots")
async def market_snapshot_history(
    limit: int = Query(default=50, ge=1, le=200),
    store: OrderEventStore = Depends(order_event_store),
) -> Any:
    return {"snapshots": store.list_market_snapshots(limit)}


@app.get("/api/positions")
async def positions(limit: int = Query(default=100, ge=1, le=500), store: OrderEventStore = Depends(order_event_store)) -> Any:
    return {"positions": store.list_balances(limit)}


@app.get("/api/orders/reconcile")
async def reconcile_orders(
    exchange_id: str = "binance",
    symbol: str = "BTC/USDT",
    settings: Settings = Depends(get_settings),
    store: OrderEventStore = Depends(order_event_store),
) -> Any:
    recent = [
        item
        for item in store.list_recent(limit=50)
        if item["exchange_id"] == exchange_id and item["symbol"] == symbol
    ]
    if settings.paper_trading:
        return {
            "status": "paper_only",
            "exchange_id": exchange_id,
            "symbol": symbol,
            "message": "Paper orders are reconciled against the local SQL audit trail only.",
            "orders": recent,
        }
    return {
        "status": "manual_review_required",
        "exchange_id": exchange_id,
        "symbol": symbol,
        "message": "Live reconciliation needs exchange order ids and closed/open order polling before production use.",
        "orders": recent,
    }


@app.post("/api/backtests/run")
async def backtest_run(
    request: StrategySignalRequest,
    client: CoinApiClient = Depends(coinapi_client),
    gateway: ExchangeGateway = Depends(exchange_gateway),
    engine: IndicatorEngine = Depends(indicator_engine),
) -> Any:
    if request.strategy == "arbitrage":
        raise HTTPException(status_code=422, detail="Backtests require an OHLCV strategy, not arbitrage tickers")
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
    strategy = _indicator_strategy(request.strategy)
    signals = [
        _json(strategy.signal(request.symbol, candles[:index], engine.calculate(candles[:index])))
        for index in range(30, len(candles) + 1)
    ]
    actionable = [signal for signal in signals if signal["action"] in {"buy", "sell"}]
    return {
        "strategy": request.strategy,
        "symbol": request.symbol,
        "source": data_source,
        "warning": warning,
        "candles": len(candles),
        "signals_tested": len(signals),
        "actionable_signals": len(actionable),
        "last_signal": signals[-1] if signals else None,
    }


def _record_order_event(
    request: OrderRequest,
    result: dict[str, Any],
    settings: Settings,
    store: OrderEventStore,
) -> dict[str, Any]:
    event = {
        "created_at": datetime.now(UTC),
        "status": result.get("status", "submitted"),
        "exchange_id": request.exchange_id,
        "symbol": request.symbol,
        "side": request.side,
        "amount": request.amount,
        "order_type": request.order_type,
        "price": request.price,
        "reference_price": request.reference_price,
        "paper_trading": settings.paper_trading,
        "live_enabled": settings.enable_live_trading,
        "confirm_live_trading": request.confirm_live_trading,
        "result": result,
    }
    return store.add(_json(event))


def _record_strategy_run(
    request: StrategySignalRequest,
    signal: dict[str, Any],
    store: OrderEventStore,
) -> dict[str, Any]:
    return store.add_strategy_run(
        _json(
            {
                "created_at": datetime.now(UTC),
                "strategy": request.strategy,
                "symbol": request.symbol,
                "source": signal.get("metadata", {}).get("data_source", request.source),
                "action": signal.get("action", "hold"),
                "confidence": signal.get("confidence", 0),
                "reason": signal.get("reason", ""),
                "input": _json(request.model_dump()),
                "signal": signal,
            }
        )
    )


def _record_risk_check(
    request: OrderRequest,
    status: str,
    reason: str,
    settings: Settings,
    store: OrderEventStore,
) -> dict[str, Any]:
    reference_price = request.reference_price or request.price
    notional = request.amount * reference_price if reference_price else None
    return store.add_risk_check(
        _json(
            {
                "created_at": datetime.now(UTC),
                "status": status,
                "exchange_id": request.exchange_id,
                "symbol": request.symbol,
                "side": request.side,
                "amount": request.amount,
                "reference_price": reference_price,
                "notional": notional,
                "max_order_usd": settings.max_order_usd,
                "max_daily_loss_usd": settings.max_daily_loss_usd,
                "reason": reason,
            }
        )
    )


def _record_market_snapshots(tickers: list[dict[str, Any]], store: OrderEventStore) -> None:
    now = datetime.now(UTC)
    store.add_market_snapshots(
        _json(
            [
                {
                    "created_at": now,
                    "exchange_id": ticker["exchange"],
                    "symbol": ticker["symbol"],
                    "bid": ticker.get("bid"),
                    "ask": ticker.get("ask"),
                    "last": ticker.get("last"),
                    "exchange_timestamp": ticker.get("timestamp"),
                }
                for ticker in tickers
            ]
        )
    )


def _record_balances(exchange_id: str, raw: dict[str, Any], store: OrderEventStore) -> None:
    now = datetime.now(UTC)
    assets = set(raw.get("total", {})) | set(raw.get("free", {})) | set(raw.get("used", {}))
    for asset in sorted(assets):
        store.upsert_balance(
            _json(
                {
                    "updated_at": now,
                    "exchange_id": exchange_id,
                    "asset": asset,
                    "total": raw.get("total", {}).get(asset),
                    "free": raw.get("free", {}).get(asset),
                    "used": raw.get("used", {}).get(asset),
                }
            )
        )


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


def _execution_mode(settings: Settings) -> str:
    if settings.paper_trading:
        return "paper"
    if settings.sandbox_mode:
        return "sandbox"
    if settings.enable_live_trading:
        return "live"
    return "blocked"


def _coinapi_user_message(exc: CoinApiError) -> str:
    if exc.is_quota_error:
        return (
            "CoinAPI quota is unavailable for this account. Add usage credits, upgrade the "
            "CoinAPI subscription, or use Exchange OHLCV / CCXT fallback data for testing."
        )
    return str(exc)
