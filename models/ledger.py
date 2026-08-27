from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel


class UserHolding(BaseModel):
    """A user's unit balance in a specific ETF vault."""
    id: str
    user_id: str
    vault_id: str
    units_balance: Decimal
    total_deposited: Decimal
    total_withdrawn: Decimal
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Transaction(BaseModel):
    """A deposit or withdrawal record."""
    id: str
    user_id: str
    vault_id: str
    transaction_type: Literal['DEPOSIT', 'WITHDRAWAL']
    fiat_amount: Decimal
    units: Decimal
    nav_at_time: Decimal
    created_at: datetime | None = None


class PortfolioValuation(BaseModel):
    """Live valuation of a user's position in a single vault."""
    vault_name: str
    risk_level: int
    units_held: str
    nav_per_unit: str
    current_value_eur: str
    net_pnl_eur: str
    return_percentage: str
