import type {
  ArbitrageScan,
  Health,
  OrderHistoryResponse,
  OrderRequest,
  PriceResponse,
  PublicConfig,
  StrategySignalRequest,
  Ticker,
  TradeSignal,
} from "../types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    ...init,
  });

  let payload: unknown = null;
  const text = await response.text();
  if (text) {
    payload = parseResponseBody(text, response.headers.get("content-type"));
  }

  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : typeof payload === "string" && payload.trim()
          ? payload
        : response.statusText;
    throw new Error(detail);
  }

  return payload as T;
}

function parseResponseBody(text: string, contentType: string | null) {
  const trimmed = text.trim();
  const looksJson = trimmed.startsWith("{") || trimmed.startsWith("[");
  if (contentType?.includes("application/json") || looksJson) {
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  }
  return text;
}

export function getHealth() {
  return request<Health>("/health");
}

export function getConfig() {
  return request<PublicConfig>("/api/config");
}

export function getPrice(base: string, quote: string, fallbackExchangeId: string, fallbackSymbol: string) {
  const params = new URLSearchParams({
    base,
    quote,
    fallback_exchange_id: fallbackExchangeId,
    fallback_symbol: fallbackSymbol,
  });
  return request<PriceResponse>(`/api/price?${params.toString()}`);
}

export function scanArbitrage(symbol: string, exchangeIds: string) {
  const params = new URLSearchParams({ symbol });
  if (exchangeIds.trim()) {
    params.set("exchange_ids", exchangeIds);
  }
  return request<ArbitrageScan>(`/api/arbitrage/scan?${params.toString()}`);
}

export function getExchangeTickers(symbol: string, exchangeIds: string) {
  const params = new URLSearchParams({ symbol });
  if (exchangeIds.trim()) {
    params.set("exchange_ids", exchangeIds);
  }
  return request<Ticker[]>(`/api/exchanges/tickers?${params.toString()}`);
}

export function getStrategySignal(body: StrategySignalRequest) {
  return request<TradeSignal>("/api/strategies/signal", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function placeOrder(body: OrderRequest) {
  return request<Record<string, unknown>>("/api/orders", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getOrderHistory() {
  return request<OrderHistoryResponse>("/api/orders/history");
}
