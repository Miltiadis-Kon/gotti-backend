"""
Candlestick Batch Runner
========================
Executes a batch of 50 stocks and persists multi-timeframe candles to MySQL.
Used by the background runner and scheduled task.
"""
import sys
from db.connection import pool
pool.initialize()

from services.candle_collection_service import candle_collection_service
from services.logging_service import logger

batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 50
logger.info(f"=== STARTING BATCH COLLECTION FOR NEXT {batch_size} STOCKS ===")
res = candle_collection_service.process_next_batch_sync(batch_size=batch_size, delay_seconds=0.5)
logger.info(
    f"=== BATCH FINISHED: {res.get('processed_count')} stocks processed, "
    f"{res.get('total_candles')} candles saved, "
    f"{res.get('remaining_count')} stocks remaining for future hourly runs ==="
)
pool.close()
