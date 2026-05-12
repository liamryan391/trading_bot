import type {
  ArbitrageScan,
  Health,
  PriceResponse,
  PublicConfig,
  StrategySignalRequest,
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
    payload = JSON.parse(text);
  }

  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : response.statusText;
    throw new Error(detail);
  }

  return payload as T;
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

export function getStrategySignal(body: StrategySignalRequest) {
  return request<TradeSignal>("/api/strategies/signal", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
