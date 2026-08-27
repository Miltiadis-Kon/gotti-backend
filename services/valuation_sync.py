from decimal import Decimal
from services.fund_engine import fund_engine
from services.logging_service import logger
from config.vault_registry import VAULT_REGISTRY


def sync_all_3_vaults() -> dict[int, Decimal | None]:
    """
    Polls the 3 Alpaca accounts and updates NAVPU across all 3 ETF vaults
    (Boomer Haven ETF, Steady Grind ETF, Diamond Hands ETF).
    """
    try:
        results = fund_engine.sync_all_vaults()
        for lvl, navpu in results.items():
            cfg = VAULT_REGISTRY.get(lvl)
            name = cfg.name if cfg else f"Level {lvl}"
            if navpu is not None:
                print(f"[{name}] Synced -> NAVPU: €{navpu}")
            else:
                print(f"[{name}] Skipped / Unconfigured")
        return results
    except Exception as e:
        logger.error(f"Valuation sync error: {e}")
        print(f"Valuation sync error: {e}")
        return {}


if __name__ == "__main__":
    sync_all_3_vaults()
