import {
  Activity,
  BarChart3,
  BookOpen,
  Bot,
  Cable,
  CheckCircle2,
  CircleAlert,
  Gauge,
  Home,
  KeyRound,
  LifeBuoy,
  Play,
  RefreshCw,
  Route,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import { getConfig, getHealth, getPrice, getStrategySignal, scanArbitrage } from "./lib/api";
import { formatNumber, formatPercent, titleCase } from "./lib/format";
import type {
  ArbitrageOpportunity,
  ArbitrageScan,
  Health,
  PriceResponse,
  PublicConfig,
  StrategyId,
  TradeSignal,
} from "./types";

type Page = "dashboard" | "setup-help" | "strategy-lab";

type BotForm = {
  base: string;
  quote: string;
  symbol: string;
  coinapiSymbol: string;
  exchanges: string;
  strategy: StrategyId;
  exchangeId: string;
  dataSource: "coinapi" | "exchange";
};

type LoadState = {
  health?: Health;
  config?: PublicConfig;
  loading: boolean;
  error?: string;
};

type Notice = {
  title: string;
  body: string;
  tone: "warning" | "danger";
};

const navItems: Array<{ page: Page; label: string; icon: typeof Home }> = [
  { page: "dashboard", label: "Dashboard", icon: Home },
  { page: "setup-help", label: "Setup Help", icon: LifeBuoy },
  { page: "strategy-lab", label: "Strategy Lab", icon: BarChart3 },
];

const defaultForm: BotForm = {
  base: "BTC",
  quote: "USD",
  symbol: "BTC/USDT",
  coinapiSymbol: "BINANCE_SPOT_BTC_USDT",
  exchanges: "binance,kraken,kucoin",
  strategy: "trend_following",
  exchangeId: "binance",
  dataSource: "coinapi",
};

function currentPage(): Page {
  const path = window.location.pathname;
  if (path === "/setup-help") return "setup-help";
  if (path === "/strategy-lab") return "strategy-lab";
  return "dashboard";
}

export default function App() {
  const [page, setPage] = useState<Page>(currentPage());
  const [system, setSystem] = useState<LoadState>({ loading: true });
  const [form, setForm] = useState<BotForm>(defaultForm);

  useEffect(() => {
    void refreshSystem();
  }, []);

  useEffect(() => {
    const onPopState = () => setPage(currentPage());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  async function refreshSystem() {
    setSystem((previous) => ({ ...previous, loading: true, error: undefined }));
    try {
      const [health, config] = await Promise.all([getHealth(), getConfig()]);
      setSystem({ health, config, loading: false });
      setForm((previous) => ({
        ...previous,
        symbol: config.default_symbol || previous.symbol,
        coinapiSymbol: config.default_coinapi_symbol_id || previous.coinapiSymbol,
        exchanges: config.exchange_ids.length ? config.exchange_ids.join(",") : previous.exchanges,
        exchangeId: config.exchange_ids[0] || previous.exchangeId,
      }));
    } catch (error) {
      setSystem({
        loading: false,
        error: error instanceof Error ? error.message : "Unable to load API status.",
      });
    }
  }

  function goTo(nextPage: Page) {
    const path = nextPage === "dashboard" ? "/" : `/${nextPage}`;
    window.history.pushState({}, "", path);
    setPage(nextPage);
  }

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <Header page={page} setPage={goTo} system={system} />
      <main className="mx-auto w-full max-w-7xl px-4 pb-12 pt-5 sm:px-6 lg:px-8">
        {page === "dashboard" && (
          <Dashboard
            form={form}
            setForm={setForm}
            system={system}
            refreshSystem={refreshSystem}
          />
        )}
        {page === "setup-help" && <SetupHelp system={system} />}
        {page === "strategy-lab" && <StrategyLab system={system} />}
      </main>
    </div>
  );
}

function Header({
  page,
  setPage,
  system,
}: {
  page: Page;
  setPage: (page: Page) => void;
  system: LoadState;
}) {
  const ready = system.health?.status === "ok";
  return (
    <header className="border-b border-white/10 bg-teal-950 text-white">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <div className="mb-3 flex items-center gap-2 text-sm font-bold uppercase text-teal-100">
              <Bot className="h-4 w-4" />
              Trading Bot API
            </div>
            <h1 className="text-4xl font-black leading-none tracking-normal sm:text-5xl lg:text-6xl">
              Market Control
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill tone={ready ? "success" : "warning"} icon={ready ? CheckCircle2 : CircleAlert}>
              {system.loading ? "Checking" : ready ? "API Online" : "Needs attention"}
            </StatusPill>
            <StatusPill tone={system.config?.paper_trading ? "neutral" : "warning"} icon={ShieldCheck}>
              {system.config?.paper_trading === false ? "Live enabled" : "Paper mode"}
            </StatusPill>
          </div>
        </div>

        <nav className="flex flex-wrap gap-2" aria-label="Primary navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = page === item.page;
            return (
              <button
                key={item.page}
                type="button"
                onClick={() => setPage(item.page)}
                className={`inline-flex min-h-11 items-center gap-2 rounded-lg px-4 py-2 text-sm font-extrabold transition ${
                  active
                    ? "bg-white text-teal-950"
                    : "bg-white/10 text-white hover:bg-white/15 focus:bg-white/15"
                }`}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
}

function Dashboard({
  form,
  setForm,
  system,
  refreshSystem,
}: {
  form: BotForm;
  setForm: (next: BotForm | ((previous: BotForm) => BotForm)) => void;
  system: LoadState;
  refreshSystem: () => Promise<void>;
}) {
  const [price, setPrice] = useState<PriceResponse | undefined>();
  const [signal, setSignal] = useState<TradeSignal | undefined>();
  const [arbitrage, setArbitrage] = useState<ArbitrageScan | undefined>();
  const [busyAction, setBusyAction] = useState<"price" | "signal" | "arbitrage" | undefined>();
  const [notice, setNotice] = useState<Notice | undefined>();

  const config = system.config;

  async function runAction(action: "price" | "signal" | "arbitrage") {
    setBusyAction(action);
    setNotice(undefined);
    try {
      if (action === "price") {
        const result = await getPrice(form.base, form.quote, form.exchangeId, form.symbol);
        setPrice(result);
        if (result.warning) {
          setNotice({
            title: "CoinAPI fallback active",
            body: `${result.warning} Showing fallback price from ${result.exchange} ${result.symbol}.`,
            tone: "warning",
          });
        }
      }
      if (action === "signal") {
        const result = await getStrategySignal({
          strategy: form.strategy,
          source: form.dataSource,
          symbol: form.symbol,
          exchange_id: form.exchangeId,
          coinapi_symbol_id: form.coinapiSymbol,
          period_id: "1HRS",
          timeframe: "1h",
          limit: 100,
        });
        setSignal(result);
        const warning = metadataString(result.metadata, "warning");
        const dataSource = metadataString(result.metadata, "data_source");
        if (warning) {
          setNotice({
            title: "CoinAPI fallback active",
            body: `${warning} Signal generated from ${dataSource || "exchange"} candles.`,
            tone: "warning",
          });
        }
      }
      if (action === "arbitrage") {
        setArbitrage(await scanArbitrage(form.symbol, form.exchanges));
      }
    } catch (error) {
      setNotice({
        title: "Request did not complete",
        body: error instanceof Error ? error.message : "The request failed.",
        tone: "danger",
      });
    } finally {
      setBusyAction(undefined);
    }
  }

  function updateField<K extends keyof BotForm>(key: K, value: BotForm[K]) {
    setForm((previous) => ({ ...previous, [key]: value }));
  }

  return (
    <div className="grid gap-5">
      <section className="overflow-hidden rounded-lg border border-line bg-panel p-4 shadow-panel">
        <form
          className="grid gap-4 xl:grid-cols-12"
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            void runAction("signal");
          }}
        >
          <TextField label="Base" value={form.base} onChange={(value) => updateField("base", value)} />
          <TextField label="Quote" value={form.quote} onChange={(value) => updateField("quote", value)} />
          <TextField
            className="xl:col-span-2"
            label="Exchange symbol"
            value={form.symbol}
            onChange={(value) => updateField("symbol", value)}
          />
          <TextField
            className="xl:col-span-3"
            label="CoinAPI symbol"
            value={form.coinapiSymbol}
            onChange={(value) => updateField("coinapiSymbol", value)}
          />
          <TextField
            className="xl:col-span-2"
            label="Exchanges"
            value={form.exchanges}
            onChange={(value) => updateField("exchanges", value)}
          />
          <SelectField
            className="xl:col-span-2"
            label="Strategy"
            value={form.strategy}
            onChange={(value) => updateField("strategy", value as StrategyId)}
            options={[
              { value: "trend_following", label: "Trend following" },
              { value: "mean_reversion", label: "Mean reversion" },
            ]}
          />
          <SelectField
            className="xl:col-span-2"
            label="Source"
            value={form.dataSource}
            onChange={(value) => updateField("dataSource", value as BotForm["dataSource"])}
            options={[
              { value: "coinapi", label: "CoinAPI" },
              { value: "exchange", label: "Exchange OHLCV" },
            ]}
          />
          <TextField
            className="xl:col-span-2"
            label="OHLCV exchange"
            value={form.exchangeId}
            onChange={(value) => updateField("exchangeId", value)}
          />

          <div className="flex flex-wrap items-end gap-2 xl:col-span-12">
            <ActionButton
              icon={RefreshCw}
              label="Refresh price"
              loading={busyAction === "price"}
              onClick={() => void runAction("price")}
            />
            <ActionButton
              icon={Play}
              label="Analyse signal"
              loading={busyAction === "signal"}
              tone="slate"
              onClick={() => void runAction("signal")}
            />
            <ActionButton
              icon={Route}
              label="Scan arbitrage"
              loading={busyAction === "arbitrage"}
              tone="amber"
              onClick={() => void runAction("arbitrage")}
            />
            <ActionButton
              icon={Activity}
              label="Reload status"
              loading={system.loading}
              tone="light"
              onClick={() => void refreshSystem()}
            />
          </div>
        </form>

        {notice && <Alert tone={notice.tone} title={notice.title} body={notice.body} />}
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Spot"
          value={price ? formatNumber(price.rate, 8) : "-"}
          caption={price ? priceCaption(price) : "CoinAPI or exchange fallback"}
        />
        <Metric
          label="Mode"
          value={config?.paper_trading === false ? "Live" : "Paper"}
          caption={config?.sandbox_mode ? "Sandbox on" : "Sandbox off"}
        />
        <Metric
          label="Indicators"
          value={system.health?.talib_backend ?? "-"}
          caption="TA-Lib or fallback"
        />
        <Metric
          label="Max order"
          value={config ? `$${config.max_order_usd}` : "-"}
          caption={config ? `${config.min_arbitrage_profit_pct}% min arbitrage` : "Risk limit"}
        />
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <Panel
          title="Signal"
          icon={TrendingUp}
          action={<SignalBadge action={signal?.action ?? "hold"} />}
        >
          <p className="min-h-12 text-sm leading-6 text-slate-600">
            {signal?.reason ?? "Run analysis to generate the next strategy signal."}
          </p>
          {signal && (
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <SignalStat label="Strategy" value={titleCase(signal.strategy)} />
              <SignalStat label="Confidence" value={`${Math.round(signal.confidence * 100)}%`} />
              <SignalStat label="Symbol" value={signal.symbol} />
            </div>
          )}
          {signal ? (
            <CodeBlock payload={signal} />
          ) : (
            <div className="mt-4">
              <EmptyState
                title="Waiting for analysis"
                body="Click Analyse signal to fetch candles, calculate indicators, and generate the strategy output."
              />
            </div>
          )}
        </Panel>

        <Panel
          title="Arbitrage"
          icon={Route}
          action={
            <span className="rounded-lg border border-line bg-slate-50 px-3 py-1 text-sm font-black">
              {arbitrage?.opportunities.length ?? 0}
            </span>
          }
        >
          <div className="grid gap-3">
            {(arbitrage?.opportunities.length ?? 0) > 0 ? (
              arbitrage?.opportunities.slice(0, 6).map((opportunity) => (
                <OpportunityRow key={`${opportunity.buy_exchange}-${opportunity.sell_exchange}`} item={opportunity} />
              ))
            ) : (
              <EmptyState
                title="No qualifying spread yet"
                body="Scan configured exchanges to compare bid and ask prices after the fee buffer."
              />
            )}
          </div>
        </Panel>
      </section>

      <Panel title="System" icon={Gauge}>
        {system.error ? (
          <Alert tone="danger" title="API status failed" body={system.error} />
        ) : (
          <div className="grid gap-4 lg:grid-cols-3">
            <ChecklistItem
              ready={Boolean(system.health?.coinapi_configured)}
              title="CoinAPI key"
              body={system.health?.coinapi_configured ? "Configured" : "Missing in .env"}
            />
            <ChecklistItem
              ready={config?.paper_trading !== false}
              title="Trading mode"
              body={config?.paper_trading === false ? "Live orders can be enabled" : "Paper trading default"}
            />
            <ChecklistItem
              ready={Boolean(config?.exchange_ids.length)}
              title="Exchanges"
              body={config?.exchange_ids.join(", ") || "No exchanges configured"}
            />
          </div>
        )}
        <CodeBlock payload={{ health: system.health, config: system.config }} />
      </Panel>
    </div>
  );
}

function SetupHelp({ system }: { system: LoadState }) {
  const commands = [
    "py -3.11 -m venv .venv",
    ".\\.venv\\Scripts\\Activate.ps1",
    "python -m pip install --upgrade pip",
    "pip install -e .",
    "npm.cmd --prefix frontend install",
    "npm.cmd run frontend:build",
    "uvicorn app.main:app --reload",
  ];

  return (
    <div className="grid gap-5">
      <PageIntro
        icon={BookOpen}
        title="Setup Help"
        body="Follow this page from top to bottom when preparing the bot on a new machine, adding keys, rebuilding the interface, or moving from paper trading toward live execution."
      />

      <section className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <Panel title="Install and Run" icon={Cable}>
          <ol className="grid gap-3">
            {commands.map((command, index) => (
              <li key={command} className="flex gap-3 rounded-lg border border-line bg-slate-50 p-3">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-md bg-teal-750 text-sm font-black text-white">
                  {index + 1}
                </span>
                <code className="min-w-0 overflow-x-auto whitespace-nowrap text-sm font-bold text-slate-800">
                  {command}
                </code>
              </li>
            ))}
          </ol>
        </Panel>

        <Panel title="Current Status" icon={Activity}>
          <div className="grid gap-3">
            <ChecklistItem
              ready={system.health?.status === "ok"}
              title="API server"
              body={system.health?.status === "ok" ? "Responding to /health" : "Start uvicorn first"}
            />
            <ChecklistItem
              ready={Boolean(system.health?.coinapi_configured)}
              title="CoinAPI"
              body={system.health?.coinapi_configured ? "Ready for market data" : "Add COINAPI_KEY to .env"}
            />
            <ChecklistItem
              ready={system.config?.paper_trading !== false}
              title="Execution safety"
              body={system.config?.paper_trading === false ? "Live mode configured" : "Paper mode active"}
            />
            <ChecklistItem
              ready={Boolean(system.config?.exchange_ids.length)}
              title="CCXT exchanges"
              body={system.config?.exchange_ids.join(", ") || "Add EXCHANGE_IDS to .env"}
            />
          </div>
        </Panel>
      </section>

      <section className="grid gap-5 lg:grid-cols-3">
        <GuideCard
          icon={KeyRound}
          title="1. Configure Keys"
          body="Copy .env.example to .env, add COINAPI_KEY, then add exchange keys only when you need private balance or order endpoints. Never use wallet seed phrases."
        />
        <GuideCard
          icon={BarChart3}
          title="2. Analyse Markets"
          body="Use Refresh price for CoinAPI spot rates, Analyse signal for trend or mean-reversion signals, and Scan arbitrage for cross-exchange spreads."
        />
        <GuideCard
          icon={ShieldCheck}
          title="3. Keep It Guarded"
          body="Stay in PAPER_TRADING=true until you have checked fees, liquidity, slippage, and exchange permissions with small dry-run orders."
        />
      </section>

      <Panel title="Environment Variables" icon={Gauge}>
        <div className="grid gap-3 md:grid-cols-2">
          {[
            ["COINAPI_KEY", "Required for CoinAPI price and OHLCV endpoints."],
            ["EXCHANGE_IDS", "Comma-separated CCXT exchange ids used by arbitrage scanning."],
            ["EXCHANGE_API_KEYS_JSON", "Optional credentials for balances or real orders."],
            ["PAPER_TRADING", "Keep true while developing and testing."],
            ["ENABLE_LIVE_TRADING", "Must be true before the live order path can run."],
            ["MAX_ORDER_USD", "Hard notional cap checked before order placement."],
          ].map(([name, body]) => (
            <div key={name} className="rounded-lg border border-line bg-slate-50 p-4">
              <code className="text-sm font-black text-teal-900">{name}</code>
              <p className="mt-2 text-sm leading-6 text-slate-600">{body}</p>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function StrategyLab({ system }: { system: LoadState }) {
  const readiness = useMemo(
    () => [
      {
        title: "Market data",
        ready: Boolean(system.health?.coinapi_configured),
        body: system.health?.coinapi_configured
          ? "CoinAPI is configured for OHLCV and spot rates."
          : "Add COINAPI_KEY before relying on CoinAPI analysis.",
      },
      {
        title: "Paper mode",
        ready: system.config?.paper_trading !== false,
        body:
          system.config?.paper_trading === false
            ? "Live mode is possible. Confirm order payloads carefully."
            : "Orders are simulated unless live flags are deliberately enabled.",
      },
      {
        title: "Risk limit",
        ready: Boolean(system.config?.max_order_usd),
        body: `Max order notional: $${system.config?.max_order_usd ?? "-"}`,
      },
    ],
    [system],
  );

  return (
    <div className="grid gap-5">
      <PageIntro
        icon={BarChart3}
        title="Strategy Lab"
        body="Use this page as the operating map for strategies, risk checks, and the API routes behind the dashboard."
      />

      <section className="grid gap-5 lg:grid-cols-3">
        <GuideCard
          icon={Route}
          title="Arbitrage"
          body="Compares bid and ask prices across configured CCXT exchanges, then subtracts the configured fee buffer before showing a spread."
        />
        <GuideCard
          icon={TrendingUp}
          title="Trend Following"
          body="Checks moving averages, MACD histogram, RSI, and close price alignment before returning buy, sell, or hold."
        />
        <GuideCard
          icon={Activity}
          title="Mean Reversion"
          body="Uses Bollinger Bands and RSI to find stretched markets that may revert toward the middle band."
        />
      </section>

      <section className="grid gap-5 lg:grid-cols-[0.85fr_1.15fr]">
        <Panel title="Execution Readiness" icon={ShieldCheck}>
          <div className="grid gap-3">
            {readiness.map((item) => (
              <ChecklistItem key={item.title} ready={item.ready} title={item.title} body={item.body} />
            ))}
          </div>
        </Panel>

        <Panel title="API Route Map" icon={Route}>
          <div className="grid gap-3">
            {[
              ["GET", "/health", "Server, CoinAPI, trading mode, and indicator backend."],
              ["GET", "/api/price", "CoinAPI exchange rate for a base and quote asset."],
              ["POST", "/api/strategies/signal", "Trend-following or mean-reversion decision."],
              ["GET", "/api/arbitrage/scan", "Cross-exchange arbitrage scan using CCXT tickers."],
              ["POST", "/api/orders", "Paper or live order placement with explicit safety gates."],
            ].map(([method, path, body]) => (
              <div key={path} className="grid gap-2 rounded-lg border border-line bg-slate-50 p-4 sm:grid-cols-[80px_1fr]">
                <span className="rounded-md bg-teal-950 px-2 py-1 text-center text-xs font-black text-white">
                  {method}
                </span>
                <div className="min-w-0">
                  <code className="break-all text-sm font-black text-slate-900">{path}</code>
                  <p className="mt-1 text-sm leading-6 text-slate-600">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </section>
    </div>
  );
}

function PageIntro({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof Home;
  title: string;
  body: string;
}) {
  return (
    <section className="rounded-lg border border-line bg-panel p-5 shadow-panel">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="grid h-12 w-12 shrink-0 place-items-center rounded-lg bg-teal-950 text-white">
          <Icon className="h-6 w-6" />
        </div>
        <div>
          <h2 className="text-2xl font-black tracking-normal">{title}</h2>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">{body}</p>
        </div>
      </div>
    </section>
  );
}

function Panel({
  title,
  icon: Icon,
  action,
  children,
}: {
  title: string;
  icon: typeof Home;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-lg border border-line bg-panel p-4 shadow-panel">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Icon className="h-5 w-5 shrink-0 text-teal-750" />
          <h2 className="truncate text-lg font-black tracking-normal">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function StatusPill({
  icon: Icon,
  tone,
  children,
}: {
  icon: typeof Home;
  tone: "success" | "warning" | "neutral";
  children: ReactNode;
}) {
  const classes = {
    success: "border-emerald-300/40 bg-emerald-400/10 text-emerald-100",
    warning: "border-amber-300/40 bg-amber-400/10 text-amber-100",
    neutral: "border-white/20 bg-white/10 text-white",
  }[tone];
  return (
    <span className={`inline-flex min-h-9 items-center gap-2 rounded-lg border px-3 py-1 text-sm font-extrabold ${classes}`}>
      <Icon className="h-4 w-4" />
      {children}
    </span>
  );
}

function TextField({
  label,
  value,
  onChange,
  className = "",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <label className={`grid min-w-0 gap-2 ${className}`}>
      <span className="text-xs font-black uppercase text-slate-500">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 w-full min-w-0 rounded-lg border border-line bg-white px-3 text-sm font-semibold outline-none transition focus:border-teal-750 focus:ring-4 focus:ring-teal-700/10"
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
  className = "",
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <label className={`grid min-w-0 gap-2 ${className}`}>
      <span className="text-xs font-black uppercase text-slate-500">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 w-full min-w-0 rounded-lg border border-line bg-white px-3 text-sm font-semibold outline-none transition focus:border-teal-750 focus:ring-4 focus:ring-teal-700/10"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function ActionButton({
  icon: Icon,
  label,
  loading,
  tone = "teal",
  onClick,
}: {
  icon: typeof Home;
  label: string;
  loading: boolean;
  tone?: "teal" | "slate" | "amber" | "light";
  onClick: () => void;
}) {
  const classes = {
    teal: "bg-teal-750 text-white hover:bg-teal-800",
    slate: "bg-slate-800 text-white hover:bg-slate-900",
    amber: "bg-amber-650 text-white hover:bg-amber-700",
    light: "border border-line bg-white text-slate-800 hover:bg-slate-50",
  }[tone];
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className={`inline-flex min-h-11 min-w-36 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-black transition disabled:cursor-wait disabled:opacity-60 ${classes}`}
    >
      <Icon className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
      {label}
    </button>
  );
}

function Metric({ label, value, caption }: { label: string; value: string; caption: string }) {
  return (
    <article className="rounded-lg border border-line bg-panel p-4 shadow-panel">
      <p className="text-xs font-black uppercase text-slate-500">{label}</p>
      <strong className="mt-3 block min-h-10 break-words text-3xl font-black tracking-normal">{value}</strong>
      <span className="mt-1 block text-sm text-slate-500">{caption}</span>
    </article>
  );
}

function SignalBadge({ action }: { action: TradeSignal["action"] }) {
  const classes = {
    buy: "bg-emerald-100 text-emerald-800",
    sell: "bg-red-100 text-red-800",
    hold: "bg-slate-100 text-slate-700",
    arbitrage: "bg-amber-100 text-amber-800",
  }[action];
  return <span className={`rounded-lg px-3 py-1 text-sm font-black uppercase ${classes}`}>{action}</span>;
}

function SignalStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-slate-50 p-3">
      <span className="text-xs font-black uppercase text-slate-500">{label}</span>
      <strong className="mt-1 block break-words text-sm font-black text-slate-900">{value}</strong>
    </div>
  );
}

function OpportunityRow({ item }: { item: ArbitrageOpportunity }) {
  return (
    <article className="rounded-lg border border-line bg-slate-50 p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <strong className="break-words text-base font-black">
          {item.buy_exchange} to {item.sell_exchange}
        </strong>
        <span className="rounded-lg bg-emerald-100 px-3 py-1 text-sm font-black text-emerald-800">
          {formatPercent(item.estimated_net_profit_pct)}
        </span>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        Buy {formatNumber(item.buy_price, 8)} and sell {formatNumber(item.sell_price, 8)}. Gross spread{" "}
        {formatPercent(item.gross_profit_pct)}.
      </p>
    </article>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-dashed border-line bg-slate-50 p-5">
      <strong className="block text-base font-black">{title}</strong>
      <p className="mt-2 text-sm leading-6 text-slate-600">{body}</p>
    </div>
  );
}

function ChecklistItem({ ready, title, body }: { ready: boolean; title: string; body: string }) {
  return (
    <div className="flex gap-3 rounded-lg border border-line bg-slate-50 p-4">
      {ready ? (
        <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-700" />
      ) : (
        <CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
      )}
      <div className="min-w-0">
        <strong className="block text-sm font-black">{title}</strong>
        <p className="mt-1 break-words text-sm leading-6 text-slate-600">{body}</p>
      </div>
    </div>
  );
}

function GuideCard({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof Home;
  title: string;
  body: string;
}) {
  return (
    <article className="rounded-lg border border-line bg-panel p-5 shadow-panel">
      <div className="mb-4 grid h-11 w-11 place-items-center rounded-lg bg-teal-950 text-white">
        <Icon className="h-5 w-5" />
      </div>
      <h3 className="text-lg font-black tracking-normal">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-600">{body}</p>
    </article>
  );
}

function Alert({
  tone,
  title,
  body,
}: {
  tone: "warning" | "danger";
  title: string;
  body: string;
}) {
  const classes =
    tone === "danger"
      ? "border-red-200 bg-red-50 text-red-900"
      : "border-amber-200 bg-amber-50 text-amber-900";
  return (
    <div className={`mt-4 rounded-lg border p-4 ${classes}`}>
      <strong className="block text-sm font-black">{title}</strong>
      <p className="mt-1 text-sm leading-6">{body}</p>
    </div>
  );
}

function CodeBlock({ payload }: { payload: unknown }) {
  return (
    <pre className="mt-4 max-h-80 overflow-auto rounded-lg border border-slate-800 bg-[#0d1c18] p-4 text-xs leading-6 text-emerald-100">
      {JSON.stringify(payload, null, 2)}
    </pre>
  );
}

function metadataString(metadata: Record<string, unknown> | undefined, key: string) {
  const value = metadata?.[key];
  return typeof value === "string" && value.trim() ? value : undefined;
}

function priceCaption(price: PriceResponse) {
  if (price.source === "ccxt") {
    return `${price.exchange ?? "exchange"} ${price.symbol ?? ""}`.trim();
  }
  return `${price.asset_id_base}/${price.asset_id_quote}`;
}
