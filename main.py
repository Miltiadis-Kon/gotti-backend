import asyncio
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from config.vault_registry import VAULT_REGISTRY
from db.connection import pool
from db.repository import repo
from services.logging_service import logger
from services.client_service import client_service
from tasks.scheduler import task_scheduler
from ws_channels.signal_listener import SignalListener
from ws_channels.trade_publisher import trade_publisher

# Import routers
from api.routers.vault_router import router as vault_router
from api.routers.holdings_router import router as holdings_router
from api.routers.transaction_router import router as transaction_router
from api.routers.signals_router import router as signals_router
from api.routers.admin_router import router as admin_router
from api.routers.client_router import router as client_router
from api.routers.subaccount_router import router as subaccount_router
from api.routers.stock_router import router as stock_router


def _seed_vaults() -> None:
    """Ensure all 3 Master ETF vault records exist in the database."""

    from decimal import Decimal
    for level, config in VAULT_REGISTRY.items():
        existing = repo.get_vault(level)
        if not existing:
            vault_id = str(uuid.uuid4())
            repo.upsert_vault(
                vault_id=vault_id,
                risk_level=level,
                name=config.name,
                symbol=config.symbol,
                annual_fee=Decimal(str(config.annual_fee)),
            )
            logger.info(f"Seeded vault: Level {level} — {config.name} (id={vault_id})")
        else:
            logger.info(f"Vault exists: Level {level} — {config.name}")


async def _on_signal_received(signal_data: dict) -> None:
    """Callback: forward classified signals with hierarchical trading permissions to the trade publisher."""
    await trade_publisher.publish_trade_command(
        ticker=signal_data["ticker"],
        risk_level=signal_data["risk_level"],
        signal_position=signal_data["signal_position"],
        evaluation_score=signal_data.get("evaluation_score"),
        eligible_levels=signal_data.get("eligible_levels"),
        eligible_vaults=signal_data.get("eligible_vaults"),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # ── Startup ──────────────────────────────────────────────
    logger.startup("Gotti Backend — Module 4 Core Engine starting...")

    # 1. Initialize database connection pool
    try:
        pool.initialize()
        logger.startup("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Database connection pool initialization warning: {e}")

    # 2. Initialize database schema & seed demo tables
    try:
        repo.init_schema()
        settings.load_from_db()
        logger.startup("Database schema verified and dynamic credentials loaded from MySQL")
    except Exception as e:
        logger.error(f"Database schema init warning: {e}")

    # 3. Seed vault records and demo client profiles
    try:
        _seed_vaults()
        client_service.seed_initial_demo_data()
        logger.startup("Vaults and Client seed data verified")
    except Exception as e:
        logger.error(f"Seed data warning: {e}")

    # 4. Start trade publisher (WebSocket server for gotti-visualize)
    try:
        await trade_publisher.start()
    except Exception as e:
        logger.error(f"Trade publisher startup warning: {e}")

    # 5. Start signal listener (WebSocket client for stock-alchemist)
    signal_listener = SignalListener(on_signal_callback=_on_signal_received)
    listener_task = asyncio.create_task(signal_listener.start())

    # 6. Start periodic task scheduler
    try:
        task_scheduler.start()
    except Exception as e:
        logger.error(f"Scheduler startup warning: {e}")

    logger.startup(
        f"Module 4 ready — API on port {settings.port}, "
        f"Trade WS on port {settings.trade_ws_port}"
    )

    yield  # ── App is running ──

    # ── Shutdown ─────────────────────────────────────────────
    logger.shutdown("Module 4 shutting down...")
    try:
        task_scheduler.stop()
    except Exception:
        pass
    try:
        signal_listener.stop()
        listener_task.cancel()
    except Exception:
        pass
    try:
        await trade_publisher.stop()
    except Exception:
        pass
    try:
        pool.close()
    except Exception:
        pass
    logger.shutdown("Shutdown complete")


# ── Create FastAPI app ───────────────────────────────────────
app = FastAPI(
    title="Gotti Backend — Module 4",
    description="Central Core Engine connecting stock-alchemist, gotti-visualize, and gotti-frontend",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS middleware ──────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount routers ────────────────────────────────────────────
# ETF Vault & Ledger endpoints (Frontend ETF contracts)
app.include_router(vault_router, prefix="/api/etf")
app.include_router(holdings_router, prefix="/api/etf")
app.include_router(transaction_router, prefix="/api/etf")

# Client Registry, Sub-Accounts, Funds, and Orders
app.include_router(client_router, prefix="/api")
app.include_router(subaccount_router, prefix="/api")
app.include_router(stock_router, prefix="/api")

# Signals & Admin
app.include_router(signals_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    from datetime import datetime, timezone
    return {
        "status": "ok",
        "service": "gotti-backend-m4",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
