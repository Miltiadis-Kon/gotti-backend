from datetime import datetime, date, timezone
from typing import Any
import numpy as np
import pandas as pd
import yfinance as yf
from services.logging_service import logger


class EarningsRiskEngine:
    """
    Earnings Event Risk Engine:
    Detects overnight gap risk and implied volatility expansion around earnings announcements.
    Calculates dynamic Earnings Multiplier (M_earnings) and strategy allocation gating rules.
    """

    def __init__(self, lookback_earnings_events: int = 4):
        self.lookback_events = lookback_earnings_events

    def get_earnings_proximity(self, ticker_symbol: str) -> dict[str, int | None]:
        """
        Detects upcoming and most recent earnings announcement dates.
        Returns:
          - days_to_next: Positive int (e.g. 2 means earnings in 2 days, 0 is event day)
          - days_since_last: Positive int (e.g. 1 means earnings was yesterday)
        """
        ticker_symbol = ticker_symbol.upper().strip()
        today = date.today()
        days_to_next: int | None = None
        days_since_last: int | None = None

        try:
            ticker = yf.Ticker(ticker_symbol)
            calendar = getattr(ticker, "calendar", None)
            
            # Check yfinance earnings_dates first
            earnings_dates_df = None
            try:
                earnings_dates_df = ticker.get_earnings_dates(limit=12)
            except Exception:
                pass

            if earnings_dates_df is not None and not earnings_dates_df.empty:
                event_dates = []
                for d in earnings_dates_df.index:
                    if isinstance(d, (datetime, pd.Timestamp)):
                        event_dates.append(d.date())
                    elif isinstance(d, date):
                        event_dates.append(d)

                future_dates = [d for d in event_dates if d >= today]
                past_dates = [d for d in event_dates if d < today]

                if future_dates:
                    days_to_next = (min(future_dates) - today).days

                if past_dates:
                    days_since_last = (today - max(past_dates)).days

            elif isinstance(calendar, dict) and "Earnings Date" in calendar:
                e_dates = calendar["Earnings Date"]
                if isinstance(e_dates, list) and e_dates:
                    first_ed = e_dates[0]
                    if isinstance(first_ed, (datetime, pd.Timestamp)):
                        ed_date = first_ed.date()
                        if ed_date >= today:
                            days_to_next = (ed_date - today).days
                        else:
                            days_since_last = (today - ed_date).days

        except Exception as e:
            logger.info(f"Earnings calendar lookup info for {ticker_symbol}: {e}")

        return {
            "days_to_next": days_to_next,
            "days_since_last": days_since_last
        }

    def compute_historical_earnings_gap(
        self,
        price_history: pd.DataFrame | None = None,
        earnings_dates: list[date] | None = None
    ) -> float:
        """
        Calculates the mean absolute overnight price gap on historical earnings days:
        Formula: Mean(|Open_t - Close_{t-1}| / Close_{t-1})
        Defaults to 5.5% (0.055) baseline if historical timestamps not supplied.
        """
        if price_history is None or price_history.empty or not earnings_dates:
            return 0.06

        gaps = []
        for ed in earnings_dates[-self.lookback_events:]:
            ed_ts = pd.Timestamp(ed)
            if ed_ts in price_history.index:
                idx = price_history.index.get_loc(ed_ts)
                if idx > 0:
                    prev_close = price_history['Close'].iloc[idx - 1]
                    event_open = price_history['Open'].iloc[idx]
                    if prev_close > 0:
                        gap = abs(event_open - prev_close) / prev_close
                        gaps.append(gap)

        return float(np.mean(gaps)) if gaps else 0.06

    def calculate_earnings_multiplier(
        self,
        ticker: str,
        price_history: pd.DataFrame | None = None,
        override_days_to_next: int | None = None,
        override_days_since_last: int | None = None
    ) -> dict[str, Any]:
        """
        Computes the dynamic risk multiplier M_earnings based on proximity and historical gap severity.
        Formula: M_earnings = M_base * sqrt(mean_gap / 0.05)
        """
        if override_days_to_next is not None or override_days_since_last is not None:
            days_to_next = override_days_to_next
            days_since_last = override_days_since_last
        else:
            proximity = self.get_earnings_proximity(ticker)
            days_to_next = proximity["days_to_next"]
            days_since_last = proximity["days_since_last"]

        hist_gap = self.compute_historical_earnings_gap(price_history)
        gap_severity_factor = max(1.0, float(np.sqrt(hist_gap / 0.05)))

        multiplier_base = 1.0
        active_window = "NONE"
        is_in_event_window = False

        # Check upcoming window (Priority 1)
        if days_to_next is not None:
            if days_to_next == 0:
                multiplier_base = 1.50
                active_window = "EVENT_DAY (T=0)"
                is_in_event_window = True
            elif 1 <= days_to_next <= 3:
                multiplier_base = 1.40
                active_window = f"IMMINENT_PRE_EARNINGS (T-{days_to_next}d)"
                is_in_event_window = True
            elif 4 <= days_to_next <= 7:
                multiplier_base = 1.25
                active_window = f"PRE_EARNINGS (T-{days_to_next}d)"
            elif 8 <= days_to_next <= 14:
                multiplier_base = 1.10
                active_window = f"APPROACHING (T-{days_to_next}d)"

        # Check recent window (Priority 2, only if not in imminent pre-earnings)
        if active_window == "NONE" and days_since_last is not None:
            if 1 <= days_since_last <= 2:
                multiplier_base = 1.25
                active_window = f"POST_EARNINGS_REACTION (T+{days_since_last}d)"
                if days_since_last <= 1:
                    is_in_event_window = True
            elif 3 <= days_since_last <= 5:
                multiplier_base = 1.10
                active_window = f"POST_EARNINGS_DIGESTION (T+{days_since_last}d)"

        final_multiplier = round(multiplier_base * gap_severity_factor, 3)

        # Allocation Gating Rules across 5 ETF Strategy tiers
        gating_rules = self.get_allocation_gating_rules(
            is_in_event_window=is_in_event_window,
            hist_gap=hist_gap
        )

        return {
            "earnings_multiplier": final_multiplier,
            "multiplier_base": multiplier_base,
            "active_window": active_window,
            "days_to_next_earnings": days_to_next,
            "days_since_last_earnings": days_since_last,
            "historical_gap_severity": round(hist_gap, 4),
            "is_in_event_window": is_in_event_window,
            "allocation_gating": gating_rules,
            "allocation_constraint_summary": (
                "Restricted (Earnings Event Window)" if is_in_event_window else "Normal Allocation (Unrestricted)"
            )
        }

    def get_allocation_gating_rules(
        self,
        is_in_event_window: bool,
        hist_gap: float,
        multiplier: float = 1.0
    ) -> dict[str, str]:
        """
        Strategy Allocation Gating Rules across 3 ETF Strategy tiers.
        """
        if not is_in_event_window:
            return {
                "Level 1: Boomer Haven": "Normal Allocation (Unrestricted)",
                "Level 2: Steady Grind": "Normal Allocation (Unrestricted)",
                "Level 3: Diamond Hands": "Normal Allocation (No Gating / Full Momentum)",
            }

        lvl1_rule = "Restricted (Hard Buy Freeze)" if multiplier > 1.15 else "Normal Allocation (Unrestricted)"
        lvl2_rule = "Restricted (5% Position Cap)" if (multiplier > 1.30 or hist_gap >= 0.06) else "Normal Allocation (Unrestricted)"
        lvl3_rule = "Normal Allocation (No Gating / Full Momentum)"

        return {
            "Level 1: Boomer Haven": lvl1_rule,
            "Level 2: Steady Grind": lvl2_rule,
            "Level 3: Diamond Hands": lvl3_rule,
        }

    def apply_to_composite_score(
        self,
        base_crs: float,
        ticker: str,
        price_history: pd.DataFrame | None = None,
        override_days_to_next: int | None = None,
        override_days_since_last: int | None = None
    ) -> dict[str, Any]:
        """
        Adjusts base CRS with Earnings Risk Multiplier:
          CRS_adjusted = min(100, Base_CRS * M_earnings)
        Re-maps to ETF strategy level (3-Tier Stratification) and resolves hierarchical trading permissions.
        """
        earnings_data = self.calculate_earnings_multiplier(
            ticker=ticker,
            price_history=price_history,
            override_days_to_next=override_days_to_next,
            override_days_since_last=override_days_since_last
        )
        multiplier = earnings_data["earnings_multiplier"]
        adjusted_crs = min(100.0, round(base_crs * multiplier, 2))

        # Re-compute gating rules with calculated multiplier
        earnings_data["allocation_gating"] = self.get_allocation_gating_rules(
            is_in_event_window=earnings_data["is_in_event_window"],
            hist_gap=earnings_data["historical_gap_severity"],
            multiplier=multiplier
        )

        # 3-Tier CRS Score Stratification:
        # Level 1: 0.0 – 35.0  (Boomer Haven ETF)
        # Level 2: 35.1 – 68.0 (Steady Grind ETF)
        # Level 3: 68.1 – 100.0 (Diamond Hands ETF)
        if adjusted_crs <= 35.0:
            assigned_level, etf_name = 1, "Boomer Haven ETF"
        elif adjusted_crs <= 68.0:
            assigned_level, etf_name = 2, "Steady Grind ETF"
        else:
            assigned_level, etf_name = 3, "Diamond Hands ETF"

        from services.risk_classifier import get_eligible_trading_levels
        eligible_levels, eligible_vaults = get_eligible_trading_levels(assigned_level)

        return {
            "ticker": ticker,
            "base_crs": base_crs,
            "earnings_multiplier": multiplier,
            "adjusted_crs": adjusted_crs,
            "assigned_level": assigned_level,
            "assigned_etf": etf_name,
            "eligible_levels": eligible_levels,
            "eligible_vaults": eligible_vaults,
            "earnings_data": earnings_data,
        }



# Singleton earnings risk engine instance
earnings_risk_engine = EarningsRiskEngine()
