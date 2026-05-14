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
