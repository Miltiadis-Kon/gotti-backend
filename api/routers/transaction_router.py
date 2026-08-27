from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from services.fund_engine import fund_engine
from db.repository import repo

router = APIRouter(tags=['Transactions'])


class DepositRequest(BaseModel):
    user_id: str
    risk_level: int
    amount: float  # EUR amount to deposit


class WithdrawRequest(BaseModel):
    user_id: str
    risk_level: int
    units: float  # Units to burn


@router.post('/deposit')
def deposit(request: DepositRequest):
    """Deposit fiat and mint units in the specified vault."""
    try:
        amount = Decimal(str(request.amount))
        if amount <= Decimal('0'):
            raise ValueError('Amount must be positive')
        result = fund_engine.process_deposit(
            user_id=request.user_id,
            risk_level=request.risk_level,
            amount_eur=amount,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/withdraw')
def withdraw(request: WithdrawRequest):
    """Burn units and compute fiat payout from the specified vault."""
    try:
        units = Decimal(str(request.units))
        if units <= Decimal('0'):
            raise ValueError('Units must be positive')
        result = fund_engine.process_withdrawal(
            user_id=request.user_id,
            risk_level=request.risk_level,
            units_to_burn=units,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/transactions')
def get_transactions(user_id: str = Query(...), limit: int = Query(50, le=200)):
    """Return transaction history for a user."""
    transactions = repo.get_user_transactions(user_id, limit=limit)
    return [
        {
            'id': tx.id,
            'vault_id': tx.vault_id,
            'type': tx.transaction_type,
            'fiat_amount': str(tx.fiat_amount),
            'units': str(tx.units),
            'nav_at_time': str(tx.nav_at_time),
            'created_at': tx.created_at.isoformat() if tx.created_at else None,
        }
        for tx in transactions
    ]
