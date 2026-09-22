"""
Candles Router
==============
REST endpoints for multi-timeframe candlestick collection, sector universe inspection,
cross-evaluation with the available_tickers database whitelist, and job tracking.
"""

from typing import Optional, List
from fastapi import APIRouter, Query, BackgroundTasks, HTTPException
from pydantic import BaseModel

from services.candle_collection_service import candle_collection_service, SECTOR_UNIVERSE_50
from db.repository import repo

router = APIRouter(prefix="/candles", tags=["Candlesticks & Market Data"])


class BackfillTriggerRequest(BaseModel):
    sectors: Optional[List[str]] = None
    db_only: bool = True
    delay_seconds: float = 1.0


class SingleCollectRequest(BaseModel):
    sector: Optional[str] = "General Diversified"
    exchange: Optional[str] = None


@router.get("/sectors")
def list_sectors():
    """List all supported sectors and total stock universe targets."""
    sectors_info = []
    for s, stocks in SECTOR_UNIVERSE_50.items():
        sectors_info.append({
            "sector": s,
            "target_stocks_count": len(stocks),
            "sample_stocks": stocks[:5]
        })
    return {
        "total_sectors": len(sectors_info),
        "sectors": sectors_info
    }


@router.get("/evaluation-list")
def get_evaluation_list():
    """
    Fetch the list of top 50 stocks under each sector and cross-evaluate
    against the available_tickers database whitelist table.
    Use this to review and evaluate before running candlestick collection.
    """
    return candle_collection_service.get_cross_evaluated_stock_list()


@router.get("/history/{ticker}")
def get_candle_history(
    ticker: str,
    timeframe: str = Query("5 min", description="Timeframe: '5 min', '1 hour', or '1 day'"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(500, description="Max candle records to return"),
):
    """Retrieve stored candlestick bars for a ticker from the MySQL database."""
    bars = repo.get_candles(
        ticker=ticker,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return {
        "ticker": ticker.upper(),
        "timeframe": timeframe,
        "count": len(bars),
        "candles": bars
    }


@router.post("/collect/{ticker}")
def collect_single_stock(
    ticker: str,
    body: SingleCollectRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger collection for a single stock."""
    clean_ticker = ticker.strip().upper()
    background_tasks.add_task(
        candle_collection_service.collect_stock_candles,
        ticker=clean_ticker,
        sector=body.sector or "General Diversified",
        exchange=body.exchange,
    )
    return {
        "status": "queued",
        "ticker": clean_ticker,
        "message": f"Candlestick collection queued for {clean_ticker}."
    }


@router.post("/collect-5min/{ticker}")
def collect_5min_candles(
    ticker: str,
    background_tasks: BackgroundTasks,
    exchange: Optional[str] = Query(None, description="Optional exchange (e.g. NASDAQ, NYSE)"),
):
    """
    Trigger 5-minute candle collection for a signaled stock.
    - If new to DB: fetches past 6 months of 5min candles.
    - If already in DB: incrementally fills from last_date up to now.
    """
    clean_ticker = ticker.strip().upper()
    background_tasks.add_task(
        candle_collection_service.collect_5min_candles_for_signal,
        ticker=clean_ticker,
        exchange=exchange,
    )
    return {
        "status": "queued",
        "ticker": clean_ticker,
        "message": f"5-minute candle collection queued for {clean_ticker}."
    }


@router.get("/coverage/{ticker}")
def get_candle_coverage(
    ticker: str,
    timeframe: str = Query("5 min", description="Timeframe: '5 min', '1 hour', or '1 day'"),
):
    """Get the earliest (first day) and latest (last day) candle dates available for a ticker."""
    clean_ticker = ticker.strip().upper()
    cov = repo.get_candle_coverage(clean_ticker, timeframe=timeframe)
    if not cov:
        raise HTTPException(
            status_code=404,
            detail=f"No candle coverage found for {clean_ticker} on timeframe {timeframe}."
        )
    return {
        "ticker": cov["ticker"],
        "timeframe": cov["timeframe"],
        "first_date": cov["first_date"].isoformat() if hasattr(cov["first_date"], "isoformat") else str(cov["first_date"]),
        "last_date": cov["last_date"].isoformat() if hasattr(cov["last_date"], "isoformat") else str(cov["last_date"]),
        "candle_count": cov["candle_count"],
        "last_synced_at": cov["last_synced_at"].isoformat() if hasattr(cov["last_synced_at"], "isoformat") else str(cov["last_synced_at"]),
    }


@router.get("/check/{ticker}")
def check_ticker_db_status(ticker: str):
    """
    Check the database FIRST for a ticker:
    - When was it last updated (last_synced_at)?
    - Does it already have full 1-year historical data in DB?
    - Is an external LSEG fetch needed?
    """
    clean_ticker = ticker.strip().upper()
    return candle_collection_service.inspect_ticker_db_status(clean_ticker)


@router.post("/backfill")
def trigger_backfill(body: BackfillTriggerRequest):
    """
    Trigger the scheduled sector candlestick backfill job.
    Decommissioned: batch backfill has been replaced by event-driven news collection.
    """
    return {
        "status": "disabled",
        "message": "Batch backfill has been decommissioned. Candlestick data (1-year 5-minute) is now fetched strictly on-demand when live news is received for a ticker."
    }


@router.post("/batch/run-next")
def trigger_next_batch(batch_size: int = Query(50, ge=1, le=100)):
    """Decommissioned: batch collection has been replaced by event-driven news collection."""
    return {
        "status": "disabled",
        "message": "Batch collection has been decommissioned. Candlestick data (1-year 5-minute) is now fetched strictly on-demand when live news is received for a ticker."
    }


@router.get("/remaining")
def get_remaining_stocks():
    """Get count and list of stocks that have not yet completed candlestick collection."""
    remaining = candle_collection_service.get_remaining_stocks()
    completed = repo.get_completed_candle_tickers()
    return {
        "total_universe": 550,
        "completed_count": len(completed),
        "remaining_count": len(remaining),
        "remaining_stocks": remaining,
    }


@router.get("/batch/signaled/remaining")
def get_signaled_remaining():
    """Get list and count of signaled tickers that still need 1-year 5-minute candles."""
    remaining = candle_collection_service.get_signaled_stocks_remaining()
    return {
        "remaining_count": len(remaining),
        "stocks": remaining,
    }


@router.post("/batch/signaled/run-next")
def trigger_signaled_batch(batch_size: int = Query(25, ge=1, le=100)):
    """Decommissioned: batch collection has been replaced by event-driven news collection."""
    return {
        "status": "disabled",
        "message": "Batch collection has been decommissioned. Candlestick data (1-year 5-minute) is now fetched strictly on-demand when live news is received for a ticker."
    }


@router.get("/scheduler/status")
def get_scheduler_status():
    """Get active scheduled jobs and collection mode."""
    from tasks.scheduler import task_scheduler
    return {
        "scheduler_active": task_scheduler._scheduler.running,
        "mode": "event_driven_news_only",
        "batch_collection_active": False,
        "description": "Batch collection removed. 1-year 5m candles are fetched on-demand when news is received for a ticker.",
        "scheduled_jobs": task_scheduler.get_job_statuses(),
    }


@router.post("/scheduler/trigger-now")
async def trigger_batch_now():
    """Decommissioned: batch collection has been replaced by event-driven news collection."""
    from tasks.scheduler import task_scheduler
    return await task_scheduler.trigger_candle_batch_now()


@router.get("/status")
def get_collection_status():
    """Get status of the backfill worker, counts, and recent job logs."""
    return candle_collection_service.get_status()

