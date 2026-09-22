# Gotti Backend (Module 4) — 3-Tier Automated ETF Architecture

The core fund accounting, quantitative risk engine, and communication backbone for the Gotti ecosystem.

---

## 3-Tier Strategy Profiles & Master ETFs

Adapting to a 3-tier master ETF architecture aligns the strategy lineup directly with Alpaca's 3-account paper trading constraint. Each ETF operates as an independent master pool backed by its own dedicated paper trading account ($1,000,000 seed each).

```
┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐
│  LEVEL 1: CONSERVATIVE  │   │    LEVEL 2: BALANCED    │   │   LEVEL 3: AGGRESSIVE   │
│    Boomer Haven ETF     │   │     Steady Grind ETF    │   │    Diamond Hands ETF    │
├─────────────────────────┤   ├─────────────────────────┤   ├─────────────────────────┤
│ • Mega-Cap Blue Chips   │   │ • Large/Mid Growth      │   │ • High-Beta & Small-Caps│
│ • Pure Buy & Hold       │   │ • Multi-Month Swings    │   │ • Tactical Momentum     │
│ • Target: 5% – 9%       │   │ • Target: 10% – 18%     │   │ • Target: 20%+          │
│ • Beta: < 0.75          │   │ • Beta: 0.85 – 1.25     │   │ • Beta: > 1.35          │
│ • CRS: 0.0 – 35.0       │   │ • CRS: 35.1 – 68.0      │   │ • CRS: 68.1 – 100.0     │
└─────────────────────────┘   └─────────────────────────┘   └─────────────────────────┘
```

| Dimension | Level 1: Boomer Haven ETF | Level 2: Steady Grind ETF | Level 3: Diamond Hands ETF |
| :--- | :--- | :--- | :--- |
| **Risk Profile** | Conservative / Capital Preservation | Moderate / Balanced Growth | Aggressive / Speculative Alpha |
| **Underlying Universe** | S&P 500 Dividend Aristocrats, Mega-Cap Value & Defensive Tech (KO, PG, JNJ, MSFT, AAPL) | Large & Mid-Cap Growth Leaders, Systematic Sector Momentum (QQQ, NVDA, META, AMD, ASML, TSM) | High-Beta Equities, Emerging Small/Micro-Caps, Dynamic Breakout Stocks (MSTR, NVDA, RIVN, MARA, SOUN) |
| **Turnover & Holding Period** | Multi-year holding, quarterly rebalance drift ($<20\%$ annual) | Multi-month trend holding with monthly momentum rebalancing ($50\%-100\%$ annual) | High-turnover tactical swing allocation and daily/weekly breakouts ($200\%+$ annual) |
| **Target 1-Year Return** | **5% – 9%** | **10% – 18%** | **20%+** |
| **Target Volatility ($\beta$)** | $\beta < 0.75$ | $\beta \approx 0.85 - 1.25$ | $\beta > 1.35$ |
| **Max Expected Drawdown** | $< -15\%$ | $-15\% \text{ to } -30\%$ | $-30\% \text{ to } -55\%+$ |
| **Pre-Earnings Gating ($T-3\text{d}$ to $T+1\text{d}$)** | **Hard Buy Freeze** if $M_{\text{earn}} > 1.15$ | Position cap at $5\%$ if $M_{\text{earn}} > 1.30$ | **No Gating** (Full alpha momentum) |

---

## 10-Question Risk Assessment & Scoring Engine

- **Scoring Mechanics**: $\mathbf{A = 1\text{ pt}} \quad\vert\quad \mathbf{B = 2\text{ pts}} \quad\vert\quad \mathbf{C = 3\text{ pts}} \quad\vert\quad \mathbf{D = 4\text{ pts}}$
- **Total Score Range**: **10 to 40 Points**
  - **10 – 19 Points**: **Level 1** $\rightarrow$ **Boomer Haven ETF**
  - **20 – 29 Points**: **Level 2** $\rightarrow$ **Steady Grind ETF**
  - **30 – 40 Points**: **Level 3** $\rightarrow$ **Diamond Hands ETF**

---

## Quantitative Single-Stock Risk Framework (CRS)

$$\text{CRS}_{\text{base}} = 0.25 S_{\text{vol}} + 0.25 S_{\text{dd}} + 0.20 S_{\beta} + 0.15 S_{\text{tail}} + 0.15 S_{\text{size}}$$

$$\text{CRS}_{\text{adjusted}} = \min\left(100.0, \; \text{CRS}_{\text{base}} \times M_{\text{earnings}}\right)$$

- **Level 1 (Boomer Haven ETF)**: $\text{CRS}_{\text{adj}} \in [0.0, 35.0]$
- **Level 2 (Steady Grind ETF)**: $\text{CRS}_{\text{adj}} \in [35.1, 68.0]$
- **Level 3 (Diamond Hands ETF)**: $\text{CRS}_{\text{adj}} \in [68.1, 100.0]$

### Hierarchical Upward Trading Permissions
- A stock classified at **Base Level $L$** can be traded in strategy tiers **$L$ through 3**.
- Level 1 ticker $\rightarrow$ eligible for Levels 1, 2, 3.
- Level 2 ticker $\rightarrow$ eligible for Levels 2, 3.
- Level 3 ticker $\rightarrow$ eligible ONLY for Level 3.

---

## Running the Application

```bash
# Start backend API (FastAPI)
fastapi dev main.py

# Run standalone valuation sync
python services/valuation_sync.py

# Seed ETF Vaults
python db/seed_vaults.py
```

---

## 📋 Ecosystem Interface Summary Table

| Interface | Service | Port | URL | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Ticker Risk & Earnings Evaluator** | `gotti-backend` | `10000` | [`http://localhost:10000/evaluate`](http://localhost:10000/evaluate) | 5-Pillar CRS score, dual-horizon vol/DD, Beta, CVaR 95%, earnings gating simulation & L1–L3 permissions. |
| **Strategy Hub & Backtester** | `gotti-visualize` | `8000` | [`http://localhost:8000/strategies`](http://localhost:8000/strategies) | Interactive Lumibot strategy execution, backtesting metrics, trade setup ledger & S/R inflections. |
| **Interactive Key Levels Chart** | `gotti-visualize` | `8000` | [`http://localhost:8000/chart`](http://localhost:8000/chart) | Dynamic Candlestick chart with Support/Resistance, Fibonacci retracements & trade markers. |
| **News Sentiment & Signals Dashboard** | `stock-alchemist` | `8080` | [`http://localhost:8080/`](http://localhost:8080/) | Live Market News Feed & FinBERT Sentiment Scores, Signal Generator & vitals. |
| **Client Trading App** | `gotti-frontend` | `3000` | [`http://localhost:3000`](http://localhost:3000) | Next.js 14 Dashboard, Segregated Sub-Accounts Hub, Onboarding Quiz & Ledger. |


---

## Detailed Endpoint Breakdown by Module

### A. Gotti Backend (`http://localhost:10000`)
- **Web UI & Docs**: Swagger at [`http://localhost:10000/docs`](http://localhost:10000/docs), ReDoc at [`http://localhost:10000/redoc`](http://localhost:10000/redoc)
- **Health & Root**: `GET /health`, `GET /`
- **ETF Vaults**: `GET /api/etf/vaults/`, `GET /api/etf/vaults/{id}/performance`
- **Holdings & Ledger**: `POST /api/etf/deposit`, `POST /api/etf/withdraw`, `GET /api/etf/holdings/`
- **Client Auth & Profile**: `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/user/profile`, `GET /api/user/financials`, `GET /api/user/snapshot`
- **Sub-Accounts & Transfers**: `GET /api/sub-accounts`, `POST /api/sub-accounts/{id}/fund`, `POST /api/sub-accounts/transfer`
- **Quantitative Signals & Risk**: `GET /api/signals/`, `GET /api/signals/{ticker}/evaluate`, `GET /api/signals/{ticker}/earnings`, `POST /api/signals/evaluate-batch`, `GET /api/signals/{ticker}/can-trade/{level}`
- **Stock Market Data**: `GET /api/stock_data/{ticker}`, `GET /api/orders/`
- **Admin**: `POST /api/admin/sync-nav`, `POST /api/admin/classify-signals`, `GET /api/admin/vault-status`, `GET /api/admin/config`, `GET /api/admin/git-status`, `POST /api/admin/git-sync`
- **WebSocket Server**: `ws://localhost:8001` (Trade Publisher to Gotti Visualize)

### B. Stock Alchemist (`http://localhost:8080`)
- **Custom Web Interfaces**:
  - **Home Dashboard & News Feed**: [`http://localhost:8080/`](http://localhost:8080/) or [`http://localhost:8080/news`](http://localhost:8080/news) (`src/templates/index.html`)
  - **Live Logs Console**: [`http://localhost:8080/logs`](http://localhost:8080/logs) (`src/templates/logs.html`)
  - **Interactive Docs**: Swagger UI at [`http://localhost:8080/docs`](http://localhost:8080/docs)
- **Health**: `GET /health`
- **Market News & Sentiment**: `GET /api/news` (Paginated list of headlines, FinBERT sentiment ratings & analysis)
- **Signals**: `GET /api/signals`, `POST /generate-signal`
- **WebSockets**:
  - `ws://localhost:8080/ws/signals` (Real-time signal stream for Gotti Backend & trading bots)
  - `ws://localhost:8080/ws/news` (Real-time live news headlines & sentiment)
- **Analysis & Testing**: `POST /saturday-analysis`, `POST /test-db`, `POST /test-gemini`
- **Dashboard & Logs API**: `GET /`, `GET /logs`, `GET /api/logs`

### C. Gotti Visualize (`http://localhost:8000`)
- **Custom Web Interface**:
  - **Stock Chart & Key Levels UI**: [`http://localhost:8000/chart`](http://localhost:8000/chart) (or `http://localhost:8000/plots/stock_chart.html`)
  - **Interactive Docs**: Swagger UI at [`http://localhost:8000/docs`](http://localhost:8000/docs)
- **Health**: `GET /health`
- **Charts API**: `GET /chart/{ticker}`, `GET /plots/stock_chart.html`
- **Strategies API**: `GET /strategies`, `POST /strategy/run`, `GET /db-data`


