-- ══════════════════════════════════════════════════════════════════
-- GOTTI ECOSYSTEM — UNIFIED DATABASE SCHEMA (MySQL 8.0)
-- Shared by: gotti-backend, stock-alchemist, gotti-visualize, gotti-frontend
-- ══════════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS gotti CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE gotti;

-- ── 1. Users & Authentication ────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(100) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NULL,
    first_name VARCHAR(100) NULL,
    last_name VARCHAR(100) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ── 2. ETF Vaults (Module 4: 3-Tier Architecture) ───────────────
CREATE TABLE IF NOT EXISTS vaults (
    id VARCHAR(36) PRIMARY KEY,
    risk_level INT UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    current_nav_per_unit DECIMAL(20, 6) NOT NULL DEFAULT 100.000000,
    total_units_outstanding DECIMAL(20, 8) NOT NULL DEFAULT 0.00000000,
    annual_fee DECIMAL(5, 4) NOT NULL DEFAULT 0.0150,
    last_synced_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ── 3. NAV History Snapshots ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS nav_snapshots (
    id VARCHAR(36) PRIMARY KEY,
    vault_id VARCHAR(36) NOT NULL,
    nav_per_unit DECIMAL(20, 6) NOT NULL,
    broker_equity DECIMAL(20, 2) NOT NULL,
    strategy_return_pct DECIMAL(10, 8) NULL,
    recorded_at TIMESTAMP NOT NULL,
    FOREIGN KEY (vault_id) REFERENCES vaults(id),
    INDEX idx_vault_recorded (vault_id, recorded_at)
);

-- ── 4. User Unit Holdings (Dual-Engine Layer 1) ─────────────────
CREATE TABLE IF NOT EXISTS user_holdings (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    vault_id VARCHAR(36) NOT NULL,
    units DECIMAL(20, 8) NOT NULL DEFAULT 0.00000000,
    cost_basis DECIMAL(20, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (vault_id) REFERENCES vaults(id),
    UNIQUE KEY uk_user_vault (user_id, vault_id)
);

-- ── 5. Unit Transactions Ledger ──────────────────────────────────
CREATE TABLE IF NOT EXISTS unit_transactions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    vault_id VARCHAR(36) NOT NULL,
    transaction_type ENUM('DEPOSIT', 'WITHDRAWAL', 'FEE_DEDUCTION') NOT NULL,
    units DECIMAL(20, 8) NOT NULL,
    nav_at_execution DECIMAL(20, 6) NOT NULL,
    cash_amount DECIMAL(20, 2) NOT NULL,
    status ENUM('PENDING', 'EXECUTED', 'FAILED') NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (vault_id) REFERENCES vaults(id)
);

-- ── 6. Client Sub-Accounts ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS client_sub_accounts (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    account_type VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    strategy VARCHAR(100) NOT NULL,
    allocated_balance DECIMAL(20, 2) NOT NULL DEFAULT 0.00,
    unallocated_balance DECIMAL(20, 2) NOT NULL DEFAULT 0.00,
    auto_invest BOOLEAN NOT NULL DEFAULT FALSE,
    is_tax_advantaged BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── 7. Client Risk Profiles ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS client_risk_profiles (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) UNIQUE NOT NULL,
    score INT NOT NULL,
    risk_level INT NOT NULL,
    level_name VARCHAR(100) NOT NULL,
    answers JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── 8. Client Transactions ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS client_transactions (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    sub_account_id VARCHAR(100) NOT NULL,
    sub_account_name VARCHAR(100) NOT NULL,
    strategy_name VARCHAR(100) NOT NULL,
    amount DECIMAL(20, 2) NOT NULL,
    type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'Fulfilled',
    method VARCHAR(100) NOT NULL,
    notes TEXT NULL,
    date VARCHAR(20) NOT NULL,
    timestamp BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_client_tx_user (user_id),
    INDEX idx_client_tx_sub (sub_account_id)
);

-- ── 9. Order Book & Execution History ────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_date VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Open',
    buy_price DECIMAL(10, 2) NULL,
    sell_price DECIMAL(10, 2) NULL,
    profit DECIMAL(10, 2) NULL,
    order_amount DECIMAL(10, 2) NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    order_type VARCHAR(20) NOT NULL DEFAULT 'Buy',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── 10. System Configuration & Runtime State ────────────────────
CREATE TABLE IF NOT EXISTS system_config (
    config_key VARCHAR(100) PRIMARY KEY,
    config_value TEXT NOT NULL,
    description VARCHAR(255) NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ── 11. Available Tradable Tickers ──────────────────────────────
CREATE TABLE IF NOT EXISTS available_tickers (
    ticker VARCHAR(20) PRIMARY KEY,
    name VARCHAR(255),
    exchange VARCHAR(50),
    sector VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    added_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    metadata JSON,
    INDEX idx_is_active (is_active),
    INDEX idx_exchange (exchange),
    INDEX idx_sector (sector)
);

-- ── 12. Corporate Calendar Events ───────────────────────────────
CREATE TABLE IF NOT EXISTS calendar (
    entry_key VARCHAR(32) PRIMARY KEY,
    date DATE NOT NULL,
    execution_date DATE,
    event_type VARCHAR(50) NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    data JSON NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    expiry_date DATE,
    metadata JSON,
    INDEX idx_date (date),
    INDEX idx_event_type (event_type),
    INDEX idx_ticker (ticker),
    INDEX idx_date_event (date, event_type),
    INDEX idx_ticker_event (ticker, event_type)
);

-- ── 13. Financial News & Live Scraped Articles ──────────────────
CREATE TABLE IF NOT EXISTS news (
    entry_key VARCHAR(32) PRIMARY KEY,
    date DATE NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    data JSON NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    expiry_date DATE,
    metadata JSON,
    INDEX idx_date (date),
    INDEX idx_ticker (ticker),
    INDEX idx_date_ticker (date, ticker)
);

-- ── 14. Deep Fundamental Analysis ───────────────────────────────
CREATE TABLE IF NOT EXISTS fundamental_analysis (
    entry_key VARCHAR(32) PRIMARY KEY,
    date DATE NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    data JSON NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    expiry_date DATE,
    metadata JSON,
    INDEX idx_date (date),
    INDEX idx_ticker (ticker),
    INDEX idx_date_ticker (date, ticker)
);

-- ── 15. Actionable Quantitative Signals ─────────────────────────
CREATE TABLE IF NOT EXISTS signals (
    signal_id VARCHAR(32) PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    signal_date DATE NOT NULL,
    signal_position VARCHAR(10) NOT NULL,
    calendar_event_keys JSON,
    news_keys JSON,
    fundamental_analysis_key VARCHAR(32),
    sentiment JSON,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    metadata JSON,
    INDEX idx_ticker (ticker),
    INDEX idx_signal_date (signal_date),
    INDEX idx_ticker_date (ticker, signal_date),
    INDEX idx_created_at (created_at)
);

-- ── 16. Historical Signals Archive ──────────────────────────────
CREATE TABLE IF NOT EXISTS historical_signals LIKE signals;

-- ── 17. Multi-Timeframe Candlesticks (LSEG Bridge) ──────────────
CREATE TABLE IF NOT EXISTS candles (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    ric VARCHAR(30) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    timestamp DATETIME NOT NULL,
    open DECIMAL(16, 4) NULL,
    high DECIMAL(16, 4) NULL,
    low DECIMAL(16, 4) NULL,
    close DECIMAL(16, 4) NULL,
    volume DECIMAL(20, 2) NULL,
    vwap DECIMAL(16, 4) NULL,
    source VARCHAR(20) DEFAULT 'lseg',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ticker_tf_ts (ticker, timeframe, timestamp),
    INDEX idx_ticker_tf (ticker, timeframe),
    INDEX idx_timestamp (timestamp)
);

-- ── 18. Candlestick Scheduled Collection Jobs ────────────────────
CREATE TABLE IF NOT EXISTS candle_collection_jobs (
    id VARCHAR(36) PRIMARY KEY,
    sector VARCHAR(100) NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    ric VARCHAR(30) NOT NULL,
    year_1_status VARCHAR(20) DEFAULT 'PENDING',
    year_1_candles INT DEFAULT 0,
    year_2_status VARCHAR(20) DEFAULT 'PENDING',
    year_2_tf VARCHAR(10) NULL,
    year_2_candles INT DEFAULT 0,
    year_3_status VARCHAR(20) DEFAULT 'PENDING',
    year_3_tf VARCHAR(10) NULL,
    year_3_candles INT DEFAULT 0,
    total_candles INT DEFAULT 0,
    overall_status VARCHAR(50) DEFAULT 'PENDING',
    error_message TEXT NULL,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_ticker (ticker),
    INDEX idx_sector (sector),
    INDEX idx_overall_status (overall_status)
);

-- ── 19. Candlestick Coverage Tracking (First & Last Day Window) ──
CREATE TABLE IF NOT EXISTS candle_coverage (
    ticker VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    first_date DATETIME NOT NULL,
    last_date DATETIME NOT NULL,
    candle_count INT NOT NULL DEFAULT 0,
    last_synced_at DATETIME NOT NULL,
    PRIMARY KEY (ticker, timeframe),
    INDEX idx_ticker (ticker),
    INDEX idx_last_date (last_date)
);

-- ══════════════════════════════════════════════════════════════════
-- SEED INITIAL ETF VAULTS (Module 4)
-- ══════════════════════════════════════════════════════════════════
INSERT INTO vaults (id, risk_level, name, symbol, current_nav_per_unit, total_units_outstanding, annual_fee)
VALUES 
  ('vault-lvl1-conservative', 1, 'Boomer Haven ETF', 'ETF-LVL1', 100.000000, 0.00000000, 0.0150),
  ('vault-lvl2-balanced',     2, 'Steady Grind ETF', 'ETF-LVL2', 100.000000, 0.00000000, 0.0150),
  ('vault-lvl3-aggressive',   3, 'Diamond Hands ETF', 'ETF-LVL3', 100.000000, 0.00000000, 0.0150)
ON DUPLICATE KEY UPDATE name=VALUES(name);
