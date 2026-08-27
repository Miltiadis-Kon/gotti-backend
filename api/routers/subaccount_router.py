from fastapi import APIRouter, HTTPException, Query
from models.client import (
    SubAccountModel,
    SubAccountWithHoldingsModel,
    HoldingPositionModel,
    CreateSubAccountRequest,
    UpdateSubAccountStrategyRequest,
    TransferCashRequest,
    FundSubAccountRequest,
    WithdrawSubAccountRequest,
    TransactionRecordModel
)
from services.client_service import client_service
from db.repository import repo

router = APIRouter(tags=["Sub-Accounts & Ledger"])


@router.get("/sub-accounts", response_model=list[SubAccountModel])
def get_all_sub_accounts(user_id: str = Query("usr-gotti-demo", description="Client user ID")):
    """Get all segregated ETF sub-accounts for a client (strictly sorted L1 to L3)."""

    try:
        return client_service.get_sub_accounts_for_user(user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sub-accounts", response_model=SubAccountModel)
def create_sub_account(request: CreateSubAccountRequest):
    """Create a new segregated ETF Sub-Account (Enforces Rule 1: Max 1 per risk tier)."""
    try:
        return client_service.create_sub_account(
            user_id=request.userId,
            risk_level=request.riskLevel,
            allocated_capital=request.allocatedCapital,
            custom_name=request.customName
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sub-accounts/{sub_account_id}", response_model=SubAccountWithHoldingsModel)
def get_sub_account_details(sub_account_id: str):
    """Get detailed sub-account view with asset allocation holdings and metrics."""
    try:
        return client_service.get_sub_account_with_details(sub_account_id=sub_account_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/sub-accounts/{sub_account_id}/strategy", response_model=SubAccountModel)
def update_sub_account_strategy(sub_account_id: str, request: UpdateSubAccountStrategyRequest):
    """Change a sub-account's strategy risk level and trigger rebalancing."""
    try:
        return client_service.update_sub_account_strategy(
            sub_account_id=sub_account_id,
            new_risk_level=request.newRiskLevel
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sub-accounts/{sub_account_id}")
def delete_sub_account(
    sub_account_id: str,
    user_id: str = Query("usr-gotti-demo", description="Client user ID")
):
    """Liquidate and delete an active sub-account."""
    try:
        client_service.delete_sub_account(sub_account_id=sub_account_id, user_id=user_id)
        return {"status": "ok", "message": f"Sub-account {sub_account_id} liquidated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sub-accounts/transfer")
def transfer_cash_between_sub_accounts(request: TransferCashRequest):
    """Transfer cash balance between two segregated sub-accounts without liquidation."""
    try:
        from_acc, to_acc = client_service.transfer_cash_between_sub_accounts(
            from_id=request.fromSubAccountId,
            to_id=request.toSubAccountId,
            amount=request.amount
        )
        return {
            "status": "ok",
            "fromAccount": from_acc,
            "toAccount": to_acc
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sub-accounts/{sub_account_id}/holdings", response_model=list[HoldingPositionModel])
def get_sub_account_holdings(sub_account_id: str):
    """Get live calculated stock position holdings for a sub-account."""
    try:
        account = repo.get_sub_account(sub_account_id)
        if not account:
            raise HTTPException(status_code=404, detail=f"Sub-account {sub_account_id} not found")
        return client_service.calculate_sub_account_holdings(account)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sub-accounts/{sub_account_id}/deposit", response_model=SubAccountModel)
@router.post("/sub-accounts/{sub_account_id}/fund", response_model=SubAccountModel)
def fund_sub_account(sub_account_id: str, request: FundSubAccountRequest):
    """Deposit fiat funds into a segregated sub-account."""
    try:
        return client_service.fund_sub_account(
            sub_account_id=sub_account_id,
            amount=request.amount,
            payment_method=request.paymentMethod
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sub-accounts/{sub_account_id}/withdraw", response_model=SubAccountModel)
def withdraw_from_sub_account(sub_account_id: str, request: WithdrawSubAccountRequest):
    """Withdraw funds from a segregated sub-account."""
    try:
        return client_service.withdraw_from_sub_account(
            sub_account_id=sub_account_id,
            amount=request.amount,
            destination=request.destination
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transactions", response_model=list[TransactionRecordModel])
def get_client_transactions(
    user_id: str = Query("usr-gotti-demo", description="Client user ID"),
    sub_account_id: str | None = Query(None, description="Filter by Sub-Account ID"),
    limit: int = Query(100, le=500)
):
    """Retrieve financial transaction history."""
    try:
        return repo.get_client_transactions(
            user_id=user_id,
            sub_account_id=sub_account_id,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
