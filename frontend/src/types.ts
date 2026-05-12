export type Health = {
  status: string;
  environment: string;
  paper_trading: boolean;
  coinapi_configured: boolean;
  talib_backend: string;
};

export type PublicConfig = {
  app_env: string;
  coinapi_configured: boolean;
  coinapi_base_url: string;
  exchange_ids: string[];
  default_symbol: string;
  default_coinapi_symbol_id: string;
  paper_trading: boolean;
  enable_live_trading: boolean;
  sandbox_mode: boolean;
  max_order_usd: string;
  max_daily_loss_usd: string;
  min_arbitrage_profit_pct: string;
  fee_buffer_pct: string;
};

export type TradeAction = "buy" | "sell" | "hold" | "arbitrage";

export type TradeSignal = {
  strategy: string;
  symbol: string;
  action: TradeAction;
  confidence: number;
  reason: string;
  metadata?: Record<string, unknown>;
};

export type Ticker = {
  exchange: string;
  symbol: string;
  bid: number | null;
  ask: number | null;
  last: number | null;
  timestamp?: string | null;
};

export type ArbitrageOpportunity = {
  symbol: string;
  buy_exchange: string;
  sell_exchange: string;
  buy_price: number;
  sell_price: number;
  gross_profit_pct: number;
  estimated_net_profit_pct: number;
  metadata?: Record<string, unknown>;
};

export type ArbitrageScan = {
  signal: TradeSignal;
  opportunities: ArbitrageOpportunity[];
  tickers: Ticker[];
};

export type StrategyId = "trend_following" | "mean_reversion";

export type StrategySignalRequest = {
  strategy: StrategyId;
  source: "coinapi" | "exchange";
  symbol: string;
  exchange_id: string;
  coinapi_symbol_id: string;
  period_id: string;
  timeframe: string;
  limit: number;
};

export type PriceResponse = {
  asset_id_base: string;
  asset_id_quote: string;
  rate: number;
  time?: string;
  source?: "coinapi" | "ccxt";
  exchange?: string;
  symbol?: string;
  warning?: string;
};
