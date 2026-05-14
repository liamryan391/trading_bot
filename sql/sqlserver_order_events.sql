CREATE TABLE dbo.order_events (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    created_at DATETIMEOFFSET(7) NOT NULL,
    status NVARCHAR(40) NOT NULL,
    exchange_id NVARCHAR(80) NOT NULL,
    symbol NVARCHAR(80) NOT NULL,
    side NVARCHAR(10) NOT NULL
        CONSTRAINT CK_order_events_side CHECK (side IN ('buy', 'sell')),
    amount DECIMAL(28, 12) NOT NULL,
    order_type NVARCHAR(40) NOT NULL,
    price DECIMAL(28, 12) NULL,
    reference_price DECIMAL(28, 12) NULL,
    paper_trading BIT NOT NULL,
    live_enabled BIT NOT NULL,
    confirm_live_trading BIT NOT NULL,
    result_json NVARCHAR(MAX) NOT NULL,
    CONSTRAINT CK_order_events_result_json CHECK (ISJSON(result_json) = 1)
);

CREATE INDEX IX_order_events_created_at
ON dbo.order_events (created_at DESC);

CREATE INDEX IX_order_events_symbol_status
ON dbo.order_events (symbol, status, created_at DESC);

CREATE TABLE dbo.strategy_runs (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    created_at DATETIMEOFFSET(7) NOT NULL,
    strategy NVARCHAR(80) NOT NULL,
    symbol NVARCHAR(80) NOT NULL,
    source NVARCHAR(80) NULL,
    action NVARCHAR(20) NOT NULL,
    confidence DECIMAL(10, 6) NOT NULL,
    reason NVARCHAR(1000) NOT NULL,
    input_json NVARCHAR(MAX) NOT NULL,
    signal_json NVARCHAR(MAX) NOT NULL,
    CONSTRAINT CK_strategy_runs_input_json CHECK (ISJSON(input_json) = 1),
    CONSTRAINT CK_strategy_runs_signal_json CHECK (ISJSON(signal_json) = 1)
);

CREATE INDEX IX_strategy_runs_created_at
ON dbo.strategy_runs (created_at DESC);

CREATE TABLE dbo.risk_checks (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    created_at DATETIMEOFFSET(7) NOT NULL,
    status NVARCHAR(40) NOT NULL,
    exchange_id NVARCHAR(80) NOT NULL,
    symbol NVARCHAR(80) NOT NULL,
    side NVARCHAR(10) NOT NULL
        CONSTRAINT CK_risk_checks_side CHECK (side IN ('buy', 'sell')),
    amount DECIMAL(28, 12) NOT NULL,
    reference_price DECIMAL(28, 12) NULL,
    notional DECIMAL(28, 12) NULL,
    max_order_usd DECIMAL(28, 12) NOT NULL,
    max_daily_loss_usd DECIMAL(28, 12) NOT NULL,
    reason NVARCHAR(1000) NOT NULL
);

CREATE INDEX IX_risk_checks_created_at
ON dbo.risk_checks (created_at DESC);

CREATE TABLE dbo.market_snapshots (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    created_at DATETIMEOFFSET(7) NOT NULL,
    exchange_id NVARCHAR(80) NOT NULL,
    symbol NVARCHAR(80) NOT NULL,
    bid DECIMAL(28, 12) NULL,
    ask DECIMAL(28, 12) NULL,
    last DECIMAL(28, 12) NULL,
    exchange_timestamp DATETIMEOFFSET(7) NULL
);

CREATE INDEX IX_market_snapshots_symbol_created_at
ON dbo.market_snapshots (symbol, created_at DESC);

CREATE TABLE dbo.positions_balances (
    exchange_id NVARCHAR(80) NOT NULL,
    asset NVARCHAR(40) NOT NULL,
    updated_at DATETIMEOFFSET(7) NOT NULL,
    total DECIMAL(28, 12) NULL,
    free DECIMAL(28, 12) NULL,
    used DECIMAL(28, 12) NULL,
    CONSTRAINT PK_positions_balances PRIMARY KEY (exchange_id, asset)
);
