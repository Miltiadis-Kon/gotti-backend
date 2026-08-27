from fastapi import APIRouter, HTTPException
from services.fund_engine import fund_engine
from services.risk_classifier import risk_classifier
from services.alpaca_client import alpaca_factory
from config.vault_registry import VAULT_REGISTRY
from config.settings import settings
from db.repository import repo

router = APIRouter(prefix='/admin', tags=['Admin'])


@router.post('/sync-nav')
def sync_nav():
    """Manually trigger NAVPU sync for all vaults."""
    results = fund_engine.sync_all_vaults()
    return {
        level: str(navpu) if navpu else 'skipped'
        for level, navpu in results.items()
    }


@router.post('/classify-signals')
def classify_signals():
    """Run risk classification on all recent signals."""
    assignments = risk_classifier.classify_all_pending()
    return [
        {
            'ticker': a.ticker,
            'risk_level': a.assigned_risk_level,
            'score': a.evaluation_score,
            'signal': a.signal_position,
        }
        for a in assignments
    ]


@router.get('/vault-status')
def vault_status():
    """Detailed vault status including broker equity."""
    status = []
    for level, config in VAULT_REGISTRY.items():
        vault = repo.get_vault(level)
        entry = {
            'risk_level': level,
            'name': config.name,
            'symbol': config.symbol,
            'nav_per_unit': str(vault.current_nav_per_unit) if vault else 'N/A',
            'total_units': str(vault.total_units_outstanding) if vault else 'N/A',
            'alpaca_configured': bool(config.api_key and config.secret_key),
            'broker_equity': None,
        }
        # Try to fetch live equity if Alpaca is configured
        if config.api_key and config.secret_key:
            try:
                entry['broker_equity'] = str(
                    alpaca_factory.get_account_equity(level)
                )
            except Exception as e:
                entry['broker_equity'] = f'Error: {e}'
        status.append(entry)
    return status


@router.get('/config')
def get_system_configs():
    """Retrieve all system credentials and configurations stored in MySQL."""
    configs = repo.get_all_configs()
    # Mask sensitive secrets in response for safety
    masked = {}
    for k, v in configs.items():
        if any(secret_term in k.lower() for secret_term in ['secret', 'key', 'password', 'token']) and len(v) > 6:
            masked[k] = v[:3] + '...' + v[-3:]
        else:
            masked[k] = v
    return {
        "count": len(configs),
        "configs": masked
    }


@router.post('/config')
def update_system_configs(payload: dict[str, str]):
    """
    Update system configurations in the MySQL system_config table
    and dynamically reload active memory settings.
    """
    if not payload:
        raise HTTPException(status_code=400, detail="Empty configuration payload")

    repo.bulk_upsert_configs(payload)
    settings.load_from_db()
    return {
        "status": "success",
        "updated_keys": list(payload.keys()),
        "message": f"Successfully updated {len(payload)} configurations in MySQL database"
    }
