from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from db.repository import repo
from models.signal import CompositeRiskEvaluation, TickerRiskAssignment, EarningsRiskData
from services.risk_classifier import risk_classifier, is_trade_permitted
from services.earnings_risk_engine import earnings_risk_engine

router = APIRouter(prefix='/signals', tags=['Signals & Risk Engine'])


class BatchEvaluateRequest(BaseModel):
    tickers: list[str]


class TradePermissionCheckResponse(BaseModel):
    ticker: str
    base_risk_level: int
    target_risk_level: int
    permitted: bool
    message: str
    eligible_levels: list[int]


class EarningsEventRiskResponse(BaseModel):
    ticker: str
    earnings_risk: EarningsRiskData
    allocation_gating: dict[str, str]


@router.get('/')
def get_latest_signals(limit: int = 50):
    """Return latest signals from stock-alchemist."""
    signals = repo.get_latest_signals(limit=limit)
    return [
        {
            'signal_id': s.signal_id,
            'ticker': s.ticker,
            'signal_position': s.signal_position,
            'sentiment': s.sentiment,
            'signal_date': s.signal_date.isoformat(),
            'created_at': s.created_at.isoformat() if s.created_at else None,
        }
        for s in signals
    ]


@router.get('/{ticker}/evaluate', response_model=CompositeRiskEvaluation)
def evaluate_ticker_risk(
    ticker: str,
    override_days_to_next: int | None = Query(None, description="Simulate days until next earnings event (0=Event Day, 1-3=Imminent, etc.)"),
    override_days_since_last: int | None = Query(None, description="Simulate days elapsed since last earnings event")
):
    """
    Run full 5-Step Dual-Horizon Composite Risk Score (CRS) quantitative evaluation on a ticker:
      • Step 1: Dual-Horizon Volatility & Acceleration (25%)
      • Step 2: Dual-Horizon Drawdowns & Ulcer Index (25%)
      • Step 3: Systematic Beta against S&P 500 (20%)
      • Step 4: Tail Risk CVaR 95% (15%)
      • Step 5: Size & Liquidity / Market Cap (15%)
      • Dynamic Earnings Event Risk Multiplier (M_earnings) & Strategy Allocation Gating Rules
      • Hierarchical Upward Trading Permissions (L_adjusted -> L_adjusted..3)
    """
    try:
        return risk_classifier.evaluate_ticker_quantitative(
            ticker=ticker.upper().strip(),
            override_days_to_next=override_days_to_next,
            override_days_since_last=override_days_since_last
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to evaluate risk for {ticker}: {str(e)}"
        )


@router.get('/{ticker}/earnings', response_model=EarningsEventRiskResponse)
def get_ticker_earnings_risk(ticker: str):
    """
    Detect earnings announcement dates, proximity window, overnight jump severity,
    and portfolio allocation gating constraints for Levels 1–3.
    """
    try:
        data = earnings_risk_engine.calculate_earnings_multiplier(ticker=ticker.upper().strip())
        return EarningsEventRiskResponse(
            ticker=ticker.upper().strip(),
            earnings_risk=EarningsRiskData(
                earnings_multiplier=data["earnings_multiplier"],
                active_window=data["active_window"],
                days_to_next_earnings=data["days_to_next_earnings"],
                days_since_last_earnings=data["days_since_last_earnings"],
                historical_gap_severity=data["historical_gap_severity"],
                is_in_event_window=data["is_in_event_window"],
                allocation_constraint_summary=data["allocation_constraint_summary"]
            ),
            allocation_gating=data["allocation_gating"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch earnings risk for {ticker}: {str(e)}"
        )


@router.post('/evaluate-batch', response_model=list[CompositeRiskEvaluation])
def evaluate_batch_tickers(request: BatchEvaluateRequest):
    """Evaluate a batch of tickers using the Dual-Horizon CRS engine."""
    results = []
    for ticker in request.tickers:
        try:
            res = risk_classifier.evaluate_ticker_quantitative(ticker.upper().strip())
            results.append(res)
        except Exception:
            continue
    return results


@router.get('/{ticker}/can-trade/{target_level}', response_model=TradePermissionCheckResponse)
def check_ticker_trade_permission(ticker: str, target_level: int):
    """
    Check if a ticker is permitted to be traded in a target ETF risk level.
    Enforces the Hierarchical Upward Trading Permission Rule:
      - Level 1 ticker -> Permitted in Levels 1..3
      - Level 2 ticker -> Permitted in Levels 2..3
      - Level 3 ticker -> Permitted in Level 3
    """
    if target_level not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="Target risk level must be between 1 and 3.")

    permitted, msg = risk_classifier.is_eligible_for_level(ticker.upper().strip(), target_level)
    assignment = risk_classifier.classify_ticker(ticker.upper().strip())
    base_lvl = assignment.assigned_risk_level if assignment else 2

    return TradePermissionCheckResponse(
        ticker=ticker.upper().strip(),
        base_risk_level=base_lvl,
        target_risk_level=target_level,
        permitted=permitted,
        message=msg,
        eligible_levels=assignment.eligible_levels if assignment else list(range(base_lvl, 4))
    )



@router.get('/{ticker}/risk', response_model=TickerRiskAssignment)
def get_ticker_risk(ticker: str):
    """Classify a ticker's risk level and retrieve its eligible trading tiers."""
    assignment = risk_classifier.classify_ticker(ticker.upper().strip())
    if not assignment:
        raise HTTPException(
            status_code=404,
            detail=f'No evaluation data found for {ticker}'
        )
    return assignment


@router.get('/assignments')
def get_risk_assignments(risk_level: int | None = None, limit: int = 50):
    """Return ticker risk assignments, optionally filtered by level."""
    assignments = repo.get_risk_assignments(risk_level=risk_level, limit=limit)
    return [a.model_dump() for a in assignments]
