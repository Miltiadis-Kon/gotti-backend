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
