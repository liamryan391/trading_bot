# Trading Bot API

Python and React crypto trading bot workspace for market analysis, strategy signals, arbitrage scanning, and guarded order execution.

The project is split into:

- `app/`: FastAPI backend, CoinAPI adapter, CCXT exchange adapter, indicators, risk checks, and strategies.
- `frontend/`: TypeScript, React, Vite, and TailwindCSS dashboard.
- `tests/`: unit tests for the core strategy logic.
- `app/static/`: built frontend assets served by FastAPI after `npm.cmd run frontend:build`.

This is not financial advice. The bot is built to start in paper mode so you can learn, test, and harden it before any live trading path is enabled.

## Features

- Dashboard at `/` for price checks, strategy signals, arbitrage scans, and system status.
- Setup Help page at `/setup-help` with install, environment, and usage guidance.
- Strategy Lab page at `/strategy-lab` for strategy behavior, readiness checks, and API route mapping.
- CoinAPI exchange rates and OHLCV market data.
- CCXT exchange ticker, OHLCV, balance, and order gateway.
- TA-Lib indicators when installed, with a pandas fallback if TA-Lib is not available.
- Strategies for arbitrage, trend following, mean reversion, GRID trading, DCA, and market making.
- Paper-trading default, live-trading opt-in, sandbox mode, and max order notional checks.

## Requirements

- Python 3.11 or newer.
- Node.js 20 or newer. This machine was checked with Node `v24.0.1`.
- A CoinAPI key for CoinAPI-powered prices and OHLCV candles.
- Optional exchange API keys for balances and order placement.

On Windows PowerShell, use `npm.cmd` instead of `npm` if script execution is disabled.

## Quick Start

From the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
npm.cmd --prefix frontend install
npm.cmd run frontend:build
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

Open:

- Dashboard: http://127.0.0.1:8000
- Setup Help: http://127.0.0.1:8000/setup-help
- Strategy Lab: http://127.0.0.1:8000/strategy-lab
- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## Configuration

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Important variables:

```env
COINAPI_KEY=your_coinapi_key
COINAPI_BASE_URL=https://rest.coinapi.io

EXCHANGE_IDS=binance,kraken,kucoin
DEFAULT_SYMBOL=BTC/USDT
DEFAULT_COINAPI_SYMBOL_ID=BINANCE_SPOT_BTC_USDT

PAPER_TRADING=true
ENABLE_LIVE_TRADING=false
SANDBOX_MODE=true

MAX_ORDER_USD=25
MAX_DAILY_LOSS_USD=100
MIN_ARBITRAGE_PROFIT_PCT=0.35
FEE_BUFFER_PCT=0.10
```

Optional CCXT credentials:

```env
EXCHANGE_API_KEYS_JSON={"binance":{"apiKey":"xxx","secret":"yyy"}}
```

Use API keys with the smallest permissions possible. Do not put wallet seed phrases, private keys, or recovery phrases in this app.

If you edit `.env` while the server is already running, restart Uvicorn. The backend caches settings at startup, so saved key changes are not visible until the process restarts.

## Frontend Development

The production frontend is built into `app/static`, which FastAPI serves.

Build production assets:

```powershell
npm.cmd run frontend:build
```

Run the Vite dev server:

```powershell
npm.cmd run frontend:dev
```

When using Vite dev mode, keep the FastAPI backend running on `http://127.0.0.1:8000`. The Vite config proxies `/api` and `/health` to FastAPI.

## Bot Workflow

1. Start the API server.
2. Open the dashboard.
3. Check that `/health` is OK and CoinAPI is configured.
4. Click `Refresh price` to fetch a CoinAPI exchange rate.
5. Choose the strategy from the selector.
6. Run the selected bot. Arbitrage scans exchange tickers; the other bots analyse OHLCV candles.
7. Review the JSON output before trusting a signal.
8. Keep `PAPER_TRADING=true` while testing.

If CoinAPI returns a quota/subscription error, the dashboard falls back to CCXT public exchange data for `Refresh price` and `Analyse signal`. The warning is still shown so you know CoinAPI did not provide the data.

## Dashboard Field Guide

- `Base`: the asset being priced, for example `BTC`.
- `Quote`: the currency used to price the base asset, for example `USD` or `USDT`.
- `Exchange symbol`: the CCXT trading pair used by exchanges, for example `BTC/USDT`.
- `CoinAPI symbol`: the CoinAPI market id used for CoinAPI OHLCV candles, for example `BINANCE_SPOT_BTC_USDT`.
- `Exchanges`: comma-separated CCXT exchange ids used by arbitrage scans, for example `binance,kraken,kucoin`.
- `Strategy`: the bot logic used by the main dashboard output panel.
- `Source`: the candle provider for non-arbitrage strategies. Use `CoinAPI` for CoinAPI candles or `Exchange OHLCV` for CCXT exchange candles.
- `OHLCV exchange`: the exchange used when `Source` is `Exchange OHLCV`, and also the fallback exchange if CoinAPI is unavailable.

Trend Following is the default selected strategy because it is the safest starter candle-based signal. Arbitrage is different from the candle strategies: it compares live bid/ask tickers across several exchanges, so the dashboard now switches the main output panel when Arbitrage is selected.

## Strategy Notes

Arbitrage:

- Uses CCXT public tickers across configured exchanges.
- Compares the lowest ask against the highest bid.
- Subtracts the configured fee buffer from both sides.
- Does not yet model withdrawal fees, transfer delays, order-book depth, borrow costs, or partial fills.

Trend following:

- Uses latest close, SMA 20, SMA 50, MACD histogram, and RSI.
- Emits buy, sell, or hold depending on trend alignment and overextension.

Mean reversion:

- Uses Bollinger Bands and RSI.
- Looks for prices stretched below the lower band or above the upper band.

GRID trading bot:

- Builds passive buy and sell levels around the latest price.
- Uses ATR when available to avoid grids that are too tight for current volatility.
- Returns a plan rather than forcing an immediate market order.

DCA bot:

- Checks whether the next scheduled accumulation buy should proceed.
- Pauses when RSI suggests the market is overheated.
- Keeps sizing and execution controlled by the existing risk and order gates.

Market making bot:

- Builds suggested passive bid and ask quotes around fair value.
- Uses ATR or a minimum spread to avoid quoting too tightly.
- Still requires inventory limits, order-book depth checks, and live exchange permissions before production use.

## Order Safety

Live order placement is blocked unless all of these are true:

- `PAPER_TRADING=false`
- `ENABLE_LIVE_TRADING=true`
- The order request includes `confirm_live_trading=true`
- The notional value passes `MAX_ORDER_USD`
- A positive `reference_price` or `price` is provided for risk checks

Start with exchange sandbox keys where possible. Keep early orders tiny, inspect exchange permissions, and verify fees and minimum order sizes for each venue.

## Useful API Routes

- `GET /health`
- `GET /api/config`
- `GET /api/price?base=BTC&quote=USD`
- `GET /api/coinapi/ohlcv?symbol_id=BINANCE_SPOT_BTC_USDT&period_id=1HRS&limit=100`
- `GET /api/indicators?source=coinapi&coinapi_symbol_id=BINANCE_SPOT_BTC_USDT`
- `POST /api/strategies/signal`
- `GET /api/arbitrage/scan?symbol=BTC/USDT&exchange_ids=binance,kraken,kucoin`
- `GET /api/balance/{exchange_id}`
- `POST /api/orders`

Example strategy request:

```json
{
  "strategy": "trend_following",
  "source": "coinapi",
  "symbol": "BTC/USDT",
  "exchange_ids": "binance,kraken,kucoin",
  "exchange_id": "binance",
  "coinapi_symbol_id": "BINANCE_SPOT_BTC_USDT",
  "period_id": "1HRS",
  "timeframe": "1h",
  "limit": 100
}
```

Example paper order request:

```json
{
  "exchange_id": "binance",
  "symbol": "BTC/USDT",
  "side": "buy",
  "amount": 0.0001,
  "order_type": "market",
  "reference_price": 50000,
  "confirm_live_trading": false
}
```

## Tests and Checks

Run backend tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Compile backend files:

```powershell
.\.venv\Scripts\python.exe -m compileall app tests
```

Build frontend:

```powershell
npm.cmd run frontend:build
```

Run all three before pushing to GitHub.

## Troubleshooting

CoinAPI errors:

- Check that `COINAPI_KEY` is set in `.env`.
- Confirm the CoinAPI symbol id, for example `BINANCE_SPOT_BTC_USDT`.
- Watch rate limits if repeated requests return `429`.
- A `403` quota/subscription response means the key is valid but the CoinAPI account has no available usage credits or active subscription. Add credits, upgrade the subscription, or use the app's CCXT exchange fallback while testing.

CCXT errors:

- Confirm the exchange id exists in CCXT.
- Confirm the symbol is valid for that exchange.
- Some exchanges do not support sandbox mode for every market.

TA-Lib:

- If TA-Lib is installed, `/health` reports `TA-Lib`.
- If not, the app uses `pandas-fallback`.
- Windows TA-Lib installs may require native binaries.

PowerShell npm issue:

- If `npm` is blocked by execution policy, use `npm.cmd`.

## CoinAPI References

The backend uses:

- `/v1/exchangerate/{asset_id_base}/{asset_id_quote}`
- `/v1/ohlcv/{symbol_id}/history`
- `/v1/ohlcv/{symbol_id}/latest`

Docs:

- https://www.coinapi.io/products/market-data-api/docs
- https://www.coinapi.io/products/market-data-api/docs/rest-api/exchange-rates/Get%20specific%20rate
- https://www.coinapi.io/products/market-data-api/docs/rest-api/ohlcv/overview
