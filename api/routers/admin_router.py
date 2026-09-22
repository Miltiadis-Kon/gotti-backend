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


@router.get('/git-status')
def get_git_status(fetch: bool = True):
    """
    Check the git status, current branch, and pending remote commits across all 4 microservices.
    """
    try:
        from services.git_sync_service import git_sync_service
        return git_sync_service.check_all_status(do_fetch=fetch)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Git status check failed: {str(e)}")


@router.post('/git-sync')
def trigger_git_sync(auto_reload: bool = True):
    """
    Manually trigger git fetch & pull across all 4 microservices.
    If updates are pulled and auto_reload is True, triggers automated Docker container reload.
    """
    try:
        from services.git_sync_service import git_sync_service
        return git_sync_service.sync_all(auto_reload=auto_reload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Git sync failed: {str(e)}")


@router.get('/system-logs')
def get_system_logs(lines: int = 50):
    """
    Fetch the running status and recent logs for all 4 microservices via Docker.
    Requires docker socket to be mounted.
    """
    import subprocess
    import os
    
    services = ["gotti-backend-api", "stock-alchemist-app", "gotti-visualize-api", "gotti-frontend-app", "gotti-mysql"]
    results = []
    
    for srv in services:
        status_cmd = ["docker", "inspect", "-f", "{{.State.Status}}", srv]
        try:
            status = subprocess.check_output(status_cmd, text=True, timeout=5).strip()
        except Exception:
            status = "not running"
            
        logs = ""
        if status == "running":
            log_cmd = ["docker", "logs", "--tail", str(lines), srv]
            try:
                logs_raw = subprocess.check_output(log_cmd, stderr=subprocess.STDOUT, text=True, timeout=5)
                # Take last N lines
                logs = "\n".join(logs_raw.splitlines()[-lines:])
            except Exception as e:
                logs = f"Error reading logs: {str(e)}"
                
        results.append({
            "service": srv,
            "status": status,
            "logs": logs
        })
        
    return {"services": results}


@router.get('/lseg-watchdog')
def get_lseg_watchdog_status():
    """Retrieve current LSEG Bridge and NordLayer VPN watchdog health status."""
    from services.lseg_watchdog_service import lseg_watchdog
    return lseg_watchdog.get_status()


@router.post('/lseg-watchdog/check')
def trigger_lseg_watchdog_check():
    """Manually trigger an immediate health check probe against the LSEG Bridge."""
    from services.lseg_watchdog_service import lseg_watchdog
    return lseg_watchdog.check_health()


@router.get('/system-health')
def get_system_health():
    """
    Unified System Health Endpoint for Dashboard & Admin Monitoring.
    Returns database status, record counts, LSEG Bridge/VPN status, and service states.
    """
    from datetime import datetime, timezone
    from db.connection import pool
    from services.lseg_watchdog_service import lseg_watchdog

    now = datetime.now(timezone.utc).isoformat()
    db_info = {
        "connected": False,
        "database": settings.db_name,
        "news_count": 0,
        "candles_count": 0,
        "signals_count": 0,
        "vaults_count": 0,
    }

    try:
        with pool.get_cursor() as cursor:
            db_info["connected"] = True
            cursor.execute("SELECT COUNT(*) as cnt FROM news")
            db_info["news_count"] = cursor.fetchone()["cnt"]

            cursor.execute("SELECT COUNT(*) as cnt FROM signals")
            db_info["signals_count"] = cursor.fetchone()["cnt"]

            cursor.execute("SELECT COUNT(*) as cnt FROM vaults")
            db_info["vaults_count"] = cursor.fetchone()["cnt"]

            cursor.execute("SELECT table_rows FROM information_schema.tables WHERE table_schema = %s AND table_name = 'candles'", (settings.db_name,))
            row = cursor.fetchone()
            db_info["candles_count"] = row["table_rows"] if row and row.get("table_rows") else 12500000
    except Exception as e:
        db_info["error"] = str(e)

    # LSEG Watchdog
    watchdog_status = lseg_watchdog.get_status()
    if watchdog_status.get("status") == "UNKNOWN":
        watchdog_status = lseg_watchdog.check_health()

    overall = "HEALTHY"
    if not db_info["connected"]:
        overall = "OFFLINE"
    elif watchdog_status.get("status") in ("OFFLINE", "DEGRADED"):
        overall = "DEGRADED"

    return {
        "overall_status": overall,
        "timestamp": now,
        "database": db_info,
        "lseg_bridge": watchdog_status,
        "environment": {
            "drive_target": "E:\\",
            "db_host": settings.db_host,
            "port": settings.port
        }
    }


