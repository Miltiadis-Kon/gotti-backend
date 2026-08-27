import os
import uuid
from decimal import Decimal
from config.settings import settings
from config.vault_registry import VAULT_REGISTRY
from services.logging_service import logger


def seed_3_etf_vaults() -> None:
    """
    Initializes and seeds the 3 Master ETF Vault records into the database
    (Boomer Haven ETF, Steady Grind ETF, Diamond Hands ETF).
    Supports project connection pool / repository.
    """
    try:
        from db.connection import pool
        from db.repository import repo
        
        pool.initialize()
        repo.init_schema()

        for level, cfg in VAULT_REGISTRY.items():
            existing = repo.get_vault(level)
            if not existing:
                vault_id = str(uuid.uuid4())
                repo.upsert_vault(
                    vault_id=vault_id,
                    risk_level=level,
                    name=cfg.name,
                    symbol=cfg.symbol,
                    annual_fee=Decimal(str(cfg.annual_fee)),
                )
                logger.info(f"Successfully seeded Level {level}: {cfg.name} ({cfg.symbol})")
            else:
                logger.info(f"Vault already exists: Level {level} — {cfg.name}")

        print("Successfully seeded 3 Master ETF Vaults.")
    except Exception as e:
        print(f"Error seeding vaults: {e}")


if __name__ == "__main__":
    seed_3_etf_vaults()
