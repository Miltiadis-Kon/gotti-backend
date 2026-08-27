from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class Vault(BaseModel):
    """Represents an ETF vault with its current NAVPU state."""
    id: str
    risk_level: int
    name: str
    symbol: str
    current_nav_per_unit: Decimal
    total_units_outstanding: Decimal
    annual_fee: Decimal
    last_synced_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NavSnapshot(BaseModel):
    """A point-in-time record of vault NAVPU and broker equity."""
    id: str
    vault_id: str
    nav_per_unit: Decimal
    broker_equity: Decimal
    strategy_return_pct: Decimal | None = None
    recorded_at: datetime
