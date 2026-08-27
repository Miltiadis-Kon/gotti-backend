import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from db.repository import repo
from models.client import (
    UserProfile,
    SubAccountModel,
    SubAccountWithHoldingsModel,
    HoldingPositionModel,
    AggregatedFinancialsModel,
    TransactionRecordModel,
    FullUserSnapshotModel,
    SubAccountMetrics
)
from services.fund_engine import fund_engine
from services.logging_service import logger
from config.vault_registry import VAULT_REGISTRY


# ── ETF Strategy Universe & Specifications (3-Tier Automated ETF Architecture) ──
ETF_METRICS_MAP: dict[int, SubAccountMetrics] = {
    1: SubAccountMetrics(sharpeRatio=1.85, maxDrawdown="< 15%", volatilityBeta="< 0.75", winRate="88%", tradeRatio="44/50"),
    2: SubAccountMetrics(sharpeRatio=1.55, maxDrawdown="15%–30%", volatilityBeta="0.85–1.25", winRate="76%", tradeRatio="38/50"),
    3: SubAccountMetrics(sharpeRatio=1.35, maxDrawdown="30%–55%+", volatilityBeta="> 1.35", winRate="64%", tradeRatio="32/50"),
}

ETF_STRATEGY_DETAILS: dict[int, dict[str, Any]] = {
    1: {
        "level": 1,
        "strategyName": "Boomer Haven ETF",
        "etfName": "Boomer Haven ETF",
        "tagline": "Capital preservation, reliable dividends, defensive titans.",
        "targetVolatility": "β < 0.75",
        "assetUniverse": "S&P 500 Dividend Aristocrats, Mega-Cap Value & Defensive Tech (KO, PG, JNJ, MSFT, AAPL)",
        "turnoverStrategy": "Pure buy & hold, quarterly rebalance drift (<20% annual turnover)",
        "targetReturn": "5% – 9%",
        "bestFor": "Conservative / Capital Preservation with minimal drawdowns.",
        "color": "#10b981",
        "sampleTickers": ["KO", "PG", "JNJ", "MSFT", "AAPL", "VTI"],
        "holdings": [
            {"ticker": "KO", "name": "The Coca-Cola Company", "weight": 0.22, "sector": "Consumer Staples", "basePrice": 68.50},
            {"ticker": "PG", "name": "Procter & Gamble Co.", "weight": 0.20, "sector": "Consumer Staples", "basePrice": 172.10},
            {"ticker": "JNJ", "name": "Johnson & Johnson", "weight": 0.18, "sector": "Healthcare", "basePrice": 161.40},
            {"ticker": "MSFT", "name": "Microsoft Corporation", "weight": 0.20, "sector": "Information Technology", "basePrice": 420.25},
            {"ticker": "AAPL", "name": "Apple Inc.", "weight": 0.20, "sector": "Information Technology", "basePrice": 224.80},
        ]
    },
    2: {
        "level": 2,
        "strategyName": "Steady Grind ETF",
        "etfName": "Steady Grind ETF",
        "tagline": "Consistent compounding with systematic momentum upside.",
        "targetVolatility": "β ≈ 0.85 - 1.25",
        "assetUniverse": "Large & Mid-Cap Growth Leaders, Systematic Sector Momentum (QQQ, NVDA, META, AMD, ASML, TSM)",
        "turnoverStrategy": "Multi-month trend holding with monthly momentum rebalancing (50%–100% annual)",
        "targetReturn": "10% – 18%",
        "bestFor": "Moderate / Balanced Growth tracking and outperforming market benchmarks.",
        "color": "#6366f1",
        "sampleTickers": ["QQQ", "NVDA", "META", "AMD", "ASML", "TSM"],
        "holdings": [
            {"ticker": "QQQ", "name": "Invesco QQQ Trust", "weight": 0.28, "sector": "Technology Growth", "basePrice": 480.50},
            {"ticker": "NVDA", "name": "Nvidia Corporation", "weight": 0.22, "sector": "Semiconductors", "basePrice": 128.40},
            {"ticker": "META", "name": "Meta Platforms Inc.", "weight": 0.18, "sector": "Interactive Media", "basePrice": 512.20},
            {"ticker": "AMD", "name": "Advanced Micro Devices", "weight": 0.16, "sector": "Semiconductors", "basePrice": 154.80},
            {"ticker": "ASML", "name": "ASML Holding N.V.", "weight": 0.16, "sector": "Semiconductor Equipment", "basePrice": 890.30},
        ]
    },
    3: {
        "level": 3,
        "strategyName": "Diamond Hands ETF",
        "etfName": "Diamond Hands ETF",
        "tagline": "High-beta breakouts, small-cap alpha, and asymmetric acceleration.",
        "targetVolatility": "β > 1.35",
        "assetUniverse": "High-Beta Equities, Emerging Small/Micro-Caps, Dynamic Breakout Stocks (MSTR, NVDA, RIVN, MARA, SOUN)",
        "turnoverStrategy": "High-turnover tactical swing allocation and daily/weekly breakouts (200%+ annual)",
        "targetReturn": "20%+",
        "bestFor": "Aggressive / Speculative Alpha targeting asymmetric upside.",
        "color": "#ef4444",
        "sampleTickers": ["MSTR", "NVDA", "RIVN", "SOUN", "MARA", "IONQ"],
        "holdings": [
            {"ticker": "MSTR", "name": "MicroStrategy Inc.", "weight": 0.30, "sector": "Bitcoin Treasury Alpha", "basePrice": 145.20},
            {"ticker": "NVDA", "name": "Nvidia Alpha Momentum", "weight": 0.25, "sector": "AI Accelerator Swings", "basePrice": 128.40},
            {"ticker": "RIVN", "name": "Rivian Automotive", "weight": 0.18, "sector": "EV Growth Momentum", "basePrice": 14.80},
            {"ticker": "MARA", "name": "MARA Holdings Inc.", "weight": 0.15, "sector": "Digital Mining Infrastructure", "basePrice": 18.90},
            {"ticker": "SOUN", "name": "SoundHound AI Inc.", "weight": 0.12, "sector": "Conversational AI Small-Cap", "basePrice": 5.40},
        ]
    }
}


class ClientService:
    """Service managing client registries, multi-sub-accounts, ledger funds, and PnL."""

    def seed_initial_demo_data(self) -> None:
        """Seed the database with the default demo user and initial sub-accounts if empty."""
        demo_user = repo.get_user("usr-gotti-demo")
        if not demo_user:
            logger.info("Seeding demo client: usr-gotti-demo")
            repo.create_user(
                user_id="usr-gotti-demo",
                email="investor@gotti.ai",
                name="Gotti Investor",
                risk_level=2,
                risk_score=26,
                strategy_name="Steady Grind ETF",
                active_sub_account_id="sub-main-02",
                total_cash_balance=11457.05,
                answers={"1": "B", "2": "C", "3": "C", "4": "C", "5": "C", "6": "B", "7": "B", "8": "C", "9": "C", "10": "C"}
            )

        # Seed sub-accounts if empty (3-Tier Segregated ETF Vaults)
        sub_accounts = repo.get_sub_accounts("usr-gotti-demo")
        if not sub_accounts:
            logger.info("Seeding demo sub-accounts for usr-gotti-demo")
            initial_subs = [
                {
                    "id": "sub-defensive-01",
                    "name": "Level 1: Boomer Haven ETF",
                    "risk_level": 1,
                    "strategy_name": "Boomer Haven ETF",
                    "allocated_capital": 25000.0,
                    "current_value": 26350.00,
                    "cash_balance": 2635.00,
                    "invested_amount": 23715.00,
                    "pnl": 1350.00,
                    "pnl_percentage": 5.40,
                    "status": "active",
                    "holdings_count": 5,
                    "description": "S&P 500 Dividend Aristocrats, Mega-Cap Value & Defensive Tech. Pure buy & hold.",
                    "created_at": "2026-02-01"
                },
                {
                    "id": "sub-main-02",
                    "name": "Level 2: Steady Grind ETF",
                    "risk_level": 2,
                    "strategy_name": "Steady Grind ETF",
                    "allocated_capital": 45000.0,
                    "current_value": 50820.50,
                    "cash_balance": 5082.05,
                    "invested_amount": 45738.45,
                    "pnl": 5820.50,
                    "pnl_percentage": 12.93,
                    "status": "active",
                    "holdings_count": 5,
                    "description": "Large & Mid-Cap Growth Leaders, Systematic Sector Momentum. Multi-month swings.",
                    "created_at": "2026-01-15"
                },
                {
                    "id": "sub-alpha-03",
                    "name": "Level 3: Diamond Hands ETF",
                    "risk_level": 3,
                    "strategy_name": "Diamond Hands ETF",
                    "allocated_capital": 30000.0,
                    "current_value": 37400.00,
                    "cash_balance": 3740.00,
                    "invested_amount": 33660.00,
                    "pnl": 7400.00,
                    "pnl_percentage": 24.67,
                    "status": "active",
                    "holdings_count": 5,
                    "description": "High-Beta Equities, Emerging Small/Micro-Caps, Dynamic Breakout Stocks. Tactical momentum.",
                    "created_at": "2026-03-10"
                }
            ]
            for s in initial_subs:
                repo.create_sub_account(
                    sub_account_id=s["id"],
                    user_id="usr-gotti-demo",
                    name=s["name"],
                    risk_level=s["risk_level"],
                    strategy_name=s["strategy_name"],
                    allocated_capital=s["allocated_capital"],
                    current_value=s["current_value"],
                    cash_balance=s["cash_balance"],
                    invested_amount=s["invested_amount"],
                    pnl=s["pnl"],
                    pnl_percentage=s["pnl_percentage"],
                    status=s["status"],
                    holdings_count=s["holdings_count"],
                    description=s["description"],
                    created_at=s["created_at"]
                )

        # Seed initial transactions if empty
        txs = repo.get_client_transactions("usr-gotti-demo")
        if not txs:
            logger.info("Seeding demo client transactions")
            repo.record_client_transaction(
                tx_id="tx-101",
                user_id="usr-gotti-demo",
                sub_account_id="sub-main-02",
                sub_account_name="Level 2: Steady Grind ETF",
                strategy_name="Steady Grind ETF",
                amount=15000.0,
                tx_type="Deposit",
                status="Fulfilled",
                method="Bank Wire Transfer (•••• 5821)",
                notes="Initial portfolio onboarding allocation",
                tx_date="2026-08-20",
                timestamp=1787200000000
            )
            repo.record_client_transaction(
                tx_id="tx-102",
                user_id="usr-gotti-demo",
                sub_account_id="sub-alpha-03",
                sub_account_name="Level 3: Diamond Hands ETF",
                strategy_name="Diamond Hands ETF",
                amount=10000.0,
                tx_type="Deposit",
                status="Fulfilled",
                method="Credit Card (Stripe)",
                notes="Direct high-beta sub-account deployment",
                tx_date="2026-08-22",
                timestamp=1787380000000
            )
            repo.record_client_transaction(
                tx_id="tx-103",
                user_id="usr-gotti-demo",
                sub_account_id="sub-defensive-01",
                sub_account_name="Level 1: Boomer Haven ETF",
                strategy_name="Boomer Haven ETF",
                amount=5000.0,
                tx_type="Deposit",
                status="Fulfilled",
                method="Debit Card (•••• 1234)",
                notes="Defensive capital top-up",
                tx_date="2026-08-25",
                timestamp=1787600000000
            )


        # Seed initial sample orders if empty
        orders = repo.get_orders(limit=10)
        if not orders:
            logger.info("Seeding demo order history")
            sample_orders = [
                {"date": "01/08/24", "symbol": "AAPL", "name": "Apple Inc.", "status": "Open", "buy_price": 148.97, "sell_price": None, "profit": None, "order_amount": 100.0, "total_amount": 15029.0, "type": "Buy"},
                {"date": "02/08/24", "symbol": "MSFT", "name": "Microsoft Corporation", "status": "Closed", "buy_price": 301.15, "sell_price": 301.29, "profit": -14.0, "order_amount": 100.0, "total_amount": 30129.0, "type": "Sell"},
                {"date": "02/08/24", "symbol": "GOOGL", "name": "Alphabet Inc.", "status": "Closed", "buy_price": 2800.0, "sell_price": 2900.0, "profit": 100.0, "order_amount": 10.0, "total_amount": 29000.0, "type": "Buy"},
                {"date": "03/08/24", "symbol": "AMZN", "name": "Amazon.com, Inc.", "status": "Closed", "buy_price": 3500.0, "sell_price": 3400.0, "profit": -100.0, "order_amount": 5.0, "total_amount": 17000.0, "type": "Sell"}
            ]
            for o in sample_orders:
                repo.create_order(
                    order_date=o["date"],
                    symbol=o["symbol"],
                    name=o["name"],
                    status=o["status"],
                    buy_price=o["buy_price"],
                    sell_price=o["sell_price"],
                    profit=o["profit"],
                    order_amount=o["order_amount"],
                    total_amount=o["total_amount"],
                    order_type=o["type"]
                )

    # ── User Profile & Identity ──────────────────────────────────────

    def get_or_create_user(self, user_id: str = "usr-gotti-demo", email: str = "investor@gotti.ai") -> UserProfile:
        """Get the active user profile, or create it if missing."""
        user = repo.get_user(user_id)
        if not user:
            user = repo.create_user(
                user_id=user_id,
                email=email,
                name="Gotti Investor",
                risk_level=3,
                risk_score=26,
                strategy_name="Steady Grind ETF",
                active_sub_account_id="sub-main-01",
                total_cash_balance=11457.05
            )
        return user

    def update_user_profile(self, user_id: str, updates: dict[str, Any]) -> UserProfile:
        """Update user profile fields."""
        if "riskLevel" in updates:
            lvl = int(updates["riskLevel"])
            config = VAULT_REGISTRY.get(lvl)
            if config:
                updates["strategyName"] = config.name

        user = repo.update_user(user_id, **updates)
        if not user:
            raise ValueError(f"User {user_id} not found")
        return user

    # ── Sub-Account Operations ───────────────────────────────────────

    def get_sub_accounts_for_user(self, user_id: str = "usr-gotti-demo") -> list[SubAccountModel]:
        """Fetch all segregated sub-accounts for the user."""
        return repo.get_sub_accounts(user_id)

    def get_sub_account_with_details(self, sub_account_id: str) -> SubAccountWithHoldingsModel:
        """Return sub-account with live asset holdings and metrics."""
        account = repo.get_sub_account(sub_account_id)
        if not account:
            raise ValueError(f"Sub-account {sub_account_id} not found")

        strategy_info = ETF_STRATEGY_DETAILS.get(account.riskLevel, ETF_STRATEGY_DETAILS[3])
        metrics = ETF_METRICS_MAP.get(account.riskLevel, ETF_METRICS_MAP[3])
        holdings = self.calculate_sub_account_holdings(account)

        return SubAccountWithHoldingsModel(
            **account.model_dump(),
            profile=strategy_info,
            holdings=holdings,
            metrics=metrics
        )

    def calculate_sub_account_holdings(self, account: SubAccountModel) -> list[HoldingPositionModel]:
        """Generate live holding allocations for a sub-account."""
        strategy_info = ETF_STRATEGY_DETAILS.get(account.riskLevel, ETF_STRATEGY_DETAILS[3])
        universe = strategy_info.get("holdings", [])
        nav = account.currentValue

        positions: list[HoldingPositionModel] = []
        for idx, asset in enumerate(universe):
            weight = asset["weight"]
            allocated = round(nav * weight, 2)
            mock_pnl_ratio = (0.08 if idx % 2 == 0 else -0.03) + (account.riskLevel * 0.02)
            unrealized_pnl = round(allocated * mock_pnl_ratio, 2)
            pnl_pct = round(mock_pnl_ratio * 100, 2)
            base_price = asset["basePrice"]
            shares = round(allocated / base_price, 2) if base_price > 0 else 0.0

            positions.append(
                HoldingPositionModel(
                    ticker=asset["ticker"],
                    name=asset["name"],
                    weightPercentage=round(weight * 100),
                    weightDecimal=weight,
                    allocatedAmount=allocated,
                    unrealizedPnl=unrealized_pnl,
                    unrealizedPnlPercentage=pnl_pct,
                    currentPrice=base_price,
                    sharesOwned=shares,
                    sector=asset["sector"],
                    isPositive=unrealized_pnl >= 0
                )
            )
        return positions

    def create_sub_account(self, user_id: str, risk_level: int, allocated_capital: float, custom_name: str | None = None) -> SubAccountModel:
        """Create a new segregated sub-account enforcing Rule 1 (Max 1 per risk tier)."""
        existing_accounts = repo.get_sub_accounts(user_id)

        # Enforce Rule 1
        for acc in existing_accounts:
            if acc.riskLevel == risk_level:
                raise ValueError(
                    f"Rule 1 Violation: Level {risk_level} ({VAULT_REGISTRY[risk_level].name}) is already active. "
                    "Only 1 sub-account allowed per risk level."
                )

        if len(existing_accounts) >= 3:
            raise ValueError("Maximum of 3 sub-accounts reached (1 per Risk Level 1–3).")


        config = VAULT_REGISTRY[risk_level]
        strategy_info = ETF_STRATEGY_DETAILS[risk_level]
        auto_name = custom_name or f"Level {risk_level}: {config.name}"
        sub_id = f"sub-{int(datetime.now(timezone.utc).timestamp())}-{uuid.uuid4().hex[:4]}"

        initial_cash = round(allocated_capital * 0.10, 2)
        initial_invested = round(allocated_capital * 0.90, 2)

        new_acc = repo.create_sub_account(
            sub_account_id=sub_id,
            user_id=user_id,
            name=auto_name,
            risk_level=risk_level,
            strategy_name=config.name,
            allocated_capital=allocated_capital,
            current_value=allocated_capital,
            cash_balance=initial_cash,
            invested_amount=initial_invested,
            pnl=0.0,
            pnl_percentage=0.0,
            status="active",
            holdings_count=len(strategy_info.get("sampleTickers", [])),
            description=config.description
        )

        # Update active sub-account ID on user profile
        repo.update_user(user_id, activeSubAccountId=new_acc.id)

        # Record funding transaction
        if allocated_capital > 0:
            repo.record_client_transaction(
                tx_id=f"tx-{uuid.uuid4().hex[:8]}",
                user_id=user_id,
                sub_account_id=new_acc.id,
                sub_account_name=new_acc.name,
                strategy_name=new_acc.strategyName,
                amount=allocated_capital,
                tx_type="Deposit",
                status="Fulfilled",
                method="Initial Capital Allocation",
                notes="Sub-account initial deployment"
            )

        logger.deposit(f"Sub-account created: {new_acc.name} for user {user_id} with €{allocated_capital}")
        return new_acc

    def update_sub_account_strategy(self, sub_account_id: str, new_risk_level: int) -> SubAccountModel:
        """Update a sub-account's risk tier and rebalance."""
        account = repo.get_sub_account(sub_account_id)
        if not account:
            raise ValueError(f"Sub-account {sub_account_id} not found")

        # Verify Rule 1
        user_accounts = repo.get_sub_accounts(account.id)
        for acc in user_accounts:
            if acc.riskLevel == new_risk_level and acc.id != sub_account_id:
                raise ValueError(f"Rule 1 Violation: Risk Level {new_risk_level} is already used by another active sub-account.")

        config = VAULT_REGISTRY[new_risk_level]
        strategy_info = ETF_STRATEGY_DETAILS[new_risk_level]

        updated = repo.update_sub_account(
            sub_account_id=sub_account_id,
            riskLevel=new_risk_level,
            strategyName=config.name,
            name=f"Level {new_risk_level}: {config.name}",
            description=config.description,
            holdingsCount=len(strategy_info.get("sampleTickers", []))
        )

        # Record rebalance transaction
        repo.record_client_transaction(
            tx_id=f"tx-{uuid.uuid4().hex[:8]}",
            user_id="usr-gotti-demo",
            sub_account_id=sub_account_id,
            sub_account_name=updated.name,
            strategy_name=config.name,
            amount=updated.currentValue,
            tx_type="Rebalance",
            status="Fulfilled",
            method="Systematic Strategy Shift",
            notes=f"Rebalanced to Level {new_risk_level} ({config.name})"
        )

        logger.info(f"Sub-account {sub_account_id} shifted to Level {new_risk_level} ({config.name})")
        return updated

    def delete_sub_account(self, sub_account_id: str, user_id: str = "usr-gotti-demo") -> None:
        """Delete / liquidate a sub-account."""
        accounts = repo.get_sub_accounts(user_id)
        if len(accounts) <= 1:
            raise ValueError("Cannot delete the only remaining active sub-account.")

        target = repo.get_sub_account(sub_account_id)
        if not target:
            raise ValueError(f"Sub-account {sub_account_id} not found")

        repo.delete_sub_account(sub_account_id)

        # Update active sub-account if target was active
        user = repo.get_user(user_id)
        if user and user.activeSubAccountId == sub_account_id:
            remaining = [a for a in accounts if a.id != sub_account_id]
            if remaining:
                repo.update_user(user_id, activeSubAccountId=remaining[0].id)

        # Record liquidation transaction
        repo.record_client_transaction(
            tx_id=f"tx-{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            sub_account_id=target.id,
            sub_account_name=target.name,
            strategy_name=target.strategyName,
            amount=target.currentValue,
            tx_type="Withdrawal",
            status="Fulfilled",
            method="Sub-Account Liquidation",
            notes="Sub-account closed and capital liquidated"
        )
        logger.withdraw(f"Sub-account {target.name} liquidated: €{target.currentValue}")

    # ── Financial Funding & Transfers ────────────────────────────────

    def fund_sub_account(self, sub_account_id: str, amount: float, payment_method: str = "Instant Card (Stripe)") -> SubAccountModel:
        """Deposit funds into a sub-account."""
        if amount <= 0:
            raise ValueError("Deposit amount must be greater than zero.")

        target = repo.get_sub_account(sub_account_id)
        if not target:
            raise ValueError(f"Sub-account {sub_account_id} not found")

        new_allocated = target.allocatedCapital + amount
        new_cash = target.cashBalance + amount
        new_value = target.currentValue + amount
        new_pnl_pct = (target.pnl / new_allocated * 100) if new_allocated > 0 else 0.0

        updated = repo.update_sub_account(
            sub_account_id=sub_account_id,
            allocatedCapital=new_allocated,
            cashBalance=new_cash,
            currentValue=new_value,
            pnlPercentage=round(new_pnl_pct, 2)
        )

        # Also credit units in Module 4 FundEngine
        try:
            fund_engine.process_deposit(
                user_id="usr-gotti-demo",
                risk_level=target.riskLevel,
                amount_eur=Decimal(str(amount))
            )
        except Exception as e:
            logger.error(f"FundEngine ledger sync warning on deposit: {e}")

        # Record transaction
        repo.record_client_transaction(
            tx_id=f"tx-{uuid.uuid4().hex[:8]}",
            user_id="usr-gotti-demo",
            sub_account_id=target.id,
            sub_account_name=target.name,
            strategy_name=target.strategyName,
            amount=amount,
            tx_type="Deposit",
            status="Fulfilled",
            method=payment_method,
            notes=f"Manual funding deposit into {target.name}"
        )

        logger.deposit(f"Funded {target.name} with €{amount} via {payment_method}")
        return updated

    def withdraw_from_sub_account(self, sub_account_id: str, amount: float, destination: str = "Bank Wire") -> SubAccountModel:
        """Withdraw funds from a sub-account."""
        if amount <= 0:
            raise ValueError("Withdrawal amount must be greater than zero.")

        target = repo.get_sub_account(sub_account_id)
        if not target:
            raise ValueError(f"Sub-account {sub_account_id} not found")

        if amount > target.currentValue:
            raise ValueError(f"Insufficient funds: Requested €{amount} but current value is €{target.currentValue}")

        new_allocated = max(0.0, target.allocatedCapital - amount)
        new_cash = max(0.0, target.cashBalance - amount)
        new_value = target.currentValue - amount
        new_pnl_pct = (target.pnl / new_allocated * 100) if new_allocated > 0 else 0.0

        updated = repo.update_sub_account(
            sub_account_id=sub_account_id,
            allocatedCapital=new_allocated,
            cashBalance=new_cash,
            currentValue=new_value,
            pnlPercentage=round(new_pnl_pct, 2)
        )

        repo.record_client_transaction(
            tx_id=f"tx-{uuid.uuid4().hex[:8]}",
            user_id="usr-gotti-demo",
            sub_account_id=target.id,
            sub_account_name=target.name,
            strategy_name=target.strategyName,
            amount=amount,
            tx_type="Withdrawal",
            status="Fulfilled",
            method=destination,
            notes=f"Withdrawal transfer to {destination}"
        )

        logger.withdraw(f"Withdrew €{amount} from {target.name} to {destination}")
        return updated

    def transfer_cash_between_sub_accounts(self, from_id: str, to_id: str, amount: float) -> tuple[SubAccountModel, SubAccountModel]:
        """Transfer cash balance between two segregated sub-accounts."""
        if amount <= 0:
            raise ValueError("Transfer amount must be greater than zero.")

        from_acc = repo.get_sub_account(from_id)
        to_acc = repo.get_sub_account(to_id)

        if not from_acc or not to_acc:
            raise ValueError("Source or destination sub-account not found.")

        if from_acc.cashBalance < amount:
            raise ValueError(f"Insufficient cash balance in {from_acc.name}: Available €{from_acc.cashBalance}, requested €{amount}")

        updated_from = repo.update_sub_account(
            sub_account_id=from_id,
            cashBalance=round(from_acc.cashBalance - amount, 2),
            currentValue=round(from_acc.currentValue - amount, 2),
            allocatedCapital=max(0.0, round(from_acc.allocatedCapital - amount, 2))
        )

        updated_to = repo.update_sub_account(
            sub_account_id=to_id,
            cashBalance=round(to_acc.cashBalance + amount, 2),
            currentValue=round(to_acc.currentValue + amount, 2),
            allocatedCapital=round(to_acc.allocatedCapital + amount, 2)
        )

        # Record internal transfer transactions
        repo.record_client_transaction(
            tx_id=f"tx-{uuid.uuid4().hex[:8]}",
            user_id="usr-gotti-demo",
            sub_account_id=from_acc.id,
            sub_account_name=from_acc.name,
            strategy_name=from_acc.strategyName,
            amount=amount,
            tx_type="Withdrawal",
            status="Fulfilled",
            method="Internal Cash Transfer",
            notes=f"Transferred €{amount} to {to_acc.name}"
        )

        repo.record_client_transaction(
            tx_id=f"tx-{uuid.uuid4().hex[:8]}",
            user_id="usr-gotti-demo",
            sub_account_id=to_acc.id,
            sub_account_name=to_acc.name,
            strategy_name=to_acc.strategyName,
            amount=amount,
            tx_type="Deposit",
            status="Fulfilled",
            method="Internal Cash Transfer",
            notes=f"Received €{amount} from {from_acc.name}"
        )

        logger.info(f"Transferred €{amount} from {from_acc.name} to {to_acc.name}")
        return updated_from, updated_to

    # ── Financial Aggregations & Snapshots ───────────────────────────

    def get_aggregated_financials(self, user_id: str = "usr-gotti-demo") -> AggregatedFinancialsModel:
        """Calculate total aggregated wealth across all user sub-accounts."""
        accounts = repo.get_sub_accounts(user_id)
        total_allocated = sum(a.allocatedCapital for a in accounts)
        total_current = sum(a.currentValue for a in accounts)
        total_cash = sum(a.cashBalance for a in accounts)
        total_invested = sum(a.investedAmount for a in accounts)
        total_pnl = round(total_current - total_allocated, 2)
        total_pnl_pct = round((total_pnl / total_allocated * 100), 2) if total_allocated > 0 else 0.0

        has_high_risk = any(a.riskLevel >= 3 for a in accounts)
        max_dd = 30.0 if has_high_risk else 15.0


        return AggregatedFinancialsModel(
            totalAllocatedCapital=round(total_allocated, 2),
            totalCurrentValue=round(total_current, 2),
            totalCashBalance=round(total_cash, 2),
            totalInvestedAmount=round(total_invested, 2),
            totalUnrealizedPnl=total_pnl,
            totalUnrealizedPnlPercentage=total_pnl_pct,
            totalActiveSubAccounts=len(accounts),
            availableCashBuffer=round(total_cash, 2),
            maxDrawdownEstimate=max_dd,
            weightedAnnualYieldTarget="12% – 18%"
        )

    def export_full_user_snapshot(self, user_id: str = "usr-gotti-demo") -> FullUserSnapshotModel:
        """Export comprehensive single-object snapshot of all user data."""
        user = self.get_or_create_user(user_id)
        accounts = repo.get_sub_accounts(user_id)
        sub_accounts_detailed = [self.get_sub_account_with_details(a.id) for a in accounts]
        financials = self.get_aggregated_financials(user_id)
        transactions = repo.get_client_transactions(user_id)

        return FullUserSnapshotModel(
            version="1.0.0",
            exportedAt=datetime.now(timezone.utc).isoformat(),
            user=user,
            aggregatedFinancials=financials,
            subAccounts=sub_accounts_detailed,
            transactions=transactions
        )


# Singleton client service instance
client_service = ClientService()
