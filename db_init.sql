USE gotti;

-- ── 1. ETF Vaults (Dual-Engine Layer 2) ────────────────────────
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

-- ── 2. NAVPU History Snapshots ─────────────────────────────────
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

-- ── 3. User Unit Ledger ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_holdings (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    vault_id VARCHAR(36) NOT NULL,
    units_balance DECIMAL(20, 8) NOT NULL DEFAULT 0.00000000,
    total_deposited DECIMAL(20, 2) NOT NULL DEFAULT 0.00,
    total_withdrawn DECIMAL(20, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_vault (user_id, vault_id),
    FOREIGN KEY (vault_id) REFERENCES vaults(id),
    INDEX idx_user (user_id)
);

-- ── 4. Ledger Transactions Log ─────────────────────────────────
CREATE TABLE IF NOT EXISTS transactions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    vault_id VARCHAR(36) NOT NULL,
    transaction_type ENUM('DEPOSIT', 'WITHDRAWAL') NOT NULL,
    fiat_amount DECIMAL(20, 2) NOT NULL,
    units DECIMAL(20, 8) NOT NULL,
    nav_at_time DECIMAL(20, 6) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vault_id) REFERENCES vaults(id),
    INDEX idx_user_tx (user_id, created_at)
);

-- ── 5. Ticker Risk Assignments ─────────────────────────────────
CREATE TABLE IF NOT EXISTS ticker_risk_assignments (
    id VARCHAR(36) PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    assigned_risk_level INT NOT NULL,
    evaluation_score DECIMAL(10, 4) NULL,
    signal_position VARCHAR(10) NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ticker (ticker),
    INDEX idx_risk_level (assigned_risk_level)
);

-- ── 6. Client Users (Frontend Client Registry) ──────────────────
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(100) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NULL,
    name VARCHAR(100) NULL,
    risk_level INT NOT NULL DEFAULT 3,
    risk_score INT NULL,
    strategy_name VARCHAR(100) NOT NULL DEFAULT 'Steady Grind ETF',
    is_logged_in BOOLEAN NOT NULL DEFAULT TRUE,
    active_sub_account_id VARCHAR(100) NULL,
    total_cash_balance DECIMAL(20, 2) NOT NULL DEFAULT 0.00,
    questionnaire_answers JSON NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_email (email)
);

-- ── 7. Client Sub-Accounts (Segregated Portfolios) ─────────────
CREATE TABLE IF NOT EXISTS sub_accounts (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    name VARCHAR(100) NOT NULL,
    risk_level INT NOT NULL,
    strategy_name VARCHAR(100) NOT NULL,
    allocated_capital DECIMAL(20, 2) NOT NULL DEFAULT 0.00,
    current_value DECIMAL(20, 2) NOT NULL DEFAULT 0.00,
    cash_balance DECIMAL(20, 2) NOT NULL DEFAULT 0.00,
    invested_amount DECIMAL(20, 2) NOT NULL DEFAULT 0.00,
    pnl DECIMAL(20, 2) NOT NULL DEFAULT 0.00,
    pnl_percentage DECIMAL(10, 4) NOT NULL DEFAULT 0.00,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    holdings_count INT NOT NULL DEFAULT 0,
    description TEXT NULL,
    created_at VARCHAR(50) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_user_sub_risk (user_id, risk_level),
    INDEX idx_sub_user (user_id)
);

-- ── 8. Client Financial Transactions ────────────────────────────
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

-- ── 9. Order History ────────────────────────────────────────────
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

-- ── 10. Centralized System Credentials & Config (Shared Across All 4 Projects) ──
CREATE TABLE IF NOT EXISTS system_config (
    config_key VARCHAR(100) PRIMARY KEY,
    config_value TEXT NOT NULL,
    description VARCHAR(255) NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
