import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from db.connection import pool
from models.vault import Vault, NavSnapshot
from models.ledger import UserHolding, Transaction
from models.signal import Signal, Evaluation, TickerRiskAssignment
from models.client import UserProfile, SubAccountModel, TransactionRecordModel
from models.order import OrderDataModel


class Repository:
    """Centralized database access for all Module 4 operations and Client Services."""

    # ── Database Initialization ──────────────────────────────────────

    def init_schema(self, schema_sql_path: str = "db_init.sql") -> None:
        """Execute table creation DDL statements from db_init.sql."""
        try:
            with open(schema_sql_path, "r", encoding="utf-8") as f:
                content = f.read()

            statements = [s.strip() for s in content.split(";") if s.strip()]
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                for stmt in statements:
                    if stmt.upper().startswith("USE "):
                        continue
                    cursor.execute(stmt)
                cursor.close()
        except Exception as e:
            from services.logging_service import logger
            logger.error(f"Error running init_schema: {e}")

    # ── Vault Operations ─────────────────────────────────────────────

    def get_vault(self, risk_level: int) -> Vault | None:
        """Fetch a single vault by risk level."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM vaults WHERE risk_level = %s',
                (risk_level,)
            )
            row = cursor.fetchone()
            return Vault(**row) if row else None

    def get_all_vaults(self) -> list[Vault]:
        """Fetch all 5 vaults ordered by risk level."""
        with pool.get_cursor() as cursor:
            cursor.execute('SELECT * FROM vaults ORDER BY risk_level ASC')
            rows = cursor.fetchall()
            return [Vault(**row) for row in rows]

    def upsert_vault(self, vault_id: str, risk_level: int, name: str,
                     symbol: str, annual_fee: Decimal) -> None:
        """Insert or update a vault definition."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''INSERT INTO vaults (id, risk_level, name, symbol, annual_fee)
                   VALUES (%s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE name = VALUES(name),
                   symbol = VALUES(symbol), annual_fee = VALUES(annual_fee)''',
                (vault_id, risk_level, name, symbol, str(annual_fee))
            )

    def update_vault_navpu(self, vault_id: str, new_navpu: Decimal,
                           last_synced_at: datetime) -> None:
        """Update the current NAVPU for a vault."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''UPDATE vaults
                   SET current_nav_per_unit = %s, last_synced_at = %s
                   WHERE id = %s''',
                (str(new_navpu), last_synced_at, vault_id)
            )

    def increment_vault_units(self, vault_id: str, units: Decimal) -> None:
        """Add units to the vault's total outstanding."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''UPDATE vaults
                   SET total_units_outstanding = total_units_outstanding + %s
                   WHERE id = %s''',
                (str(units), vault_id)
            )

    def decrement_vault_units(self, vault_id: str, units: Decimal) -> None:
        """Subtract units from the vault's total outstanding."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''UPDATE vaults
                   SET total_units_outstanding = total_units_outstanding - %s
                   WHERE id = %s''',
                (str(units), vault_id)
            )

    # ── NAV Snapshot Operations ──────────────────────────────────────

    def record_nav_snapshot(self, vault_id: str, nav_per_unit: Decimal,
                            broker_equity: Decimal, strategy_return_pct: Decimal | None,
                            recorded_at: datetime) -> None:
        """Record a point-in-time NAVPU snapshot."""
        snapshot_id = str(uuid.uuid4())
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''INSERT INTO nav_snapshots
                   (id, vault_id, nav_per_unit, broker_equity, strategy_return_pct, recorded_at)
                   VALUES (%s, %s, %s, %s, %s, %s)''',
                (snapshot_id, vault_id, str(nav_per_unit), str(broker_equity),
                 str(strategy_return_pct) if strategy_return_pct is not None else None,
                 recorded_at)
            )

    def get_nav_history(self, vault_id: str, limit: int = 100) -> list[NavSnapshot]:
        """Fetch NAVPU history for a vault, most recent first."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''SELECT * FROM nav_snapshots
                   WHERE vault_id = %s
                   ORDER BY recorded_at DESC
                   LIMIT %s''',
                (vault_id, limit)
            )
            rows = cursor.fetchall()
            return [NavSnapshot(**row) for row in rows]

    # ── User Holding Operations (Ledger Layer) ───────────────────────

    def get_user_holding(self, user_id: str, vault_id: str) -> UserHolding | None:
        """Fetch a user's holding in a specific vault."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM user_holdings WHERE user_id = %s AND vault_id = %s',
                (user_id, vault_id)
            )
            row = cursor.fetchone()
            return UserHolding(**row) if row else None

    def get_all_user_holdings(self, user_id: str) -> list[UserHolding]:
        """Fetch all holdings for a user across all vaults."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM user_holdings WHERE user_id = %s',
                (user_id,)
            )
            rows = cursor.fetchall()
            return [UserHolding(**row) for row in rows]

    def credit_user_units(self, user_id: str, vault_id: str,
                          units: Decimal, fiat_amount: Decimal) -> None:
        """Add units to a user's holding (deposit). Creates holding if needed."""
        holding_id = str(uuid.uuid4())
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''INSERT INTO user_holdings (id, user_id, vault_id, units_balance, total_deposited)
                   VALUES (%s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE
                   units_balance = units_balance + VALUES(units_balance),
                   total_deposited = total_deposited + VALUES(total_deposited)''',
                (holding_id, user_id, vault_id, str(units), str(fiat_amount))
            )

    def debit_user_units(self, user_id: str, vault_id: str,
                         units: Decimal, fiat_payout: Decimal) -> None:
        """Remove units from a user's holding (withdrawal)."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''UPDATE user_holdings
                   SET units_balance = units_balance - %s,
                       total_withdrawn = total_withdrawn + %s
                   WHERE user_id = %s AND vault_id = %s''',
                (str(units), str(fiat_payout), user_id, vault_id)
            )

    # ── Transaction Operations ───────────────────────────────────────

    def record_transaction(self, user_id: str, vault_id: str,
                           transaction_type: str, fiat_amount: Decimal,
                           units: Decimal, nav_at_time: Decimal) -> str:
        """Log a deposit or withdrawal transaction. Returns the transaction ID."""
        tx_id = str(uuid.uuid4())
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''INSERT INTO transactions
                   (id, user_id, vault_id, transaction_type, fiat_amount, units, nav_at_time)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                (tx_id, user_id, vault_id, transaction_type,
                 str(fiat_amount), str(units), str(nav_at_time))
            )
        return tx_id

    def get_user_transactions(self, user_id: str, limit: int = 50) -> list[Transaction]:
        """Fetch transaction history for a user, most recent first."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''SELECT * FROM transactions
                   WHERE user_id = %s
                   ORDER BY created_at DESC
                   LIMIT %s''',
                (user_id, limit)
            )
            rows = cursor.fetchall()
            return [Transaction(**row) for row in rows]

    # ── Signal Operations (reads from stock-alchemist tables) ────────

    def get_latest_signals(self, limit: int = 50) -> list[Signal]:
        """Read recent signals from stock-alchemist's signals table."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''SELECT signal_id, ticker, signal_position, sentiment,
                          signal_date, created_at
                   FROM signals
                   ORDER BY created_at DESC
                   LIMIT %s''',
                (limit,)
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                sent = row.get('sentiment')
                if isinstance(sent, str):
                    try:
                        sent = json.loads(sent)
                    except (json.JSONDecodeError, TypeError):
                        sent = None
                row['sentiment'] = sent
                results.append(Signal(**row))
            return results

    def get_evaluation(self, ticker: str) -> Evaluation | None:
        """Read the latest fundamental evaluation for a ticker from stock-alchemist."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''SELECT ticker, data, created_at
                   FROM fundamental_analysis
                   WHERE ticker = %s
                   ORDER BY created_at DESC
                   LIMIT 1''',
                (ticker,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            data = row.get('data')
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    data = {}
            row['data'] = data
            return Evaluation(**row)

    # ── Risk Assignment Operations ───────────────────────────────────

    def save_risk_assignment(self, ticker: str, risk_level: int,
                             score: float | None, signal_position: str | None) -> str:
        """Save a ticker's risk level assignment."""
        assignment_id = str(uuid.uuid4())
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''INSERT INTO ticker_risk_assignments
                   (id, ticker, assigned_risk_level, evaluation_score, signal_position)
                   VALUES (%s, %s, %s, %s, %s)''',
                (assignment_id, ticker, risk_level, score, signal_position)
            )
        return assignment_id

    def get_risk_assignments(self, risk_level: int | None = None,
                             limit: int = 50) -> list[TickerRiskAssignment]:
        """Fetch risk assignments, optionally filtered by level."""
        with pool.get_cursor() as cursor:
            if risk_level is not None:
                cursor.execute(
                    '''SELECT * FROM ticker_risk_assignments
                       WHERE assigned_risk_level = %s
                       ORDER BY assigned_at DESC LIMIT %s''',
                    (risk_level, limit)
                )
            else:
                cursor.execute(
                    '''SELECT * FROM ticker_risk_assignments
                       ORDER BY assigned_at DESC LIMIT %s''',
                    (limit,)
                )
            rows = cursor.fetchall()
            return [TickerRiskAssignment(**row) for row in rows]

    # ── Client Registry & User Profile Operations ────────────────────

    def get_user(self, user_id: str) -> UserProfile | None:
        """Fetch user profile by user_id."""
        with pool.get_cursor() as cursor:
            cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_user_profile(row)

    def get_user_by_email(self, email: str) -> UserProfile | None:
        """Fetch user profile by email."""
        with pool.get_cursor() as cursor:
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_user_profile(row)

    def create_user(self, user_id: str, email: str, password_hash: str | None = None,
                    name: str | None = None, risk_level: int = 3, risk_score: int | None = None,
                    strategy_name: str = "Steady Grind ETF", active_sub_account_id: str = "",
                    total_cash_balance: float = 0.0, answers: dict | None = None) -> UserProfile:
        """Create a new user profile record."""
        answers_json = json.dumps(answers) if answers else None
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''INSERT INTO users (id, email, password_hash, name, risk_level, risk_score,
                                      strategy_name, is_logged_in, active_sub_account_id,
                                      total_cash_balance, questionnaire_answers)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s, %s)''',
                (user_id, email, password_hash, name, risk_level, risk_score,
                 strategy_name, active_sub_account_id, total_cash_balance, answers_json)
            )
        return self.get_user(user_id)  # type: ignore

    def update_user(self, user_id: str, **kwargs) -> UserProfile | None:
        """Update fields of an existing user profile."""
        if not kwargs:
            return self.get_user(user_id)

        field_mapping = {
            "riskLevel": "risk_level",
            "riskScore": "risk_score",
            "strategyName": "strategy_name",
            "isLoggedIn": "is_logged_in",
            "activeSubAccountId": "active_sub_account_id",
            "totalCashBalance": "total_cash_balance",
            "answers": "questionnaire_answers"
        }

        set_clauses = []
        values = []
        for k, v in kwargs.items():
            db_col = field_mapping.get(k, k)
            if db_col == "questionnaire_answers" and isinstance(v, dict):
                v = json.dumps(v)
            set_clauses.append(f"{db_col} = %s")
            values.append(v)

        values.append(user_id)
        sql_query = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = %s"

        with pool.get_cursor() as cursor:
            cursor.execute(sql_query, tuple(values))

        return self.get_user(user_id)

    def _row_to_user_profile(self, row: dict) -> UserProfile:
        answers = row.get("questionnaire_answers")
        if isinstance(answers, str):
            try:
                answers = json.loads(answers)
            except Exception:
                answers = None

        return UserProfile(
            id=row["id"],
            email=row["email"],
            riskLevel=row["risk_level"],
            riskScore=row.get("risk_score"),
            strategyName=row["strategy_name"],
            isLoggedIn=bool(row["is_logged_in"]),
            activeSubAccountId=row.get("active_sub_account_id") or "",
            totalCashBalance=float(row.get("total_cash_balance") or 0.0),
            answers=answers,
            createdAt=row["created_at"].isoformat() if isinstance(row.get("created_at"), datetime) else str(row.get("created_at") or ""),
            updatedAt=row["updated_at"].isoformat() if isinstance(row.get("updated_at"), datetime) else str(row.get("updated_at") or "")
        )

    # ── Client Sub-Account Operations ────────────────────────────────

    def get_sub_accounts(self, user_id: str) -> list[SubAccountModel]:
        """Fetch all segregated sub-accounts for a user ordered by risk_level."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM sub_accounts WHERE user_id = %s ORDER BY risk_level ASC',
                (user_id,)
            )
            rows = cursor.fetchall()
            return [self._row_to_sub_account(r) for r in rows]

    def get_sub_account(self, sub_account_id: str) -> SubAccountModel | None:
        """Fetch a single sub-account by its ID."""
        with pool.get_cursor() as cursor:
            cursor.execute('SELECT * FROM sub_accounts WHERE id = %s', (sub_account_id,))
            row = cursor.fetchone()
            return self._row_to_sub_account(row) if row else None

    def get_sub_account_by_level(self, user_id: str, risk_level: int) -> SubAccountModel | None:
        """Fetch a sub-account by user_id and risk_level."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM sub_accounts WHERE user_id = %s AND risk_level = %s',
                (user_id, risk_level)
            )
            row = cursor.fetchone()
            return self._row_to_sub_account(row) if row else None

    def create_sub_account(self, sub_account_id: str, user_id: str, name: str,
                           risk_level: int, strategy_name: str, allocated_capital: float,
                           current_value: float, cash_balance: float, invested_amount: float,
                           pnl: float, pnl_percentage: float, status: str = "active",
                           holdings_count: int = 0, description: str | None = None,
                           created_at: str | None = None) -> SubAccountModel:
        """Create a new segregated sub-account."""
        created_str = created_at or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''INSERT INTO sub_accounts
                   (id, user_id, name, risk_level, strategy_name, allocated_capital,
                    current_value, cash_balance, invested_amount, pnl, pnl_percentage,
                    status, holdings_count, description, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                (sub_account_id, user_id, name, risk_level, strategy_name,
                 allocated_capital, current_value, cash_balance, invested_amount,
                 pnl, pnl_percentage, status, holdings_count, description, created_str)
            )
        return self.get_sub_account(sub_account_id)  # type: ignore

    def update_sub_account(self, sub_account_id: str, **kwargs) -> SubAccountModel | None:
        """Update an existing sub-account."""
        if not kwargs:
            return self.get_sub_account(sub_account_id)

        field_mapping = {
            "strategyName": "strategy_name",
            "allocatedCapital": "allocated_capital",
            "currentValue": "current_value",
            "cashBalance": "cash_balance",
            "investedAmount": "invested_amount",
            "pnlPercentage": "pnl_percentage",
            "holdingsCount": "holdings_count",
            "riskLevel": "risk_level"
        }

        set_clauses = []
        values = []
        for k, v in kwargs.items():
            db_col = field_mapping.get(k, k)
            set_clauses.append(f"{db_col} = %s")
            values.append(v)

        values.append(sub_account_id)
        sql_query = f"UPDATE sub_accounts SET {', '.join(set_clauses)} WHERE id = %s"

        with pool.get_cursor() as cursor:
            cursor.execute(sql_query, tuple(values))

        return self.get_sub_account(sub_account_id)

    def delete_sub_account(self, sub_account_id: str) -> bool:
        """Delete a sub-account."""
        with pool.get_cursor() as cursor:
            cursor.execute('DELETE FROM sub_accounts WHERE id = %s', (sub_account_id,))
            return cursor.rowcount > 0

    def _row_to_sub_account(self, row: dict) -> SubAccountModel:
        return SubAccountModel(
            id=row["id"],
            name=row["name"],
            riskLevel=row["risk_level"],
            strategyName=row["strategy_name"],
            allocatedCapital=float(row.get("allocated_capital") or 0.0),
            currentValue=float(row.get("current_value") or 0.0),
            cashBalance=float(row.get("cash_balance") or 0.0),
            investedAmount=float(row.get("invested_amount") or 0.0),
            pnl=float(row.get("pnl") or 0.0),
            pnlPercentage=float(row.get("pnl_percentage") or 0.0),
            status=row.get("status") or "active",
            createdAt=str(row.get("created_at") or ""),
            holdingsCount=int(row.get("holdings_count") or 0),
            description=row.get("description")
        )

    # ── Client Transaction Records ───────────────────────────────────

    def record_client_transaction(self, tx_id: str, user_id: str, sub_account_id: str,
                                  sub_account_name: str, strategy_name: str, amount: float,
                                  tx_type: str, status: str = "Fulfilled",
                                  method: str = "Instant Card (Stripe)", notes: str | None = None,
                                  tx_date: str | None = None, timestamp: int | None = None) -> TransactionRecordModel:
        """Record a financial ledger transaction in client_transactions."""
        now_date = tx_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now_ts = timestamp or int(datetime.now(timezone.utc).timestamp() * 1000)

        with pool.get_cursor() as cursor:
            cursor.execute(
                '''INSERT INTO client_transactions
                   (id, user_id, sub_account_id, sub_account_name, strategy_name,
                    amount, type, status, method, notes, date, timestamp)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                (tx_id, user_id, sub_account_id, sub_account_name, strategy_name,
                 amount, tx_type, status, method, notes, now_date, now_ts)
            )

        return TransactionRecordModel(
            id=tx_id,
            subAccountId=sub_account_id,
            subAccountName=sub_account_name,
            strategyName=strategy_name,
            amount=amount,
            type=tx_type,  # type: ignore
            status=status,  # type: ignore
            method=method,
            date=now_date,
            timestamp=now_ts,
            notes=notes
        )

    def get_client_transactions(self, user_id: str, sub_account_id: str | None = None,
                                limit: int = 100) -> list[TransactionRecordModel]:
        """Fetch client transactions, optionally filtered by sub-account."""
        with pool.get_cursor() as cursor:
            if sub_account_id:
                cursor.execute(
                    '''SELECT * FROM client_transactions
                       WHERE user_id = %s AND sub_account_id = %s
                       ORDER BY timestamp DESC LIMIT %s''',
                    (user_id, sub_account_id, limit)
                )
            else:
                cursor.execute(
                    '''SELECT * FROM client_transactions
                       WHERE user_id = %s
                       ORDER BY timestamp DESC LIMIT %s''',
                    (user_id, limit)
                )
            rows = cursor.fetchall()
            return [
                TransactionRecordModel(
                    id=r["id"],
                    subAccountId=r["sub_account_id"],
                    subAccountName=r["sub_account_name"],
                    strategyName=r["strategy_name"],
                    amount=float(r["amount"]),
                    type=r["type"],
                    status=r["status"],
                    method=r["method"],
                    date=r["date"],
                    timestamp=int(r["timestamp"]),
                    notes=r.get("notes")
                )
                for r in rows
            ]

    # ── Orders History Operations ────────────────────────────────────

    def get_orders(self, limit: int = 100) -> list[OrderDataModel]:
        """Fetch trade order history."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM orders ORDER BY id DESC LIMIT %s',
                (limit,)
            )
            rows = cursor.fetchall()
            return [
                OrderDataModel(
                    id=r["id"],
                    date=r["order_date"],
                    symbol=r["symbol"],
                    name=r["name"],
                    status=r["status"],
                    buyPrice=float(r["buy_price"]) if r["buy_price"] is not None else "-",
                    sellPrice=float(r["sell_price"]) if r["sell_price"] is not None else "-",
                    profit=float(r["profit"]) if r["profit"] is not None else "-",
                    orderAmount=float(r["order_amount"]),
                    totalAmount=float(r["total_amount"]),
                    type=r["order_type"]
                )
                for r in rows
            ]

    def create_order(self, order_date: str, symbol: str, name: str, status: str,
                     buy_price: float | None, sell_price: float | None, profit: float | None,
                     order_amount: float, total_amount: float, order_type: str) -> int:
        """Insert a trade order into orders."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''INSERT INTO orders
                   (order_date, symbol, name, status, buy_price, sell_price,
                    profit, order_amount, total_amount, order_type)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                (order_date, symbol, name, status, buy_price, sell_price,
                 profit, order_amount, total_amount, order_type)
            )
            return cursor.lastrowid

    # ── System Configuration Operations (Shared Across All 4 Projects) ──

    def get_config(self, config_key: str) -> str | None:
        """Fetch a configuration value from system_config table."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                'SELECT config_value FROM system_config WHERE config_key = %s',
                (config_key,)
            )
            row = cursor.fetchone()
            return row["config_value"] if row else None

    def set_config(self, config_key: str, config_value: str,
                   description: str | None = None) -> None:
        """Insert or update a configuration key in system_config table."""
        with pool.get_cursor() as cursor:
            cursor.execute(
                '''INSERT INTO system_config (config_key, config_value, description)
                   VALUES (%s, %s, %s)
                   ON DUPLICATE KEY UPDATE config_value = VALUES(config_value),
                   description = COALESCE(VALUES(description), description)''',
                (config_key, config_value, description)
            )

    def get_all_configs(self) -> dict[str, str]:
        """Fetch all system configuration key-value pairs from MySQL."""
        with pool.get_cursor() as cursor:
            cursor.execute('SELECT config_key, config_value FROM system_config')
            rows = cursor.fetchall()
            return {r["config_key"]: r["config_value"] for r in rows}

    def bulk_upsert_configs(self, configs: dict[str, str]) -> None:
        """Bulk update system configurations."""
        with pool.get_cursor() as cursor:
            for key, val in configs.items():
                cursor.execute(
                    '''INSERT INTO system_config (config_key, config_value)
                       VALUES (%s, %s)
                       ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)''',
                    (key, str(val))
                )


# Singleton repository instance
repo = Repository()
