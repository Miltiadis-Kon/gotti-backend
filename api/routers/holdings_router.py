from fastapi import APIRouter, HTTPException, Query
from services.fund_engine import fund_engine

router = APIRouter(prefix='/holdings', tags=['Holdings'])


@router.get('/')
def get_all_holdings(user_id: str = Query(..., description='User ID')):
    """Return a user's holdings across all ETF vaults with live valuations."""
    valuations = fund_engine.get_all_user_valuations(user_id)
    return [v.model_dump() for v in valuations]


@router.get('/{risk_level}')
def get_holding(risk_level: int, user_id: str = Query(..., description='User ID')):
    """Return a user's holding in a specific vault."""
    valuation = fund_engine.get_user_valuation(user_id, risk_level)
    if not valuation:
        raise HTTPException(
            status_code=404,
            detail=f'No holding found for user in level {risk_level}'
        )
    return valuation.model_dump()
