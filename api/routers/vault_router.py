from fastapi import APIRouter, HTTPException
from db.repository import repo
from config.vault_registry import VAULT_REGISTRY

router = APIRouter(prefix='/vaults', tags=['Vaults'])


@router.get('/')
def get_all_vaults():
    """Return all 3 Master ETF vaults with current NAVPU."""

    vaults = repo.get_all_vaults()
    result = []
    for vault in vaults:
        config = VAULT_REGISTRY.get(vault.risk_level)
        result.append({
            'id': vault.id,
            'risk_level': vault.risk_level,
            'name': vault.name,
            'symbol': vault.symbol,
            'description': config.description if config else '',
            'nav_per_unit': str(vault.current_nav_per_unit),
            'total_units': str(vault.total_units_outstanding),
            'annual_fee': str(vault.annual_fee),
            'last_synced_at': vault.last_synced_at.isoformat() if vault.last_synced_at else None,
        })
    return result


@router.get('/{risk_level}')
def get_vault(risk_level: int):
    """Return a single vault by risk level."""
    vault = repo.get_vault(risk_level)
    if not vault:
        raise HTTPException(status_code=404, detail=f'Vault not found for level {risk_level}')
    config = VAULT_REGISTRY.get(risk_level)
    return {
        'id': vault.id,
        'risk_level': vault.risk_level,
        'name': vault.name,
        'symbol': vault.symbol,
        'description': config.description if config else '',
        'nav_per_unit': str(vault.current_nav_per_unit),
        'total_units': str(vault.total_units_outstanding),
        'annual_fee': str(vault.annual_fee),
        'last_synced_at': vault.last_synced_at.isoformat() if vault.last_synced_at else None,
    }


@router.get('/{risk_level}/performance')
def get_vault_performance(risk_level: int, limit: int = 100):
    """Return NAVPU history snapshots for a vault."""
    vault = repo.get_vault(risk_level)
    if not vault:
        raise HTTPException(status_code=404, detail=f'Vault not found for level {risk_level}')
    snapshots = repo.get_nav_history(vault.id, limit=limit)
    return [
        {
            'nav_per_unit': str(s.nav_per_unit),
            'broker_equity': str(s.broker_equity),
            'strategy_return_pct': str(s.strategy_return_pct) if s.strategy_return_pct else None,
            'recorded_at': s.recorded_at.isoformat(),
        }
        for s in snapshots
    ]
