from fastapi import APIRouter, HTTPException, Query
from models.client import (
    UserProfile,
    UserProfileUpdateRequest,
    UserRegisterRequest,
    UserLoginRequest,
    AggregatedFinancialsModel,
    FullUserSnapshotModel
)
from services.client_service import client_service

router = APIRouter(tags=["Client & Auth"])


@router.post("/auth/register", response_model=UserProfile)
def register_user(request: UserRegisterRequest):
    """Register a new client profile."""
    try:
        user = client_service.get_or_create_user(
            user_id=f"usr-{request.email.split('@')[0]}",
            email=request.email
        )
        if request.riskLevel or request.answers:
            user = client_service.update_user_profile(
                user_id=user.id,
                updates={
                    "riskLevel": request.riskLevel,
                    "riskScore": request.riskScore,
                    "answers": request.answers
                }
            )
        return user
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auth/login", response_model=UserProfile)
def login_user(request: UserLoginRequest):
    """Log in an existing client profile."""
    try:
        user = client_service.get_or_create_user(email=request.email)
        return client_service.update_user_profile(user.id, {"isLoggedIn": True})
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/user/profile", response_model=UserProfile)
def get_user_profile(user_id: str = Query("usr-gotti-demo", description="Client user ID")):
    """Get active client profile details."""
    try:
        return client_service.get_or_create_user(user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/user/profile", response_model=UserProfile)
def update_user_profile(
    updates: UserProfileUpdateRequest,
    user_id: str = Query("usr-gotti-demo", description="Client user ID")
):
    """Update client profile settings, risk tier, or answers."""
    try:
        update_dict = {k: v for k, v in updates.model_dump(exclude_unset=True).items() if v is not None}
        return client_service.update_user_profile(user_id=user_id, updates=update_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/user/financials", response_model=AggregatedFinancialsModel)
def get_user_financials(user_id: str = Query("usr-gotti-demo", description="Client user ID")):
    """Calculate aggregated wealth, NAV, cash, and PnL across all client sub-accounts."""
    try:
        return client_service.get_aggregated_financials(user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/snapshot", response_model=FullUserSnapshotModel)
def export_user_snapshot(user_id: str = Query("usr-gotti-demo", description="Client user ID")):
    """Export complete snapshot of user profile, sub-accounts, transactions, and holdings."""
    try:
        return client_service.export_full_user_snapshot(user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user/reset", response_model=FullUserSnapshotModel)
def reset_user_state(user_id: str = Query("usr-gotti-demo", description="Client user ID")):
    """Reset user state to default demo profile and accounts."""
    try:
        client_service.seed_initial_demo_data()
        return client_service.export_full_user_snapshot(user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
