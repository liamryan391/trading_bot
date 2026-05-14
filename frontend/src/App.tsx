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
  Info,
  KeyRound,
  LifeBuoy,
  Moon,
  Play,
  RefreshCw,
  Route,
  ShieldCheck,
  Sun,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import {
  getConfig,
  getEnvironmentStatus,
  getExchangeTickers,
  getHealth,
  getOrderHistory,
  getPrice,
  getStrategySignal,
  placeOrder,
  scanArbitrage,
} from "./lib/api";
import { formatNumber, formatPercent } from "./lib/format";
import type {
  ArbitrageOpportunity,
  ArbitrageScan,
  EnvironmentStatus,
  Health,
  OrderHistoryEntry,
  PriceResponse,
  PublicConfig,
  StrategyId,
  Ticker,
  TradeSignal,
} from "./types";

type Page = "dashboard" | "setup-help" | "auto-trader-guide" | "strategy-lab" | "execution-control";
type Theme = "light" | "dark";

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

type StrategyDefinition = {
  id: StrategyId;
  label: string;
  shortLabel: string;
  icon: LucideIcon;
  kind: "ohlcv" | "ticker";
  primaryAction: string;
  description: string;
  outputTitle: string;
  emptyTitle: string;
  emptyBody: string;
};

const navItems: Array<{ page: Page; label: string; icon: LucideIcon }> = [
  { page: "dashboard", label: "Dashboard", icon: Home },
  { page: "setup-help", label: "Setup Help", icon: LifeBuoy },
  { page: "strategy-lab", label: "Strategy Lab", icon: BarChart3 },
  { page: "execution-control", label: "Execution Control", icon: ShieldCheck },
];

const strategyDefinitions: StrategyDefinition[] = [
  {
    id: "trend_following",
    label: "Trend Following",
    shortLabel: "Trend",
    icon: TrendingUp,
    kind: "ohlcv",
    primaryAction: "Analyse trend",
    description:
      "Uses recent OHLCV candles, moving averages, MACD, and RSI to check whether the market is trending up or down.",
    outputTitle: "Trend Following Signal",
    emptyTitle: "Waiting for trend analysis",
    emptyBody: "Run the bot to calculate indicators and decide whether trend conditions are buy, sell, or hold.",
  },
  {
    id: "mean_reversion",
    label: "Mean Reversion",
    shortLabel: "Mean revert",
    icon: Activity,
    kind: "ohlcv",
    primaryAction: "Analyse reversion",
    description:
      "Uses Bollinger Bands and RSI to check whether price is stretched away from its recent range and may revert.",
    outputTitle: "Mean Reversion Signal",
    emptyTitle: "Waiting for reversion analysis",
    emptyBody: "Run the bot to compare price with Bollinger Bands and RSI.",
  },
  {
    id: "arbitrage",
    label: "Arbitrage",
    shortLabel: "Arbitrage",
    icon: Route,
    kind: "ticker",
    primaryAction: "Scan arbitrage",
    description:
      "Compares live bid and ask prices across the configured exchanges, then subtracts the fee buffer before showing opportunities.",
    outputTitle: "Arbitrage Opportunities",
    emptyTitle: "Ready to scan spreads",
    emptyBody: "Run the bot to compare the configured exchanges and find cross-exchange spreads.",
  },
  {
    id: "grid_trading",
    label: "GRID Trading Bot",
    shortLabel: "GRID",
    icon: Gauge,
    kind: "ohlcv",
    primaryAction: "Build grid",
    description:
      "Builds passive buy and sell levels around the current price using volatility so the bot can work inside a range.",
    outputTitle: "GRID Trading Plan",
    emptyTitle: "Waiting for grid plan",
    emptyBody: "Run the bot to calculate grid spacing and the nearest passive buy and sell levels.",
  },
  {
    id: "dca",
    label: "DCA (Dollar Cost Averaging)",
    shortLabel: "DCA",
    icon: RefreshCw,
    kind: "ohlcv",
    primaryAction: "Check DCA",
    description:
      "Checks whether the next scheduled accumulation buy is acceptable or should pause because the market is overheated.",
    outputTitle: "DCA Signal",
    emptyTitle: "Waiting for DCA check",
    emptyBody: "Run the bot to decide whether the next dollar cost averaging entry should proceed.",
  },
  {
    id: "market_making",
    label: "Market Making Bot",
    shortLabel: "Market making",
    icon: Bot,
    kind: "ohlcv",
    primaryAction: "Quote market",
    description:
      "Prepares passive bid and ask quotes around fair value while flagging that inventory and order-book depth still need checks.",
    outputTitle: "Market Making Quotes",
    emptyTitle: "Waiting for maker quotes",
    emptyBody: "Run the bot to calculate a fair value, passive bid, passive ask, and quoted spread.",
  },
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
  if (path === "/setup-help/auto-trader") return "auto-trader-guide";
  if (path === "/setup-help") return "setup-help";
  if (path === "/strategy-lab") return "strategy-lab";
  if (path === "/execution-control") return "execution-control";
  return "dashboard";
}

export default function App() {
  const [page, setPage] = useState<Page>(currentPage());
  const [system, setSystem] = useState<LoadState>({ loading: true });
  const [form, setForm] = useState<BotForm>(defaultForm);
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    void refreshSystem();
  }, []);

  useEffect(() => {
    const onPopState = () => setPage(currentPage());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    window.localStorage.setItem("trading-bot-theme", theme);
  }, [theme]);

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
    const path =
      nextPage === "dashboard"
        ? "/"
        : nextPage === "auto-trader-guide"
          ? "/setup-help/auto-trader"
          : `/${nextPage}`;
    window.history.pushState({}, "", path);
    setPage(nextPage);
  }

  return (
    <div className={`min-h-screen bg-canvas text-ink ${theme === "dark" ? "theme-dark" : ""}`}>
      <Header
        page={page}
        setPage={goTo}
        system={system}
        theme={theme}
        toggleTheme={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
      />
      <main className="mx-auto w-full max-w-7xl px-4 pb-12 pt-5 sm:px-6 lg:px-8">
        {page === "dashboard" && (
          <Dashboard
            form={form}
            setForm={setForm}
            system={system}
            refreshSystem={refreshSystem}
          />
        )}
        {page === "setup-help" && <SetupHelp system={system} setPage={goTo} />}
        {page === "auto-trader-guide" && <AutoTraderGuide setPage={goTo} />}
        {page === "strategy-lab" && <StrategyLab system={system} />}
        {page === "execution-control" && <ExecutionControl system={system} refreshSystem={refreshSystem} />}
      </main>
    </div>
  );
}

function Header({
  page,
  setPage,
  system,
  theme,
  toggleTheme,
}: {
  page: Page;
  setPage: (page: Page) => void;
  system: LoadState;
  theme: Theme;
  toggleTheme: () => void;
}) {
  const ready = system.health?.status === "ok";
  const ThemeIcon = theme === "dark" ? Sun : Moon;
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
            <button
              type="button"
              onClick={toggleTheme}
              className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-white/20 bg-white/10 px-3 py-1 text-sm font-extrabold text-white transition hover:bg-white/15 focus:bg-white/15"
            >
              <ThemeIcon className="h-4 w-4" />
              {theme === "dark" ? "Light mode" : "Dark mode"}
            </button>
          </div>
        </div>

        <nav className="flex flex-wrap gap-2" aria-label="Primary navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = page === item.page || (page === "auto-trader-guide" && item.page === "setup-help");
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
  const [busyAction, setBusyAction] = useState<"price" | "strategy" | undefined>();
  const [notice, setNotice] = useState<Notice | undefined>();

  const config = system.config;
  const strategy = strategyDefinition(form.strategy);
  const StrategyIcon = strategy.icon;
  const isArbitrage = strategy.kind === "ticker";
  const sourceLabel = isArbitrage ? "Exchange tickers" : form.dataSource === "coinapi" ? "CoinAPI OHLCV" : "Exchange OHLCV";

  useEffect(() => {
    setSignal(undefined);
    setArbitrage(undefined);
    setNotice(undefined);
  }, [form.strategy]);

  async function runAction(action: "price" | "strategy") {
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
      if (action === "strategy") {
        if (isArbitrage) {
          const result = await scanArbitrage(form.symbol, form.exchanges);
          setArbitrage(result);
          setSignal(result.signal);
          return;
        }

        const result = await getStrategySignal({
          strategy: form.strategy,
          source: form.dataSource,
          symbol: form.symbol,
          exchange_ids: form.exchanges,
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
      <section className="overflow-hidden rounded-lg border border-line bg-panel p-5 shadow-panel">
        <div className="mb-4 flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-xl font-black tracking-normal">Market Setup</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">
              Configure the market, data source, and bot logic used by the main strategy panel.
            </p>
          </div>
          <span className="inline-flex w-fit items-center gap-2 rounded-lg border border-line bg-slate-50 px-3 py-2 text-sm font-black text-slate-700">
            <StrategyIcon className="h-4 w-4 text-teal-750" />
            {strategy.label}
          </span>
        </div>

        <form
          className="grid gap-4 xl:grid-cols-12"
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            void runAction("strategy");
          }}
        >
          <TextField
            label="Base"
            help="Asset being priced, e.g. BTC."
            value={form.base}
            onChange={(value) => updateField("base", value)}
          />
          <TextField
            label="Quote"
            help="Pricing currency, e.g. USD or USDT."
            value={form.quote}
            onChange={(value) => updateField("quote", value)}
          />
          <TextField
            className="xl:col-span-2"
            label="Exchange symbol"
            help="CCXT pair format, e.g. BTC/USDT."
            value={form.symbol}
            onChange={(value) => updateField("symbol", value)}
          />
          <TextField
            className="xl:col-span-3"
            label="CoinAPI symbol"
            help="CoinAPI market id for candles."
            value={form.coinapiSymbol}
            onChange={(value) => updateField("coinapiSymbol", value)}
          />
          <TextField
            className="xl:col-span-2"
            label="Exchanges"
            help="Venues used by arbitrage scans."
            value={form.exchanges}
            onChange={(value) => updateField("exchanges", value)}
          />
          <SelectField
            className="xl:col-span-2"
            label="Strategy"
            help="Bot logic for the output panel."
            value={form.strategy}
            onChange={(value) => updateField("strategy", value as StrategyId)}
            options={strategyDefinitions.map((item) => ({ value: item.id, label: item.label }))}
          />
          <SelectField
            className="xl:col-span-2"
            label="Source"
            help="OHLCV provider for candle bots."
            value={form.dataSource}
            onChange={(value) => updateField("dataSource", value as BotForm["dataSource"])}
            options={[
              { value: "coinapi", label: "CoinAPI" },
              { value: "exchange", label: "Exchange OHLCV" },
            ]}
            disabled={isArbitrage}
          />
          <TextField
            className="xl:col-span-2"
            label="OHLCV exchange"
            help="Exchange for OHLCV or fallback."
            value={form.exchangeId}
            onChange={(value) => updateField("exchangeId", value)}
            disabled={isArbitrage}
          />

          <div className="border-t border-line pt-4 xl:col-span-12">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex gap-3 text-sm leading-6 text-slate-600">
                <Info className="mt-0.5 h-5 w-5 shrink-0 text-teal-750" />
                <p>
                  Trend Following is selected by default because it is the safest starter signal for OHLCV candles.
                  Arbitrage was previously separate because it uses live exchange tickers instead of candles; selecting
                  it now switches the output panel to arbitrage opportunities.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <ActionButton
                  icon={RefreshCw}
                  label="Refresh price"
                  loading={busyAction === "price"}
                  onClick={() => void runAction("price")}
                />
                <ActionButton
                  icon={isArbitrage ? Route : Play}
                  label={strategy.primaryAction}
                  loading={busyAction === "strategy"}
                  tone="slate"
                  onClick={() => void runAction("strategy")}
                />
                <ActionButton
                  icon={Activity}
                  label="Reload status"
                  loading={system.loading}
                  tone="light"
                  onClick={() => void refreshSystem()}
                />
              </div>
            </div>
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
        <Metric label="Selected Bot" value={strategy.shortLabel} caption={strategy.kind === "ticker" ? "Ticker scan" : "Candle signal"} />
        <Metric label="Market Data" value={sourceLabel} caption={isArbitrage ? form.exchanges : form.symbol} />
        <Metric
          label="Risk Mode"
          value={config?.paper_trading === false ? "Live" : "Paper"}
          caption={config ? `$${config.max_order_usd} max order` : "Risk limit"}
        />
      </section>

      <section className="grid gap-5 xl:grid-cols-[1.35fr_0.65fr]">
        <StrategyOutputPanel strategy={strategy} signal={signal} arbitrage={arbitrage} />
        <Panel title="Strategy Details" icon={strategy.icon}>
          <p className="text-sm leading-6 text-slate-600">{strategy.description}</p>
          <div className="mt-4 grid gap-3">
            <SignalStat label="Output type" value={strategy.kind === "ticker" ? "Exchange ticker scan" : "OHLCV signal"} />
            <SignalStat label="Run button" value={strategy.primaryAction} />
            <SignalStat label="Current source" value={sourceLabel} />
          </div>
        </Panel>
      </section>

      <AutomatedTradingPanel paperTrading={config?.paper_trading !== false} />

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
        <PayloadDetails payload={{ health: system.health, config: system.config }} />
      </Panel>
    </div>
  );
}

function AutomatedTradingPanel({ paperTrading }: { paperTrading: boolean }) {
  return (
    <Panel title="Automated Trading Safety" icon={ShieldCheck}>
      <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <p className="text-sm leading-6 text-slate-600">
            The app is currently safest as a signal and paper-trading control panel. For full automation,
            the execution loop should run on a schedule, call the selected strategy, pass every order through
            the risk manager, then submit only approved orders through `/api/orders`.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <SignalStat label="Current mode" value={paperTrading ? "Paper trading" : "Live-capable"} />
            <SignalStat label="Order gate" value="/api/orders" />
            <SignalStat label="Secret type" value="Exchange API keys" />
          </div>
        </div>
        <div className="grid gap-3">
          <ChecklistItem
            ready={paperTrading}
            title="Start in paper mode"
            body="Keep PAPER_TRADING=true until fills, fees, and strategy behavior are proven."
          />
          <ChecklistItem
            ready
            title="No wallet seed phrases"
            body="The bot should never store recovery phrases or private keys. Use exchange API keys only."
          />
          <ChecklistItem
            ready
            title="Disable withdrawals"
            body="Give bot keys view and trade permissions only; keep withdrawal permission off."
          />
        </div>
      </div>
    </Panel>
  );
}

function StrategyOutputPanel({
  strategy,
  signal,
  arbitrage,
}: {
  strategy: StrategyDefinition;
  signal?: TradeSignal;
  arbitrage?: ArbitrageScan;
}) {
  if (strategy.kind === "ticker") {
    return (
      <Panel
        title={strategy.outputTitle}
        icon={strategy.icon}
        action={
          <span className="rounded-lg border border-line bg-slate-50 px-3 py-1 text-sm font-black">
            {arbitrage?.opportunities.length ?? 0}
          </span>
        }
      >
        <p className="min-h-12 text-sm leading-6 text-slate-600">
          {signal?.reason ?? strategy.emptyBody}
        </p>
        {signal && <SignalSnapshot signal={signal} strategy={strategy} />}
        <div className="mt-4 grid gap-3">
          {(arbitrage?.opportunities.length ?? 0) > 0 ? (
            arbitrage?.opportunities.slice(0, 6).map((opportunity) => (
              <OpportunityRow key={`${opportunity.buy_exchange}-${opportunity.sell_exchange}`} item={opportunity} />
            ))
          ) : (
            <EmptyState
              title={arbitrage ? "No qualifying spread yet" : strategy.emptyTitle}
              body={
                arbitrage
                  ? "Configured exchanges were scanned, but no spread cleared the fee and profit buffer."
                  : strategy.emptyBody
              }
            />
          )}
        </div>
        {arbitrage && <PayloadDetails payload={arbitrage} />}
      </Panel>
    );
  }

  return (
    <Panel
      title={strategy.outputTitle}
      icon={strategy.icon}
      action={<SignalBadge action={signal?.action ?? "hold"} />}
    >
      <p className="min-h-12 text-sm leading-6 text-slate-600">
        {signal?.reason ?? strategy.emptyBody}
      </p>
      {signal ? (
        <>
          <SignalSnapshot signal={signal} strategy={strategy} />
          <PayloadDetails payload={signal} />
        </>
      ) : (
        <div className="mt-4">
          <EmptyState title={strategy.emptyTitle} body={strategy.emptyBody} />
        </div>
      )}
    </Panel>
  );
}

function SetupHelp({ system, setPage }: { system: LoadState; setPage: (page: Page) => void }) {
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

      <Panel
        title="Auto-Trader Guide"
        icon={Bot}
        action={
          <button
            type="button"
            onClick={() => setPage("auto-trader-guide")}
            className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-slate-800 px-3 py-2 text-sm font-black text-white transition hover:bg-slate-900"
          >
            <Route className="h-4 w-4" />
            Open guide
          </button>
        }
      >
        <p className="text-sm leading-6 text-slate-600">
          A full auto-trader needs a scheduled worker that gathers market data, runs one selected
          strategy, checks risk, submits approved orders, and records every result.
        </p>
      </Panel>

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
          body="Use the strategy selector to run trend, mean reversion, arbitrage, GRID, DCA, or market-making checks from one dashboard."
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
            ["KILL_SWITCH_ENABLED", "Emergency stop that blocks all order placement."],
            ["MAX_ORDER_USD", "Hard notional cap checked before order placement."],
            ["MIN_ORDER_USD", "Minimum notional size checked before order placement."],
            ["MAX_SLIPPAGE_PCT", "Maximum allowed gap between reference and limit price."],
            ["DATABASE_URL", "Optional SQL Server connection string for Alembic migrations."],
            ["ORDER_DATABASE_PATH", "Local SQL database file used for order event history."],
          ].map(([name, body]) => (
            <div key={name} className="rounded-lg border border-line bg-slate-50 p-4">
              <code className="text-sm font-black text-teal-900">{name}</code>
              <p className="mt-2 text-sm leading-6 text-slate-600">{body}</p>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Wallet and API Safety" icon={ShieldCheck}>
        <div className="grid gap-4 lg:grid-cols-3">
          <ChecklistItem
            ready
            title="Trading funds"
            body="Keep only a small trading balance on the exchange account connected to the bot."
          />
          <ChecklistItem
            ready
            title="Long-term funds"
            body="Move savings to cold storage or a self-custody wallet you control."
          />
          <ChecklistItem
            ready
            title="Bot access"
            body="Use exchange API keys with view/trade permissions, IP restrictions where possible, and no withdrawals."
          />
        </div>
      </Panel>
    </div>
  );
}

function AutoTraderGuide({ setPage }: { setPage: (page: Page) => void }) {
  return (
    <div className="grid gap-5">
      <PageIntro
        icon={Bot}
        title="Auto-Trader Guide"
        body="Use this as the build path for moving from manual analysis to a guarded scheduled worker. Keep each stage visible and auditable before enabling live orders."
      />

      <Panel
        title="Execution Flow"
        icon={Route}
        action={
          <button
            type="button"
            onClick={() => setPage("execution-control")}
            className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-slate-800 px-3 py-2 text-sm font-black text-white transition hover:bg-slate-900"
          >
            <ShieldCheck className="h-4 w-4" />
            Open controls
          </button>
        }
      >
        <div className="grid gap-3 lg:grid-cols-5">
          {[
            ["1", "Market data", "Fetch price, tickers, or OHLCV candles from CoinAPI or CCXT."],
            ["2", "Strategy", "Run the selected bot and store the last signal with its reason."],
            ["3", "Risk checks", "Check max order size, reference price, mode, and permissions."],
            ["4", "Order gate", "Submit approved orders through /api/orders only."],
            ["5", "History", "Record order status, paper/live mode, and exchange response."],
          ].map(([step, title, body]) => (
            <div key={step} className="rounded-lg border border-line bg-slate-50 p-4">
              <span className="grid h-8 w-8 place-items-center rounded-md bg-teal-750 text-sm font-black text-white">
                {step}
              </span>
              <h3 className="mt-3 text-base font-black">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">{body}</p>
            </div>
          ))}
        </div>
      </Panel>

      <section className="grid gap-5 lg:grid-cols-3">
        <GuideCard
          icon={Activity}
          title="Worker Schedule"
          body="Run the worker on an interval such as every 5, 15, or 60 minutes. Avoid overlapping runs and record every decision."
        />
        <GuideCard
          icon={ShieldCheck}
          title="Approval Gate"
          body="A signal is not an order. Require risk approval and keep PAPER_TRADING=true until the history looks correct."
        />
        <GuideCard
          icon={KeyRound}
          title="Secrets"
          body="Use exchange API keys with view/trade permissions. Never store wallet seeds, private keys, or withdrawal-enabled bot keys."
        />
      </section>

      <Panel title="Implementation Checklist" icon={CheckCircle2}>
        <div className="grid gap-3 md:grid-cols-2">
          <ChecklistItem
            ready
            title="Persist decisions"
            body="Use the SQL audit trail locally, then move long-term order events into SQL Server/T-SQL."
          />
          <ChecklistItem
            ready
            title="One active worker"
            body="Use a lock so only one scheduled run can place orders at a time."
          />
          <ChecklistItem
            ready
            title="Dry-run replay"
            body="Backtest or replay saved candles before enabling any live execution flags."
          />
          <ChecklistItem
            ready
            title="Kill switch"
            body="Add a single environment flag or UI control that blocks all order placement immediately."
          />
        </div>
      </Panel>
    </div>
  );
}

function ExecutionControl({
  system,
  refreshSystem,
}: {
  system: LoadState;
  refreshSystem: () => Promise<void>;
}) {
  const [form, setForm] = useState({
    strategy: "trend_following" as StrategyId,
    source: "exchange" as BotForm["dataSource"],
    symbol: "BTC/USDT",
    exchangeId: "binance",
    exchangeIds: "binance,kraken,kucoin",
    coinapiSymbol: "BINANCE_SPOT_BTC_USDT",
    amount: "0.0001",
    referencePrice: "50000",
    confirmLive: false,
  });
  const [lastSignal, setLastSignal] = useState<TradeSignal | undefined>();
  const [orderResult, setOrderResult] = useState<Record<string, unknown> | undefined>();
  const [history, setHistory] = useState<OrderHistoryEntry[]>([]);
  const [busyAction, setBusyAction] = useState<"signal" | "order" | "history" | "status" | undefined>();
  const [notice, setNotice] = useState<Notice | undefined>();

  useEffect(() => {
    setForm((previous) => ({
      ...previous,
      symbol: system.config?.default_symbol || previous.symbol,
      exchangeId: system.config?.exchange_ids[0] || previous.exchangeId,
      exchangeIds: system.config?.exchange_ids.length
        ? system.config.exchange_ids.join(",")
        : previous.exchangeIds,
      coinapiSymbol: system.config?.default_coinapi_symbol_id || previous.coinapiSymbol,
    }));
  }, [system.config]);

  useEffect(() => {
    void loadHistory();
  }, []);

  const amount = Number(form.amount);
  const referencePrice = Number(form.referencePrice);
  const maxOrder = Number(system.config?.max_order_usd ?? 0);
  const notional = amount * referencePrice;
  const proposedSide =
    lastSignal?.action === "buy" || lastSignal?.action === "sell" ? lastSignal.action : undefined;
  const proposedOrder = proposedSide
    ? {
        exchange_id: form.exchangeId,
        symbol: form.symbol,
        side: proposedSide,
        amount,
        order_type: "market",
        price: null,
        reference_price: referencePrice,
        confirm_live_trading: form.confirmLive,
      }
    : undefined;
  const riskChecks = [
    {
      ready: Boolean(lastSignal),
      title: "Signal available",
      body: lastSignal ? lastSignal.reason : "Generate a strategy signal first.",
    },
    {
      ready: Boolean(proposedSide),
      title: "Action is tradeable",
      body: proposedSide ? `Signal proposes a ${proposedSide} order.` : "Hold and arbitrage signals do not create a single market order.",
    },
    {
      ready: Number.isFinite(amount) && amount > 0,
      title: "Amount is positive",
      body: `Amount: ${form.amount || "-"}`,
    },
    {
      ready: Number.isFinite(referencePrice) && referencePrice > 0,
      title: "Reference price is positive",
      body: `Reference price: ${form.referencePrice || "-"}`,
    },
    {
      ready: maxOrder > 0 && Number.isFinite(notional) && notional > 0 && notional <= maxOrder,
      title: "Inside max order limit",
      body: maxOrder ? `$${notional.toFixed(2)} notional against $${maxOrder.toFixed(2)} max.` : "Risk config is not loaded yet.",
    },
  ];
  const riskApproved = riskChecks.every((item) => item.ready);

  async function runSignal() {
    setBusyAction("signal");
    setNotice(undefined);
    setOrderResult(undefined);
    try {
      const result = await getStrategySignal({
        strategy: form.strategy,
        source: form.source,
        symbol: form.symbol,
        exchange_ids: form.exchangeIds,
        exchange_id: form.exchangeId,
        coinapi_symbol_id: form.coinapiSymbol,
        period_id: "1HRS",
        timeframe: "1h",
        limit: 100,
      });
      setLastSignal(result);
    } catch (error) {
      setNotice({
        title: "Signal failed",
        body: error instanceof Error ? error.message : "Unable to generate a signal.",
        tone: "danger",
      });
    } finally {
      setBusyAction(undefined);
    }
  }

  async function submitOrder() {
    if (!proposedOrder || !riskApproved) {
      setNotice({
        title: "Order blocked",
        body: "The proposed order must pass every risk check before it can be submitted.",
        tone: "warning",
      });
      return;
    }

    setBusyAction("order");
    setNotice(undefined);
    try {
      const result = await placeOrder(proposedOrder);
      setOrderResult(result);
      await loadHistory();
    } catch (error) {
      setNotice({
        title: "Order rejected",
        body: error instanceof Error ? error.message : "The order request failed.",
        tone: "danger",
      });
      await loadHistory();
    } finally {
      setBusyAction(undefined);
    }
  }

  async function loadHistory() {
    setBusyAction((current) => current ?? "history");
    try {
      const result = await getOrderHistory();
      setHistory(result.orders);
    } catch (error) {
      setNotice({
        title: "History unavailable",
        body: error instanceof Error ? error.message : "Unable to load order history.",
        tone: "warning",
      });
    } finally {
      setBusyAction((current) => (current === "history" ? undefined : current));
    }
  }

  async function reloadStatus() {
    setBusyAction("status");
    try {
      await refreshSystem();
      await loadHistory();
    } finally {
      setBusyAction(undefined);
    }
  }

  function updateField(key: keyof typeof form, value: string | boolean) {
    setForm((previous) => ({ ...previous, [key]: value }));
  }

  return (
    <div className="grid gap-5">
      <PageIntro
        icon={ShieldCheck}
        title="Execution Control"
        body="Review paper/live mode, the latest signal, a proposed order, risk approval, and order history before any order can move toward live execution."
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Mode"
          value={system.config?.paper_trading === false ? "Live-capable" : "Paper"}
          caption={system.config?.enable_live_trading ? "Live flag enabled" : "Live flag off"}
        />
        <Metric
          label="Max Order"
          value={system.config ? `$${system.config.max_order_usd}` : "-"}
          caption="Risk manager hard cap"
        />
        <Metric
          label="Last Signal"
          value={lastSignal?.action.toUpperCase() ?? "-"}
          caption={lastSignal?.strategy ?? "No signal generated"}
        />
        <Metric
          label="Risk Approval"
          value={riskApproved ? "Approved" : "Blocked"}
          caption={riskApproved ? "Ready for order gate" : "Needs checks"}
        />
      </section>

      <section className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <Panel title="Execution Inputs" icon={Bot}>
          <div className="grid gap-4 md:grid-cols-2">
            <SelectField
              label="Strategy"
              help="Signal source for the proposed order."
              value={form.strategy}
              onChange={(value) => updateField("strategy", value as StrategyId)}
              options={strategyDefinitions.map((item) => ({ value: item.id, label: item.label }))}
            />
            <SelectField
              label="Source"
              help="OHLCV provider for candle strategies."
              value={form.source}
              onChange={(value) => updateField("source", value as BotForm["dataSource"])}
              options={[
                { value: "coinapi", label: "CoinAPI" },
                { value: "exchange", label: "Exchange OHLCV" },
              ]}
              disabled={form.strategy === "arbitrage"}
            />
            <TextField
              label="Symbol"
              help="CCXT trading pair."
              value={form.symbol}
              onChange={(value) => updateField("symbol", value)}
            />
            <TextField
              label="Exchange"
              help="Exchange used for OHLCV and orders."
              value={form.exchangeId}
              onChange={(value) => updateField("exchangeId", value)}
            />
            <TextField
              label="Amount"
              help="Base asset amount to trade."
              value={form.amount}
              onChange={(value) => updateField("amount", value)}
            />
            <TextField
              label="Reference price"
              help="Used for risk notional checks."
              value={form.referencePrice}
              onChange={(value) => updateField("referencePrice", value)}
            />
          </div>
          <label className="mt-4 flex gap-3 rounded-lg border border-line bg-slate-50 p-4 text-sm leading-6 text-slate-600">
            <input
              type="checkbox"
              checked={form.confirmLive}
              onChange={(event) => updateField("confirmLive", event.target.checked)}
              className="mt-1 h-4 w-4"
            />
            <span>
              Confirm live trading. This still only works if `PAPER_TRADING=false` and
              `ENABLE_LIVE_TRADING=true` are configured on the backend.
            </span>
          </label>
          <div className="mt-4 flex flex-wrap gap-2">
            <ActionButton
              icon={Play}
              label="Generate signal"
              loading={busyAction === "signal"}
              tone="slate"
              onClick={() => void runSignal()}
            />
            <ActionButton
              icon={ShieldCheck}
              label="Submit approved order"
              loading={busyAction === "order"}
              disabled={!riskApproved}
              onClick={() => void submitOrder()}
            />
            <ActionButton
              icon={RefreshCw}
              label="Reload status"
              loading={busyAction === "status"}
              tone="light"
              onClick={() => void reloadStatus()}
            />
          </div>
          {notice && <Alert tone={notice.tone} title={notice.title} body={notice.body} />}
        </Panel>

        <Panel title="Proposed Order" icon={Route} action={<SignalBadge action={lastSignal?.action ?? "hold"} />}>
          <p className="text-sm leading-6 text-slate-600">
            {lastSignal?.reason ?? "Generate a signal to build a proposed order."}
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <SignalStat label="Side" value={proposedSide ?? "-"} />
            <SignalStat label="Notional" value={Number.isFinite(notional) ? `$${notional.toFixed(2)}` : "-"} />
            <SignalStat label="Mode" value={system.config?.paper_trading === false ? "Live-capable" : "Paper"} />
          </div>
          <div className="mt-4 grid gap-3">
            {riskChecks.map((item) => (
              <ChecklistItem key={item.title} ready={item.ready} title={item.title} body={item.body} />
            ))}
          </div>
          {proposedOrder ? <PayloadDetails payload={proposedOrder} /> : null}
          {orderResult ? <PayloadDetails payload={orderResult} /> : null}
        </Panel>
      </section>

      <Panel
        title="Order History"
        icon={Activity}
        action={
          <ActionButton
            icon={RefreshCw}
            label="Refresh history"
            loading={busyAction === "history"}
            tone="light"
            onClick={() => void loadHistory()}
          />
        }
      >
        {history.length ? (
          <div className="grid gap-3">
            {history.map((item) => (
              <OrderHistoryRow key={item.id} item={item} />
            ))}
          </div>
        ) : (
          <EmptyState
            title="No order events yet"
            body="Submit a paper order from this page to see the execution audit trail."
          />
        )}
      </Panel>
    </div>
  );
}

function OrderHistoryRow({ item }: { item: OrderHistoryEntry }) {
  return (
    <article className="rounded-lg border border-line bg-slate-50 p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <strong className="text-base font-black">
          #{item.id} {item.side.toUpperCase()} {item.symbol}
        </strong>
        <span className="rounded-lg bg-slate-100 px-3 py-1 text-sm font-black uppercase text-slate-700">
          {item.status}
        </span>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        {item.exchange_id} / amount {item.amount} / reference{" "}
        {item.reference_price ? `$${item.reference_price}` : "-"} /{" "}
        {item.paper_trading ? "paper" : "live-capable"} / {new Date(item.created_at).toLocaleString()}
      </p>
    </article>
  );
}

function StrategyLab({ system }: { system: LoadState }) {
  const [marketForm, setMarketForm] = useState({
    symbol: "BTC/USDT",
    exchangeIds: "binance,kraken,kucoin",
  });
  const [tickers, setTickers] = useState<Ticker[]>([]);
  const [history, setHistory] = useState<OrderHistoryEntry[]>([]);
  const [environment, setEnvironment] = useState<EnvironmentStatus | undefined>();
  const [busyAction, setBusyAction] = useState<"market" | "history" | "environment" | undefined>();
  const [notice, setNotice] = useState<Notice | undefined>();
  const [marketUpdatedAt, setMarketUpdatedAt] = useState<string | undefined>();

  useEffect(() => {
    setMarketForm((previous) => ({
      ...previous,
      symbol: system.config?.default_symbol || previous.symbol,
      exchangeIds: system.config?.exchange_ids.length
        ? system.config.exchange_ids.join(",")
        : previous.exchangeIds,
    }));
  }, [system.config]);

  useEffect(() => {
    void loadLabState();
  }, []);

  const maxOrder = Number(system.config?.max_order_usd ?? 0);
  const maxDailyLoss = Number(system.config?.max_daily_loss_usd ?? 0);
  const recordedNotional = history.reduce(
    (sum, item) => sum + item.amount * Number(item.reference_price ?? item.price ?? 0),
    0,
  );
  const rejectedOrders = history.filter((item) => ["rejected", "failed"].includes(item.status)).length;
  const paperOrders = history.filter((item) => item.paper_trading).length;
  const bestBid = bestTicker(tickers, "bid", "max");
  const bestAsk = bestTicker(tickers, "ask", "min");
  const marketSpread =
    bestBid?.bid && bestAsk?.ask ? ((bestBid.bid - bestAsk.ask) / bestAsk.ask) * 100 : undefined;
  const readiness = useMemo(
    () => [
      {
        title: "Market data",
        ready: Boolean(system.health?.coinapi_configured || tickers.length),
        body: system.health?.coinapi_configured
          ? "CoinAPI is configured for OHLCV and spot rates."
          : tickers.length
            ? "Exchange market data is available through CCXT."
            : "Add COINAPI_KEY or refresh exchange tickers.",
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
        title: "SQL audit trail",
        ready: Boolean(system.config?.order_database_path),
        body: system.config?.order_database_path
          ? `Order events persist to ${system.config.order_database_path}.`
          : "Configure ORDER_DATABASE_PATH before relying on history.",
      },
    ],
    [history.length, system, tickers.length],
  );

  async function loadMarketOverview() {
    setBusyAction("market");
    setNotice(undefined);
    try {
      const result = await getExchangeTickers(marketForm.symbol, marketForm.exchangeIds);
      setTickers(result);
      setMarketUpdatedAt(new Date().toLocaleTimeString());
    } catch (error) {
      setNotice({
        title: "Market data unavailable",
        body: error instanceof Error ? error.message : "Unable to load exchange tickers.",
        tone: "warning",
      });
    } finally {
      setBusyAction(undefined);
    }
  }

  async function loadOrderHistory() {
    setBusyAction((current) => current ?? "history");
    try {
      const result = await getOrderHistory();
      setHistory(result.orders);
    } catch (error) {
      setNotice({
        title: "Order history unavailable",
        body: error instanceof Error ? error.message : "Unable to load order history.",
        tone: "warning",
      });
    } finally {
      setBusyAction((current) => (current === "history" ? undefined : current));
    }
  }

  async function loadEnvironmentStatus() {
    setBusyAction((current) => current ?? "environment");
    try {
      setEnvironment(await getEnvironmentStatus());
    } catch (error) {
      setNotice({
        title: "Environment status unavailable",
        body: error instanceof Error ? error.message : "Unable to load environment status.",
        tone: "warning",
      });
    } finally {
      setBusyAction((current) => (current === "environment" ? undefined : current));
    }
  }

  async function loadLabState() {
    await Promise.all([loadOrderHistory(), loadEnvironmentStatus()]);
  }

  return (
    <div className="grid gap-5">
      <PageIntro
        icon={BarChart3}
        title="Strategy Lab"
        body="Live market context, strategy fit, risk budget, and API visibility before a signal becomes an order."
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Metric label="Exchanges Online" value={`${tickers.length}`} caption={marketForm.exchangeIds} />
        <Metric
          label="Best Bid"
          value={bestBid?.bid ? formatNumber(bestBid.bid, 8) : "-"}
          caption={bestBid?.exchange ?? "Refresh market"}
        />
        <Metric
          label="Best Ask"
          value={bestAsk?.ask ? formatNumber(bestAsk.ask, 8) : "-"}
          caption={bestAsk?.exchange ?? "Refresh market"}
        />
        <Metric
          label="Spread"
          value={typeof marketSpread === "number" ? formatPercent(marketSpread) : "-"}
          caption={marketUpdatedAt ? `Updated ${marketUpdatedAt}` : "Cross-exchange view"}
        />
      </section>

      <EnvironmentPanel
        environment={environment}
        loading={busyAction === "environment"}
        onRefresh={() => void loadEnvironmentStatus()}
      />

      <section className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel
          title="Market Board"
          icon={Activity}
          action={
            <ActionButton
              icon={RefreshCw}
              label="Refresh market"
              loading={busyAction === "market"}
              tone="light"
              onClick={() => void loadMarketOverview()}
            />
          }
        >
          <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
            <div className="grid content-start gap-4">
              <TextField
                label="Symbol"
                help="CCXT trading pair."
                value={marketForm.symbol}
                onChange={(value) => setMarketForm((previous) => ({ ...previous, symbol: value }))}
              />
              <TextField
                label="Exchanges"
                help="Comma-separated CCXT exchange ids."
                value={marketForm.exchangeIds}
                onChange={(value) => setMarketForm((previous) => ({ ...previous, exchangeIds: value }))}
              />
              {notice && <Alert tone={notice.tone} title={notice.title} body={notice.body} />}
            </div>
            <MarketTickerTable tickers={tickers} />
          </div>
        </Panel>

        <Panel
          title="Risk Budget"
          icon={ShieldCheck}
          action={
            <ActionButton
              icon={RefreshCw}
              label="Reload history"
              loading={busyAction === "history"}
              tone="light"
              onClick={() => void loadOrderHistory()}
            />
          }
        >
          <RiskBudgetChart
            maxOrder={maxOrder}
            maxDailyLoss={maxDailyLoss}
            recordedNotional={recordedNotional}
          />
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <SignalStat label="Events" value={`${history.length}`} />
            <SignalStat label="Paper" value={`${paperOrders}`} />
            <SignalStat label="Rejected" value={`${rejectedOrders}`} />
          </div>
        </Panel>
      </section>

      <section className="grid gap-5 lg:grid-cols-3">
        {strategyDefinitions.map((item) => (
          <StrategyCapabilityCard key={item.id} strategy={item} />
        ))}
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
              ["GET", "/api/environment/status", "Paper, sandbox, live, SQL, and last decision status."],
              ["GET", "/api/config", "Public runtime configuration and SQL audit path."],
              ["GET", "/api/exchanges/tickers", "Current exchange bid, ask, last, and timestamps."],
              ["POST", "/api/strategies/signal", "Trend, mean reversion, GRID, DCA, market making, or arbitrage signal."],
              ["GET", "/api/arbitrage/scan", "Cross-exchange arbitrage opportunities using CCXT tickers."],
              ["POST", "/api/orders", "Paper or live order placement with explicit safety gates."],
              ["GET", "/api/orders/history", "SQL-backed order event history."],
              ["POST", "/api/backtests/run", "Historical OHLCV replay before sandbox or live orders."],
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

function EnvironmentPanel({
  environment,
  loading,
  onRefresh,
}: {
  environment?: EnvironmentStatus;
  loading: boolean;
  onRefresh: () => void;
}) {
  const mode = environment?.mode ?? "paper";
  const modeText = mode === "live" ? "Live" : mode === "sandbox" ? "Sandbox" : mode === "blocked" ? "Blocked" : "Paper";
  return (
    <Panel
      title="Test Mode and Environment"
      icon={ShieldCheck}
      action={
        <ActionButton
          icon={RefreshCw}
          label="Refresh environment"
          loading={loading}
          tone="light"
          onClick={onRefresh}
        />
      }
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <SignalStat label="Mode" value={modeText} />
        <SignalStat label="Exchange Connected" value={environment?.exchange_connected ? "Yes" : "No"} />
        <SignalStat label="Testnet Keys" value={environment?.testnet_keys_present ? "Present" : "Missing"} />
        <SignalStat label="SQL Database" value={environment?.sql_database.connected ? "Connected" : "Unavailable"} />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <ChecklistItem
          ready={environment?.paper_trading !== false || environment?.sandbox_mode === true}
          title="Paper or sandbox first"
          body={
            environment
              ? `Current execution path is ${modeText.toLowerCase()}.`
              : "Load environment status before testing orders."
          }
        />
        <ChecklistItem
          ready={environment?.kill_switch_enabled === false}
          title="Kill switch"
          body={environment?.kill_switch_enabled ? "Order placement is blocked." : "Order placement is not globally blocked."}
        />
        <ChecklistItem
          ready={environment?.live_enabled === false || environment?.paper_trading === false}
          title="Live flag"
          body={environment?.live_enabled ? "Live flag is enabled; use sandbox checks carefully." : "Live flag is off."}
        />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <SignalStat label="Last Strategy Run" value={statusSummary(environment?.last_strategy_run, "strategy")} />
        <SignalStat label="Last Risk Decision" value={statusSummary(environment?.last_risk_decision, "status")} />
        <SignalStat label="Last Order Result" value={environment?.last_order_result?.status ?? "-"} />
      </div>
    </Panel>
  );
}

function MarketTickerTable({ tickers }: { tickers: Ticker[] }) {
  if (!tickers.length) {
    return (
      <EmptyState
        title="No market snapshot yet"
        body="Refresh the market board to compare configured exchanges."
      />
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-line">
      <div className="grid grid-cols-[1fr_1fr_1fr_1fr] bg-slate-50 px-3 py-2 text-xs font-black uppercase text-slate-500">
        <span>Exchange</span>
        <span>Bid</span>
        <span>Ask</span>
        <span>Last</span>
      </div>
      <div className="divide-y divide-line">
        {tickers.map((ticker) => (
          <div
            key={`${ticker.exchange}-${ticker.symbol}`}
            className="grid grid-cols-[1fr_1fr_1fr_1fr] gap-2 px-3 py-3 text-sm"
          >
            <strong className="min-w-0 break-words font-black">{ticker.exchange}</strong>
            <span>{ticker.bid ? formatNumber(ticker.bid, 8) : "-"}</span>
            <span>{ticker.ask ? formatNumber(ticker.ask, 8) : "-"}</span>
            <span>{ticker.last ? formatNumber(ticker.last, 8) : "-"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function RiskBudgetChart({
  maxOrder,
  maxDailyLoss,
  recordedNotional,
}: {
  maxOrder: number;
  maxDailyLoss: number;
  recordedNotional: number;
}) {
  const rows = [
    {
      label: "Single order cap",
      value: maxOrder,
      max: Math.max(maxDailyLoss, maxOrder),
      caption: `$${maxOrder.toFixed(2)} max order`,
    },
    {
      label: "Daily loss guard",
      value: maxDailyLoss,
      max: Math.max(maxDailyLoss, maxOrder),
      caption: `$${maxDailyLoss.toFixed(2)} daily guard`,
    },
    {
      label: "Recorded notional",
      value: recordedNotional,
      max: Math.max(maxDailyLoss, recordedNotional, 1),
      caption: `$${recordedNotional.toFixed(2)} in recent events`,
    },
  ];

  return (
    <div className="grid gap-4">
      {rows.map((row) => (
        <div key={row.label}>
          <div className="mb-2 flex items-center justify-between gap-3 text-sm">
            <span className="font-black">{row.label}</span>
            <span className="text-slate-500">{row.caption}</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-teal-750"
              style={{ width: barWidth(row.value, row.max) }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function StrategyCapabilityCard({ strategy }: { strategy: StrategyDefinition }) {
  const Icon = strategy.icon;
  return (
    <article className="rounded-lg border border-line bg-panel p-5 shadow-panel">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="grid h-11 w-11 place-items-center rounded-lg bg-teal-950 text-white">
          <Icon className="h-5 w-5" />
        </div>
        <span className="rounded-lg bg-slate-50 px-3 py-1 text-xs font-black uppercase text-slate-600">
          {strategy.kind === "ticker" ? "Ticker" : "OHLCV"}
        </span>
      </div>
      <h3 className="text-lg font-black tracking-normal">{strategy.label}</h3>
      <p className="mt-2 min-h-16 text-sm leading-6 text-slate-600">{strategy.description}</p>
      <div className="mt-4 grid gap-3">
        <SignalStat label="Primary Action" value={strategy.primaryAction} />
        <SignalStat label="Output" value={strategy.outputTitle} />
      </div>
    </article>
  );
}

function PageIntro({
  icon: Icon,
  title,
  body,
}: {
  icon: LucideIcon;
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
  icon: LucideIcon;
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
  icon: LucideIcon;
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
  help,
  value,
  onChange,
  className = "",
  disabled = false,
}: {
  label: string;
  help: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
  disabled?: boolean;
}) {
  return (
    <label className={`grid min-w-0 gap-2 ${className}`}>
      <FieldLabel label={label} help={help} />
      <input
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 w-full min-w-0 rounded-lg border border-line bg-white px-3 text-sm font-semibold outline-none transition disabled:bg-slate-100 disabled:text-slate-500 focus:border-teal-750 focus:ring-4 focus:ring-teal-700/10"
      />
      <p className="text-xs leading-5 text-slate-500">{help}</p>
    </label>
  );
}

function SelectField({
  label,
  help,
  value,
  options,
  onChange,
  className = "",
  disabled = false,
}: {
  label: string;
  help: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
  className?: string;
  disabled?: boolean;
}) {
  return (
    <label className={`grid min-w-0 gap-2 ${className}`}>
      <FieldLabel label={label} help={help} />
      <select
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 w-full min-w-0 rounded-lg border border-line bg-white px-3 text-sm font-semibold outline-none transition disabled:bg-slate-100 disabled:text-slate-500 focus:border-teal-750 focus:ring-4 focus:ring-teal-700/10"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <p className="text-xs leading-5 text-slate-500">{help}</p>
    </label>
  );
}

function FieldLabel({ label, help }: { label: string; help: string }) {
  return (
    <span className="flex items-center gap-1.5 text-xs font-black uppercase text-slate-500">
      {label}
      <span title={help}>
        <Info className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
      </span>
      <span className="sr-only">{help}</span>
    </span>
  );
}

function ActionButton({
  icon: Icon,
  label,
  loading,
  disabled = false,
  tone = "teal",
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  loading: boolean;
  disabled?: boolean;
  tone?: "teal" | "slate" | "light";
  onClick: () => void;
}) {
  const classes = {
    teal: "bg-teal-750 text-white hover:bg-teal-800",
    slate: "bg-slate-800 text-white hover:bg-slate-900",
    light: "border border-line bg-white text-slate-800 hover:bg-slate-50",
  }[tone];
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading || disabled}
      className={`inline-flex min-h-11 min-w-36 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-black transition disabled:cursor-not-allowed disabled:opacity-60 ${classes}`}
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
      <strong className="mt-3 block min-h-10 break-words text-2xl font-black tracking-normal">{value}</strong>
      <span className="mt-1 block break-words text-sm text-slate-500">{caption}</span>
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

function SignalSnapshot({ signal, strategy }: { signal: TradeSignal; strategy: StrategyDefinition }) {
  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-3">
      <SignalStat label="Strategy" value={strategy.label} />
      <SignalStat label="Confidence" value={`${Math.round(signal.confidence * 100)}%`} />
      <SignalStat label="Symbol" value={signal.symbol} />
    </div>
  );
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
  icon: LucideIcon;
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

function PayloadDetails({ payload }: { payload: unknown }) {
  return (
    <details className="mt-4 rounded-lg border border-line bg-slate-50">
      <summary className="cursor-pointer px-4 py-3 text-sm font-black text-slate-700">
        API response
      </summary>
      <CodeBlock payload={payload} />
    </details>
  );
}

function CodeBlock({ payload }: { payload: unknown }) {
  return (
    <pre className="max-h-80 overflow-auto border-t border-slate-800 bg-[#0d1c18] p-4 text-xs leading-6 text-emerald-100">
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

function bestTicker(tickers: Ticker[], field: "bid" | "ask", mode: "min" | "max") {
  const values = tickers.filter((ticker) => typeof ticker[field] === "number");
  if (!values.length) return undefined;
  return values.reduce((best, ticker) => {
    const next = ticker[field] ?? 0;
    const current = best[field] ?? 0;
    return mode === "max" ? (next > current ? ticker : best) : next < current ? ticker : best;
  });
}

function barWidth(value: number, max: number) {
  if (!Number.isFinite(value) || !Number.isFinite(max) || max <= 0) return "0%";
  return `${Math.min(100, Math.max(0, (value / max) * 100)).toFixed(1)}%`;
}

function statusSummary(value: Record<string, unknown> | null | undefined, key: string) {
  const raw = value?.[key];
  return typeof raw === "string" && raw.trim() ? raw : "-";
}

function strategyDefinition(id: StrategyId) {
  return strategyDefinitions.find((item) => item.id === id) ?? strategyDefinitions[0];
}

function initialTheme(): Theme {
  const saved = window.localStorage.getItem("trading-bot-theme");
  if (saved === "dark" || saved === "light") {
    return saved;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
