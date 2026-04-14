-- ============================================================
-- Quant System Database Init
-- PostgreSQL 16 + TimescaleDB
-- ============================================================

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ======================== Relational Tables ========================

CREATE TABLE users (
    id            BIGSERIAL PRIMARY KEY,
    username      VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email         VARCHAR(100),
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_users_username ON users(username);

CREATE TABLE fund_config (
    id         SERIAL PRIMARY KEY,
    code       VARCHAR(10) UNIQUE NOT NULL,
    name       VARCHAR(100) NOT NULL,
    exchange   VARCHAR(2) NOT NULL,
    index_sina VARCHAR(30) NOT NULL,
    index_name VARCHAR(50) NOT NULL,
    is_active  BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_fund_config_active ON fund_config(is_active) WHERE is_active = true;

CREATE TABLE alert_rules (
    id                SERIAL PRIMARY KEY,
    user_id           BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    metric            VARCHAR(50) NOT NULL,
    operator          VARCHAR(5) NOT NULL,
    threshold         DECIMAL(12,4) NOT NULL,
    channel           VARCHAR(20) DEFAULT 'websocket',
    description       VARCHAR(200),
    is_active         BOOLEAN DEFAULT true,
    last_triggered_at TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_alert_rules_user   ON alert_rules(user_id)  WHERE is_active = true;
CREATE INDEX idx_alert_rules_metric ON alert_rules(metric)   WHERE is_active = true;

-- ======================== TimescaleDB Hypertables ========================

CREATE TABLE market_quotes (
    id           BIGSERIAL,
    time         TIMESTAMPTZ NOT NULL,
    source       VARCHAR(20) NOT NULL,
    symbol       VARCHAR(20) NOT NULL,
    open         DECIMAL(12,4),
    high         DECIMAL(12,4),
    low          DECIMAL(12,4),
    close        DECIMAL(12,4),
    volume       BIGINT,
    amount       DECIMAL(18,2),
    change_pct   DECIMAL(8,4),
    data_quality VARCHAR(10) DEFAULT 'live'
);
SELECT create_hypertable('market_quotes', by_range('time'));
CREATE INDEX idx_mq_symbol_time ON market_quotes(symbol, time DESC);
CREATE INDEX idx_mq_source      ON market_quotes(source, time DESC);
SELECT add_retention_policy('market_quotes', INTERVAL '2 years');

CREATE TABLE crush_margin_history (
    id                BIGSERIAL,
    time              TIMESTAMPTZ NOT NULL,
    meal_price        DECIMAL(10,2),
    oil_price         DECIMAL(10,2),
    cbot_cents        DECIMAL(10,2),
    usdcny            DECIMAL(8,4),
    freight_usd       DECIMAL(8,2),
    landed_cost_cny   DECIMAL(10,2),
    total_revenue_cny DECIMAL(10,2),
    crush_margin_cny  DECIMAL(10,2),
    signal            VARCHAR(20)
);
SELECT create_hypertable('crush_margin_history', by_range('time'));
CREATE INDEX idx_crush_time ON crush_margin_history(time DESC);
SELECT add_retention_policy('crush_margin_history', INTERVAL '5 years');

CREATE TABLE signal_history (
    id                 BIGSERIAL,
    time               TIMESTAMPTZ NOT NULL,
    signal_type        VARCHAR(30) NOT NULL,
    direction          VARCHAR(10) NOT NULL,
    confidence         DECIMAL(4,3),
    composite_score    INTEGER,
    factors            JSONB,
    reasoning_chain    JSONB,
    escalated          BOOLEAN DEFAULT false,
    escalate_reason    VARCHAR(200),
    market_snapshot_id UUID
);
SELECT create_hypertable('signal_history', by_range('time'));
CREATE INDEX idx_signal_type_time ON signal_history(signal_type, time DESC);
CREATE INDEX idx_signal_escalated ON signal_history(escalated, time DESC) WHERE escalated = true;

CREATE TABLE lof_premium_history (
    id               BIGSERIAL,
    time             TIMESTAMPTZ NOT NULL,
    fund_code        VARCHAR(10) NOT NULL,
    fund_name        VARCHAR(100),
    market_price     DECIMAL(10,4),
    estimated_nav    DECIMAL(10,4),
    official_nav     DECIMAL(10,4),
    premium_pct      DECIMAL(8,4),
    index_change_pct DECIMAL(8,4),
    nav_source       VARCHAR(20)
);
SELECT create_hypertable('lof_premium_history', by_range('time'));
CREATE INDEX idx_lof_fund_time ON lof_premium_history(fund_code, time DESC);
SELECT add_retention_policy('lof_premium_history', INTERVAL '3 years');

-- ======================== Continuous Aggregates ========================

CREATE MATERIALIZED VIEW market_quotes_30m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('30 minutes', time) AS bucket,
    symbol,
    first(open, time)  AS open,
    max(high)          AS high,
    min(low)           AS low,
    last(close, time)  AS close,
    sum(volume)        AS volume,
    sum(amount)        AS amount,
    count(*)           AS tick_count
FROM market_quotes
GROUP BY bucket, symbol;

SELECT add_continuous_aggregate_policy('market_quotes_30m',
    start_offset    => INTERVAL '2 hours',
    end_offset      => INTERVAL '30 minutes',
    schedule_interval => INTERVAL '30 minutes');

CREATE MATERIALIZED VIEW market_quotes_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    symbol,
    first(open, time)  AS open,
    max(high)          AS high,
    min(low)           AS low,
    last(close, time)  AS close,
    sum(volume)        AS volume,
    sum(amount)        AS amount,
    count(*)           AS tick_count
FROM market_quotes
GROUP BY bucket, symbol;

SELECT add_continuous_aggregate_policy('market_quotes_daily',
    start_offset    => INTERVAL '3 days',
    end_offset      => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');

CREATE MATERIALIZED VIEW crush_margin_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    avg(crush_margin_cny) AS avg_margin,
    min(crush_margin_cny) AS min_margin,
    max(crush_margin_cny) AS max_margin,
    last(signal, time)    AS last_signal
FROM crush_margin_history
GROUP BY bucket;

SELECT add_continuous_aggregate_policy('crush_margin_daily',
    start_offset    => INTERVAL '3 days',
    end_offset      => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');

-- ======================== JSONB Document Tables ========================

CREATE TABLE workflow_state (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_type VARCHAR(30) NOT NULL,
    current_phase VARCHAR(30) NOT NULL,
    state_data    JSONB NOT NULL,
    error_message TEXT,
    retry_count   INTEGER DEFAULT 0,
    is_terminal   BOOLEAN DEFAULT false,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_wf_type_terminal ON workflow_state(workflow_type, is_terminal) WHERE is_terminal = false;
CREATE INDEX idx_wf_updated       ON workflow_state(updated_at DESC);

CREATE TABLE usda_psd (
    id           SERIAL PRIMARY KEY,
    report_month DATE NOT NULL,
    region       VARCHAR(10) NOT NULL,
    commodity    VARCHAR(20) DEFAULT 'soybeans',
    data         JSONB NOT NULL,
    fetched_at   TIMESTAMPTZ DEFAULT now(),
    UNIQUE(report_month, region, commodity)
);
CREATE INDEX idx_usda_region_month ON usda_psd(region, report_month DESC);

CREATE TABLE market_snapshot (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    time         TIMESTAMPTZ NOT NULL,
    context      JSONB NOT NULL,
    data_quality VARCHAR(10),
    created_at   TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_snapshot_time ON market_snapshot(time DESC);
