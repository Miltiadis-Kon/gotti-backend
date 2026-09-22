"""
NewsListener WebSocket Client
=============================
Subscribes to stock-alchemist's real-time news stream (/ws/news).
When news arrives for a ticker, triggers 1-year 5-minute candlestick collection
for that specific stock on-demand (no bulk batch polling).
"""

import asyncio
import json
from websockets.asyncio.client import connect
from services.logging_service import logger
from config.settings import settings
from services.candle_collection_service import candle_collection_service


class NewsListener:
    """
    WebSocket client connecting to stock-alchemist /ws/news.
    Listens for breaking news and triggers 1y 5m candle collection for mentioned tickers.
    """

    def __init__(self):
        base_url = getattr(settings, "sa_ws_url", "ws://stock-alchemist:8080/ws/signals")
        if "/ws/signals" in base_url:
            self._url = base_url.replace("/ws/signals", "/ws/news")
        else:
            self._url = "ws://stock-alchemist:8080/ws/news"
        self._running = False
        self._reconnect_delay = 1

    async def start(self) -> None:
        """Start listening for live news. Runs indefinitely with auto-reconnect."""
        self._running = True
        logger.startup(f"News listener connecting to {self._url}")

        while self._running:
            try:
                async with connect(self._url) as ws:
                    logger.info("Connected to stock-alchemist live news stream (/ws/news)")
                    self._reconnect_delay = 1  # Reset on successful connect

                    async for message in ws:
                        await self._handle_message(message)

            except Exception as e:
                if not self._running:
                    break
                logger.error(
                    f"News listener disconnected: {e}. "
                    f"Reconnecting in {self._reconnect_delay}s..."
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)

    async def _handle_message(self, raw_message: str) -> None:
        """Parse incoming news item and fetch 1-year 5m candles for each mentioned ticker."""
        try:
            data = json.loads(raw_message)
            symbols = data.get("symbols") or []
            if isinstance(symbols, str):
                symbols = [s.strip() for s in symbols.split(",") if s.strip()]
            headline = str(data.get("headline") or "")

            if not symbols:
                return

            for raw_ticker in symbols:
                if not isinstance(raw_ticker, str):
                    continue
                ticker = raw_ticker.strip().upper()
                # Skip invalid or crypto symbols
                if not ticker or "/" in ticker or "+" in ticker or "=" in ticker or ticker.endswith("USD"):
                    continue

                # 1. First check DB: last updated (last_synced_at) & whether ticker already has 1-year historical data
                db_status = await asyncio.to_thread(
                    candle_collection_service.inspect_ticker_db_status,
                    ticker,
                )

                if not db_status.get("action_needed"):
                    logger.info(
                        f"[NEWS CANDLES] News received for {ticker} ('{headline[:50]}...'). "
                        f"DB check: {db_status['reason']} -> No LSEG fetch needed."
                    )
                    continue

                # 2. Only if DB check indicates missing historical data or stale coverage, ask LSEG
                logger.info(
                    f"[NEWS CANDLES] News received for {ticker} ('{headline[:50]}...'). "
                    f"DB check: {db_status['reason']} -> Requesting {db_status['fetch_type']} from LSEG..."
                )

                # Fetch 1 year of 5-minute candles on-demand in background
                asyncio.create_task(
                    asyncio.to_thread(
                        candle_collection_service.collect_5min_candles_for_signal,
                        ticker=ticker,
                    )
                )

        except json.JSONDecodeError:
            logger.debug(f"[NEWS CANDLES] Invalid JSON on news stream: {raw_message[:80]}")
        except Exception as e:
            logger.error(f"[NEWS CANDLES] Error handling news item for candle collection: {e}")

    def stop(self) -> None:
        """Stop the news listener gracefully."""
        self._running = False
        logger.shutdown("News listener stopped")


news_listener = NewsListener()
