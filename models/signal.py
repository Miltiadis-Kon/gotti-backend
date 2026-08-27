from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, Field


class Signal(BaseModel):
    """A trading signal produced by stock-alchemist."""
    signal_id: str
    ticker: str
    signal_position: str  # BUY / SELL / HOLD
    sentiment: dict | None = None
    signal_date: date
    created_at: datetime | None = None


class Evaluation(BaseModel):
    """Fundamental evaluation data from stock-alchemist."""
    ticker: str
    data: dict  # Full evaluation JSON blob
    created_at: datetime | None = None

    @property
    def risk_score(self) -> float:
        """Extract risk score from evaluation data. Returns 50.0 if not found."""
        if isinstance(self.data, dict):
            return float(self.data.get('risk_score', 50.0))
        return 50.0

    @property
    def overall_score(self) -> float | None:
        """Extract overall score from evaluation data."""
        if isinstance(self.data, dict):
            score = self.data.get('overall_score')
            return float(score) if score is not None else None
        return None

    @property
    def signal(self) -> str | None:
        """Extract signal recommendation from evaluation data."""
        if isinstance(self.data, dict):
            return self.data.get('signal')
        return None

    @property
    def confidence(self) -> float | None:
        """Extract confidence from evaluation data."""
        if isinstance(self.data, dict):
            conf = self.data.get('confidence')
            return float(conf) if conf is not None else None
        return None


class TickerRiskAssignment(BaseModel):
    """Maps a ticker to a risk level based on its evaluation and provides trading permissions."""
    id: str
    ticker: str
    assigned_risk_level: int
    eligible_levels: list[int] = Field(
        default_factory=list,
        description="List of ETF strategy levels (1-3) permitted to trade this ticker (L >= assigned_level)"
    )
    eligible_vaults: list[str] = Field(
        default_factory=list,
        description="Names of ETF strategy vaults permitted to trade this ticker"
    )
    evaluation_score: float | None = None
    signal_position: str | None = None
    assigned_at: datetime | None = None
    details: dict[str, Any] | None = None


class DualHorizonMetrics(BaseModel):
    quarterly_vol: str
    annual_vol: str
    vol_shock_ratio: float
    quarterly_mdd: str
    annual_mdd: str
    quarterly_cvar_95: str
    downside_vol_63: str | None = None
    beta: float | None = None
    market_cap: float | None = None
    dollar_volume_30d: float | None = None


class RiskBreakdown(BaseModel):
    volatility: float = Field(description="Dual-Horizon Volatility & Acceleration score (25% weight)")
    drawdown: float = Field(description="Dual-Horizon Drawdowns & Ulcer Index score (25% weight)")
    beta: float = Field(description="Systematic Beta score against S&P 500 (20% weight)")
    tail_risk: float = Field(description="Tail Risk CVaR 95% score (15% weight)")
    liquidity: float = Field(description="Market Cap & 30d Dollar Volume score (15% weight)")


class EarningsRiskData(BaseModel):
    earnings_multiplier: float = Field(description="Dynamic Multiplier M_earnings based on timeline proximity and gap jump")
    active_window: str = Field(description="Timeline status: EVENT_DAY, IMMINENT_PRE_EARNINGS, PRE_EARNINGS, POST_EARNINGS, etc.")
    days_to_next_earnings: int | None = None
    days_since_last_earnings: int | None = None
    historical_gap_severity: float = Field(description="Mean absolute overnight jump on historical earnings days")
    is_in_event_window: bool = Field(description="True if within T-3d to T+1d earnings window")
    allocation_constraint_summary: str = Field(description="Summary of portfolio allocation gating constraints")


class CompositeRiskEvaluation(BaseModel):
    ticker: str
    base_crs: float = Field(description="Unadjusted Dual-Horizon Composite Risk Score")
    composite_risk_score: float = Field(description="Final Adjusted CRS = min(100, base_crs * M_earnings)")
    earnings_multiplier: float = Field(description="Earnings Risk Multiplier applied to base score")
    assigned_level: int = Field(description="Assigned ETF Strategy Level (1-3) based on Adjusted CRS")
    assigned_etf: str = Field(description="Name of Assigned ETF Strategy")
    eligible_levels: list[int] = Field(
        description="Hierarchical Trading Permission: Level L ticker can be traded in tiers L through 3"
    )
    eligible_vaults: list[str] = Field(
        description="Names of ETF strategy tiers eligible to hold and trade this ticker"
    )
    scores: RiskBreakdown
    metrics: DualHorizonMetrics
    earnings_risk: EarningsRiskData
    allocation_gating: dict[str, str] = Field(
        description="Strategy Allocation Gating Rules across Levels 1-3 during active earnings window"
    )
    evaluated_at: str

