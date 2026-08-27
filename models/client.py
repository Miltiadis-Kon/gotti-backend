from datetime import datetime
from decimal import Decimal
from typing import Literal, Any
from pydantic import BaseModel, Field


RiskLevelType = Literal[1, 2, 3]


class UserProfile(BaseModel):
    id: str
    email: str
    riskLevel: int = Field(default=2, alias="riskLevel")
    riskScore: int | None = Field(default=None, alias="riskScore")
    strategyName: str = Field(default="Steady Grind ETF", alias="strategyName")
    isLoggedIn: bool = Field(default=True, alias="isLoggedIn")
    activeSubAccountId: str = Field(default="", alias="activeSubAccountId")
    totalCashBalance: float = Field(default=0.0, alias="totalCashBalance")
    answers: dict[str, str] | None = None
    createdAt: str | None = None
    updatedAt: str | None = None

    class Config:
        populate_by_name = True


class UserRegisterRequest(BaseModel):
    email: str
    password: str | None = None
    name: str | None = None
    riskLevel: int = 2
    riskScore: int | None = None
    answers: dict[str, str] | None = None



class UserLoginRequest(BaseModel):
    email: str
    password: str | None = None


class UserProfileUpdateRequest(BaseModel):
    email: str | None = None
    riskLevel: int | None = None
    riskScore: int | None = None
    strategyName: str | None = None
    isLoggedIn: bool | None = None
    activeSubAccountId: str | None = None
    totalCashBalance: float | None = None
    answers: dict[str, str] | None = None


class SubAccountModel(BaseModel):
    id: str
    name: str
    riskLevel: int
    strategyName: str
    allocatedCapital: float
    currentValue: float
    cashBalance: float
    investedAmount: float
    pnl: float
    pnlPercentage: float
    status: Literal["active", "rebalancing", "paused"] = "active"
    createdAt: str
    holdingsCount: int = 0
    description: str | None = None


class CreateSubAccountRequest(BaseModel):
    userId: str = "usr-gotti-demo"
    riskLevel: int
    allocatedCapital: float
    customName: str | None = None


class UpdateSubAccountStrategyRequest(BaseModel):
    newRiskLevel: int


class TransferCashRequest(BaseModel):
    fromSubAccountId: str
    toSubAccountId: str
    amount: float


class FundSubAccountRequest(BaseModel):
    amount: float
    paymentMethod: str = "Instant Card (Stripe)"


class WithdrawSubAccountRequest(BaseModel):
    amount: float
    destination: str = "Bank Wire"


class HoldingPositionModel(BaseModel):
    ticker: str
    name: str
    weightPercentage: float
    weightDecimal: float
    allocatedAmount: float
    unrealizedPnl: float
    unrealizedPnlPercentage: float
    currentPrice: float
    sharesOwned: float
    sector: str
    isPositive: bool


class SubAccountMetrics(BaseModel):
    sharpeRatio: float
    maxDrawdown: str
    volatilityBeta: str
    winRate: str
    tradeRatio: str


class SubAccountWithHoldingsModel(SubAccountModel):
    profile: dict[str, Any]
    holdings: list[HoldingPositionModel]
    metrics: SubAccountMetrics


class AggregatedFinancialsModel(BaseModel):
    totalAllocatedCapital: float
    totalCurrentValue: float
    totalCashBalance: float
    totalInvestedAmount: float
    totalUnrealizedPnl: float
    totalUnrealizedPnlPercentage: float
    totalActiveSubAccounts: int
    availableCashBuffer: float
    maxDrawdownEstimate: float
    weightedAnnualYieldTarget: str


class TransactionRecordModel(BaseModel):
    id: str
    subAccountId: str
    subAccountName: str
    strategyName: str
    amount: float
    type: Literal["Deposit", "Withdrawal", "Rebalance", "Dividend"]
    status: Literal["Fulfilled", "Pending", "Processing", "Failed"] = "Fulfilled"
    method: str
    date: str
    timestamp: int
    notes: str | None = None


class FullUserSnapshotModel(BaseModel):
    version: str = "1.0.0"
    exportedAt: str
    user: UserProfile
    aggregatedFinancials: AggregatedFinancialsModel
    subAccounts: list[SubAccountWithHoldingsModel]
    transactions: list[TransactionRecordModel]
