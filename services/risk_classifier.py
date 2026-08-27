from datetime import datetime, timezone
import numpy as np
import pandas as pd
import yfinance as yf

from db.repository import repo
from models.signal import (
    TickerRiskAssignment,
    Evaluation,
    CompositeRiskEvaluation,
    RiskBreakdown,
    DualHorizonMetrics,
    EarningsRiskData
)
from services.logging_service import logger
from services.earnings_risk_engine import earnings_risk_engine
from config.vault_registry import VAULT_REGISTRY


def calculate_drawdown_metrics(price_series: pd.Series) -> tuple[float, float]:
    """Computes Max Drawdown and Ulcer Index for a given price window."""
    if len(price_series) == 0:
        return 0.0, 0.0
    cum_returns = price_series / price_series.iloc[0]
    peak = cum_returns.cummax()
    drawdowns = (cum_returns - peak) / peak
    max_dd = float(abs(drawdowns.min())) if len(drawdowns) > 0 else 0.0
    ulcer = float(np.sqrt(np.mean((drawdowns * 100) ** 2))) if len(drawdowns) > 0 else 0.0
    return max_dd, ulcer


def get_eligible_trading_levels(base_level: int) -> tuple[list[int], list[str]]:
    """
    Hierarchical Upward Trading Permission Rule (3-Tier):
      - A ticker evaluated at Base Level L can be traded in strategy tiers L through 3.
      - Level 1 ticker -> eligible for Levels 1, 2, 3.
      - Level 2 ticker -> eligible for Levels 2, 3.
      - Level 3 ticker -> eligible ONLY for Level 3.
    """
    clamped_level = min(max(int(base_level), 1), 3)
    eligible_levels = list(range(clamped_level, 4))
    eligible_vaults = [VAULT_REGISTRY[lvl].name for lvl in eligible_levels if lvl in VAULT_REGISTRY]
    return eligible_levels, eligible_vaults



def is_trade_permitted(base_level: int, target_level: int) -> bool:
    """Check if a stock with base_level is permitted to be traded in target_level."""
    return target_level >= base_level


def evaluate_stock_risk_dual_horizon(
    stock_prices: pd.Series,
    benchmark_prices: pd.Series,
    dollar_volume_30d: float,
    market_cap: float
) -> dict:
    """
    Evaluates baseline stock risk using 63-day (Quarterly) and 252-day (Annual) dual horizons.
    Combines volatility, drawdown severity, market beta, tail risk, and size/liquidity metrics.
    """
    # Align returns
    r_stock_all = stock_prices.pct_change().dropna()
    r_bench_all = benchmark_prices.pct_change().dropna()

    combined = pd.concat([r_stock_all, r_bench_all], axis=1, join="inner").dropna()
    if len(combined) < 63:
        raise ValueError(f"Insufficient overlapping price observations: {len(combined)} (need at least 63)")

    # Annual window (252 days)
    combined_252 = combined.tail(252)
    r_stock_252 = combined_252.iloc[:, 0]
    r_bench_252 = combined_252.iloc[:, 1]

    # Quarterly window (63 days)
    combined_63 = combined_252.tail(63)
    r_stock_63 = combined_63.iloc[:, 0]
    p_stock_63 = stock_prices.loc[combined_63.index]
    p_stock_252 = stock_prices.loc[combined_252.index]

    # 1. Volatility & Acceleration
    vol_252 = float(r_stock_252.std() * np.sqrt(252)) if len(r_stock_252) > 1 else 0.20
    vol_63 = float(r_stock_63.std() * np.sqrt(252)) if len(r_stock_63) > 1 else vol_252

    blended_vol = (0.60 * vol_63) + (0.40 * vol_252)
    vol_shock_ratio = (vol_63 / vol_252) if vol_252 > 0 else 1.0

    downside_q = r_stock_63[r_stock_63 < 0]
    downside_vol_63 = float(downside_q.std() * np.sqrt(252)) if len(downside_q) > 1 else vol_63

    base_vol_score = min(max((blended_vol / 0.80) * 100, 0), 100)
    shock_penalty = max(0, (vol_shock_ratio - 1.0) * 25)
    vol_score = min(base_vol_score + shock_penalty, 100)

    # 2. Drawdowns & Ulcer Index
    mdd_252, ulcer_252 = calculate_drawdown_metrics(p_stock_252)
    mdd_63, ulcer_63 = calculate_drawdown_metrics(p_stock_63)

    blended_mdd = (0.50 * mdd_63) + (0.50 * mdd_252)
    blended_ulcer = (0.60 * ulcer_63) + (0.40 * ulcer_252)
    dd_score = min(max((blended_mdd / 0.65) * 60 + (blended_ulcer / 20.0) * 40, 0), 100)

    # 3. Systematic Beta
    cov_matrix = np.cov(r_stock_252, r_bench_252)
    beta = float(cov_matrix[0, 1] / cov_matrix[1, 1]) if cov_matrix.shape == (2, 2) and cov_matrix[1, 1] > 0 else 1.0
    beta_score = min(max((beta / 2.0) * 100, 0), 100)

    # 4. Tail Risk / CVaR 95%
    var_95_63 = float(np.percentile(r_stock_63, 5))
    tail_losses = r_stock_63[r_stock_63 <= var_95_63]
    cvar_95_63 = float(abs(tail_losses.mean())) if len(tail_losses) > 0 else abs(var_95_63)
    tail_score = min(max((cvar_95_63 / 0.08) * 100, 0), 100)

    # 5. Size & Liquidity (Market Cap calibration)
    if market_cap > 25e9:
        size_score = 10.0  # Mega/Large (>$25B)
    elif market_cap >= 3e9:
        size_score = 45.0  # Mid/Large ($3B - $25B)
    else:
        size_score = 85.0  # Small/Micro (<$3B)


    # Composite Risk Score Calculation
    base_crs = (
        0.25 * vol_score +
        0.25 * dd_score +
        0.20 * beta_score +
        0.15 * tail_score +
        0.15 * size_score
    )

    return {
        "base_crs": round(base_crs, 2),
        "scores": {
            "volatility": round(vol_score, 2),
            "drawdown": round(dd_score, 2),
            "beta": round(beta_score, 2),
            "tail_risk": round(tail_score, 2),
            "liquidity": round(size_score, 2),
        },
        "quarterly_vs_annual": {
            "quarterly_vol": f"{vol_63 * 100:.2f}%",
            "annual_vol": f"{vol_252 * 100:.2f}%",
            "vol_shock_ratio": round(vol_shock_ratio, 2),
            "quarterly_mdd": f"-{mdd_63 * 100:.2f}%",
            "annual_mdd": f"-{mdd_252 * 100:.2f}%",
            "quarterly_cvar_95": f"-{cvar_95_63 * 100:.2f}%",
            "downside_vol_63": f"{downside_vol_63 * 100:.2f}%",
            "beta": round(beta, 2),
            "market_cap": market_cap,
            "dollar_volume_30d": dollar_volume_30d,
        }
    }


class RiskClassifier:
    """
    Quantitative Risk Engine:
    Integrates Dual-Horizon CRS, Earnings Event Multipliers (M_earnings),
    Strategy Allocation Gating Rules, and Hierarchical Upward Trading Permissions.
    """

    def __init__(self, benchmark_ticker: str = "SPY"):
        self.benchmark_ticker = benchmark_ticker
        self._benchmark_cache: pd.Series | None = None
        self._cache_date: str | None = None

    def _get_benchmark_prices(self) -> pd.Series:
        """Fetch and cache 1.5 years of benchmark closing prices (SPY)."""
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._benchmark_cache is not None and self._cache_date == today_str and len(self._benchmark_cache) >= 252:
            return self._benchmark_cache

        try:
            bench = yf.Ticker(self.benchmark_ticker)
            hist = bench.history(period="2y", interval="1d")
            if len(hist) >= 63:
                self._benchmark_cache = hist["Close"]
                self._cache_date = today_str
                return self._benchmark_cache
        except Exception as e:
            logger.error(f"Failed to fetch benchmark {self.benchmark_ticker}: {e}")

        # Fallback synthetic benchmark if offline
        dates = pd.date_range(end=datetime.now(timezone.utc), periods=300, freq="B")
        synthetic_prices = pd.Series(
            500.0 * np.cumprod(1 + np.random.normal(0.0004, 0.01, size=len(dates))),
            index=dates
        )
        self._benchmark_cache = synthetic_prices
        return self._benchmark_cache

    def evaluate_ticker_quantitative(
        self,
        ticker: str,
        override_days_to_next: int | None = None,
        override_days_since_last: int | None = None
    ) -> CompositeRiskEvaluation:
        """
        Run full Dual-Horizon quantitative evaluation, apply Earnings Risk Multiplier,
        and determine strategy allocation gating constraints.
        """
        ticker = ticker.upper().strip()
        bench_prices = self._get_benchmark_prices()
        price_df = None

        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2y", interval="1d")
            if len(hist) < 63:
                raise ValueError(f"Insufficient history for {ticker}: {len(hist)} bars")

            stock_prices = hist["Close"]
            price_df = hist
            
            fast_info = getattr(stock, "fast_info", None)
            market_cap = 5e10
            dollar_vol_30d = 5e7

            if fast_info:
                market_cap = getattr(fast_info, "market_cap", None) or market_cap
                vol_avg = getattr(fast_info, "three_month_average_volume", None) or 1e6
                last_price = stock_prices.iloc[-1]
                dollar_vol_30d = float(vol_avg * last_price)
            elif hasattr(stock, "info") and isinstance(stock.info, dict):
                market_cap = stock.info.get("marketCap", market_cap)
                dollar_vol_30d = stock.info.get("averageDailyVolume10Day", 1e6) * stock_prices.iloc[-1]

        except Exception as e:
            logger.error(f"yfinance fetch error for {ticker}: {e}. Using fallback simulation.")
            dates = pd.date_range(end=datetime.now(timezone.utc), periods=300, freq="B")
            np.random.seed(abs(hash(ticker)) % (2**32))
            vol_factor = 0.01 + (abs(hash(ticker)) % 5) * 0.008
            stock_prices = pd.Series(
                100.0 * np.cumprod(1 + np.random.normal(0.0002, vol_factor, size=len(dates))),
                index=dates
            )
            market_cap = 1e10
            dollar_vol_30d = 2e7

        # 1. Baseline calculation
        eval_result = evaluate_stock_risk_dual_horizon(
            stock_prices=stock_prices,
            benchmark_prices=bench_prices,
            dollar_volume_30d=dollar_vol_30d,
            market_cap=market_cap
        )

        base_crs = eval_result["base_crs"]
        scores_data = eval_result["scores"]
        metrics_data = eval_result["quarterly_vs_annual"]

        # 2. Dynamic Earnings Event Multiplier (M_earnings)
        earnings_impact = earnings_risk_engine.apply_to_composite_score(
            base_crs=base_crs,
            ticker=ticker,
            price_history=price_df,
            override_days_to_next=override_days_to_next,
            override_days_since_last=override_days_since_last
        )

        adjusted_crs = earnings_impact["adjusted_crs"]
        assigned_level = earnings_impact["assigned_level"]
        assigned_etf = earnings_impact["assigned_etf"]
        eligible_levels = earnings_impact["eligible_levels"]
        eligible_vaults = earnings_impact["eligible_vaults"]
        earnings_data = earnings_impact["earnings_data"]

        # Persist assignment to DB
        try:
            repo.save_risk_assignment(
                ticker=ticker,
                risk_level=assigned_level,
                score=adjusted_crs,
                signal_position="BUY"
            )
        except Exception as db_err:
            logger.error(f"Failed to persist risk assignment to DB: {db_err}")

        # Console logging
        m_earn = earnings_data["earnings_multiplier"]
        win_status = earnings_data["active_window"]
        if m_earn > 1.0:
            logger.risk(
                f"{ticker} -> Base CRS: {base_crs:.1f} x {m_earn:.2f}x [EARNINGS: {win_status}] "
                f"-> Adjusted CRS: {adjusted_crs:.1f} -> Level {assigned_level} ({assigned_etf}) | "
                f"Eligible in Levels {eligible_levels}"
            )
        else:
            logger.risk(
                f"{ticker} -> Base CRS: {base_crs:.1f} -> Level {assigned_level} ({assigned_etf}) | "
                f"Eligible in Levels {eligible_levels}"
            )

        return CompositeRiskEvaluation(
            ticker=ticker,
            base_crs=base_crs,
            composite_risk_score=adjusted_crs,
            earnings_multiplier=m_earn,
            assigned_level=assigned_level,
            assigned_etf=assigned_etf,
            eligible_levels=eligible_levels,
            eligible_vaults=eligible_vaults,
            scores=RiskBreakdown(**scores_data),
            metrics=DualHorizonMetrics(**metrics_data),
            earnings_risk=EarningsRiskData(
                earnings_multiplier=m_earn,
                active_window=win_status,
                days_to_next_earnings=earnings_data["days_to_next_earnings"],
                days_since_last_earnings=earnings_data["days_since_last_earnings"],
                historical_gap_severity=earnings_data["historical_gap_severity"],
                is_in_event_window=earnings_data["is_in_event_window"],
                allocation_constraint_summary=earnings_data["allocation_constraint_summary"]
            ),
            allocation_gating=earnings_data["allocation_gating"],
            evaluated_at=datetime.now(timezone.utc).isoformat()
        )

    def is_eligible_for_level(self, ticker: str, target_level: int) -> tuple[bool, str]:
        """
        Check if a ticker is permitted to be traded in a specific ETF level.
        Enforces: Base Level L ticker can be traded in target_level >= L.
        """
        assignment = self.classify_ticker(ticker)
        if not assignment:
            return False, f"Ticker {ticker} has no classification record"

        base_level = assignment.assigned_risk_level
        permitted = is_trade_permitted(base_level, target_level)
        target_vault = VAULT_REGISTRY.get(target_level)
        target_name = target_vault.name if target_vault else f"Level {target_level}"
        base_vault = VAULT_REGISTRY.get(base_level)
        base_name = base_vault.name if base_vault else f"Level {base_level}"

        if permitted:
            msg = f"Authorized: {ticker} (Base Level {base_level} - {base_name}) can be traded in Level {target_level} ({target_name})"
        else:
            msg = (
                f"Prohibited: {ticker} has Base Level {base_level} ({base_name}) and cannot be traded in lower-tier "
                f"Level {target_level} ({target_name}). Permitted in Levels {list(range(base_level, 4))}."
            )
        return permitted, msg

    def classify_ticker(self, ticker: str) -> TickerRiskAssignment | None:
        """
        Classify a ticker into an ETF strategy level with eligible trading tiers.
        """
        ticker = ticker.upper().strip()
        try:
            evaluation = self.evaluate_ticker_quantitative(ticker)
            return TickerRiskAssignment(
                id=f"risk-{ticker}-{int(datetime.now(timezone.utc).timestamp())}",
                ticker=ticker,
                assigned_risk_level=evaluation.assigned_level,
                eligible_levels=evaluation.eligible_levels,
                eligible_vaults=evaluation.eligible_vaults,
                evaluation_score=evaluation.composite_risk_score,
                signal_position="BUY",
                assigned_at=datetime.now(timezone.utc),
                details=evaluation.model_dump()
            )
        except Exception as e:
            logger.error(f"Quantitative evaluation failed for {ticker}: {e}")

        # Fallback to DB stored evaluation from stock-alchemist (3-tier CRS calibration)
        db_eval = repo.get_evaluation(ticker)
        if db_eval:
            risk_score = db_eval.risk_score
            assigned_level = 1 if risk_score <= 35.0 else (2 if risk_score <= 68.0 else 3)
            eligible_levels, eligible_vaults = get_eligible_trading_levels(assigned_level)
            return TickerRiskAssignment(
                id=f"risk-{ticker}-db",
                ticker=ticker,
                assigned_risk_level=assigned_level,
                eligible_levels=eligible_levels,
                eligible_vaults=eligible_vaults,
                evaluation_score=risk_score,
                signal_position=db_eval.signal or "BUY",
                assigned_at=datetime.now(timezone.utc)
            )


        return None

    def classify_all_pending(self) -> list[TickerRiskAssignment]:
        """Classify all tickers that have recent signals from stock-alchemist."""
        signals = repo.get_latest_signals(limit=50)
        assignments = []
        seen_tickers: set[str] = set()

        for signal in signals:
            if signal.ticker in seen_tickers:
                continue
            seen_tickers.add(signal.ticker)
            assignment = self.classify_ticker(signal.ticker)
            if assignment:
                assignments.append(assignment)

        logger.info(f"Dual-Horizon CRS engine classified {len(assignments)} tickers")
        return assignments


# Singleton classifier instance
risk_classifier = RiskClassifier()
