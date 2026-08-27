from decimal import Decimal, ROUND_HALF_EVEN
from datetime import datetime, timezone

from db.repository import repo
from services.alpaca_client import alpaca_factory
from services.logging_service import logger
from config.vault_registry import VAULT_REGISTRY
from models.ledger import PortfolioValuation

# Precision constants for financial calculations
PRECISION_NAV = Decimal('0.000001')     # 6 decimal places
PRECISION_UNITS = Decimal('0.00000001')  # 8 decimal places
PRECISION_FIAT = Decimal('0.01')         # 2 decimal places


class FundEngine:
    """Core Module 4 engine: NAVPU synchronization and unit-based ledger operations."""

    def __init__(self):
        # Track last known broker equity per level for return calculation
        self._last_broker_equity: dict[int, Decimal] = {}

    def sync_strategy_nav(self, risk_level: int) -> Decimal | None:
        """
        Pull equity from the dedicated Alpaca paper account, calculate strategy
        return R_t, apply fee accrual, and update NAVPU in the database.

        Returns the new NAVPU, or None if sync fails.
        """
        try:
            config = VAULT_REGISTRY.get(risk_level)
            if not config:
                logger.error(f'No vault config for risk level {risk_level}')
                return None

            # Skip if no Alpaca credentials configured
            if not config.api_key or not config.secret_key:
                logger.info(f'Skipping NAV sync for Level {risk_level} — no Alpaca credentials')
                return None

            vault = repo.get_vault(risk_level)
            if not vault:
                logger.error(f'Vault not found in DB for risk level {risk_level}')
                return None

            # 1. Fetch current Alpaca equity
            current_equity = alpaca_factory.get_account_equity(risk_level)

            # 2. Calculate strategy return R_t
            previous_equity = self._last_broker_equity.get(risk_level, current_equity)
            self._last_broker_equity[risk_level] = current_equity

            if previous_equity > Decimal('0'):
                return_pct = (current_equity - previous_equity) / previous_equity
            else:
                return_pct = Decimal('0')

            # 3. Apply return and daily fee accrual to NAVPU
            current_navpu = vault.current_nav_per_unit
            daily_fee = Decimal(str(config.annual_fee)) / Decimal('365')
            new_navpu = (
                current_navpu * (Decimal('1') + return_pct)
                - (current_navpu * daily_fee)
            ).quantize(PRECISION_NAV, rounding=ROUND_HALF_EVEN)

            # 4. Persist to database
            now = datetime.now(timezone.utc)
            repo.update_vault_navpu(vault.id, new_navpu, now)
            repo.record_nav_snapshot(
                vault_id=vault.id,
                nav_per_unit=new_navpu,
                broker_equity=current_equity,
                strategy_return_pct=return_pct.quantize(
                    Decimal('0.00000001'), rounding=ROUND_HALF_EVEN
                ),
                recorded_at=now,
            )

            logger.navpu(
                f'Level {risk_level} ({config.name}): '
                f'NAVPU {current_navpu} → {new_navpu} | '
                f'Return: {return_pct:.6%} | Equity: ${current_equity}'
            )
            return new_navpu

        except Exception as e:
            logger.error(f'NAV sync failed for level {risk_level}: {e}')
            return None

    def sync_all_vaults(self) -> dict[int, Decimal | None]:
        """Sync NAVPU for all 3 ETF vaults. Returns {risk_level: new_navpu}."""
        results = {}
        for level in range(1, 4):
            results[level] = self.sync_strategy_nav(level)
        logger.info(f'NAV sync complete for {sum(1 for v in results.values() if v is not None)}/3 vaults')
        return results


    def process_deposit(self, user_id: str, risk_level: int,
                        amount_eur: Decimal) -> dict:
        """
        Mint units for a client deposit. Zero Alpaca impact.

        Returns dict with deposit details.
        """
        vault = repo.get_vault(risk_level)
        if not vault:
            raise ValueError(f'Vault not found for risk level {risk_level}')

        current_navpu = vault.current_nav_per_unit
        units_minted = (amount_eur / current_navpu).quantize(
            PRECISION_UNITS, rounding=ROUND_HALF_EVEN
        )

        # Update ledger and vault totals
        repo.credit_user_units(user_id, vault.id, units_minted, amount_eur)
        repo.increment_vault_units(vault.id, units_minted)
        tx_id = repo.record_transaction(
            user_id=user_id,
            vault_id=vault.id,
            transaction_type='DEPOSIT',
            fiat_amount=amount_eur,
            units=units_minted,
            nav_at_time=current_navpu,
        )

        logger.deposit(
            f'User {user_id[:8]}... → Level {risk_level} ({vault.name}): '
            f'€{amount_eur} → {units_minted} units @ NAVPU {current_navpu}'
        )

        return {
            'transaction_id': tx_id,
            'vault_name': vault.name,
            'risk_level': risk_level,
            'amount_eur': str(amount_eur),
            'units_minted': str(units_minted),
            'nav_per_unit': str(current_navpu),
        }

    def process_withdrawal(self, user_id: str, risk_level: int,
                           units_to_burn: Decimal) -> dict:
        """
        Burn units for a client redemption and compute fiat payout.

        Returns dict with withdrawal details.
        """
        vault = repo.get_vault(risk_level)
        if not vault:
            raise ValueError(f'Vault not found for risk level {risk_level}')

        # Verify user has enough units
        holding = repo.get_user_holding(user_id, vault.id)
        if not holding or holding.units_balance < units_to_burn:
            available = holding.units_balance if holding else Decimal('0')
            raise ValueError(
                f'Insufficient units. Requested: {units_to_burn}, '
                f'Available: {available}'
            )

        current_navpu = vault.current_nav_per_unit
        payout_eur = (units_to_burn * current_navpu).quantize(
            PRECISION_FIAT, rounding=ROUND_HALF_EVEN
        )

        # Update ledger and vault totals
        repo.debit_user_units(user_id, vault.id, units_to_burn, payout_eur)
        repo.decrement_vault_units(vault.id, units_to_burn)
        tx_id = repo.record_transaction(
            user_id=user_id,
            vault_id=vault.id,
            transaction_type='WITHDRAWAL',
            fiat_amount=payout_eur,
            units=units_to_burn,
            nav_at_time=current_navpu,
        )

        logger.withdraw(
            f'User {user_id[:8]}... ← Level {risk_level} ({vault.name}): '
            f'{units_to_burn} units → €{payout_eur} @ NAVPU {current_navpu}'
        )

        return {
            'transaction_id': tx_id,
            'vault_name': vault.name,
            'risk_level': risk_level,
            'units_burned': str(units_to_burn),
            'payout_eur': str(payout_eur),
            'nav_per_unit': str(current_navpu),
        }

    def get_user_valuation(self, user_id: str, risk_level: int) -> PortfolioValuation | None:
        """Compute live valuation for a user's position in a single vault."""
        vault = repo.get_vault(risk_level)
        if not vault:
            return None

        holding = repo.get_user_holding(user_id, vault.id)
        if not holding:
            return None

        units = holding.units_balance
        navpu = vault.current_nav_per_unit
        cost_basis = holding.total_deposited - holding.total_withdrawn

        current_value = (units * navpu).quantize(PRECISION_FIAT, rounding=ROUND_HALF_EVEN)
        net_pnl = current_value - cost_basis
        return_pct = (
            (net_pnl / cost_basis * Decimal('100'))
            if cost_basis > Decimal('0')
            else Decimal('0')
        )

        return PortfolioValuation(
            vault_name=vault.name,
            risk_level=risk_level,
            units_held=str(units),
            nav_per_unit=str(navpu),
            current_value_eur=str(current_value),
            net_pnl_eur=str(net_pnl),
            return_percentage=f'{return_pct:.2f}%',
        )

    def get_all_user_valuations(self, user_id: str) -> list[PortfolioValuation]:
        """Compute live valuations across all 3 ETF vaults for a user."""
        valuations = []
        for level in range(1, 4):
            val = self.get_user_valuation(user_id, level)
            if val:
                valuations.append(val)
        return valuations



# Singleton engine instance
fund_engine = FundEngine()
