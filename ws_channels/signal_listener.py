import asyncio
import json
from websockets.asyncio.client import connect
from services.logging_service import logger
from services.risk_classifier import risk_classifier
from config.settings import settings


class SignalListener:
    """
    WebSocket client that subscribes to stock-alchemist's signal stream.
    Auto-reconnects on disconnect with exponential backoff.
    """

    def __init__(self, on_signal_callback=None):
        self._url = settings.sa_ws_url
        self._running = False
        self._on_signal = on_signal_callback
        self._reconnect_delay = 1  # seconds, doubles on failure, max 60

    async def start(self) -> None:
        """Start listening for signals. Runs indefinitely with auto-reconnect."""
        self._running = True
        logger.startup(f'Signal listener connecting to {self._url}')

        while self._running:
            try:
                async with connect(self._url) as ws:
                    logger.info('Connected to stock-alchemist signal stream')
                    self._reconnect_delay = 1  # Reset on successful connect

                    async for message in ws:
                        await self._handle_message(message)

            except Exception as e:
                if not self._running:
                    break
                logger.error(
                    f'Signal listener disconnected: {e}. '
                    f'Reconnecting in {self._reconnect_delay}s...'
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)

    async def _handle_message(self, raw_message: str) -> None:
        """Parse and process an incoming signal message."""
        try:
            data = json.loads(raw_message)
            ticker = data.get('ticker', '')
            position = data.get('signal_position', data.get('position', ''))
            sentiment = data.get('sentiment')

            logger.signal(
                f'Received: {ticker} {position} '
                f'(sentiment: {sentiment})'
            )

            # Classify the ticker's risk level with hierarchical upward trading permissions
            assignment = risk_classifier.classify_ticker(ticker)

            # Forward to the trade publisher callback if registered
            if assignment and self._on_signal:
                await self._on_signal({
                    'ticker': ticker,
                    'signal_position': position,
                    'risk_level': assignment.assigned_risk_level,
                    'evaluation_score': assignment.evaluation_score,
                    'eligible_levels': assignment.eligible_levels,
                    'eligible_vaults': assignment.eligible_vaults,
                })

        except json.JSONDecodeError:
            logger.error(f'Invalid JSON from signal stream: {raw_message[:100]}')
        except Exception as e:
            logger.error(f'Error handling signal: {e}')

    def stop(self) -> None:
        """Stop the listener gracefully."""
        self._running = False
        logger.shutdown('Signal listener stopped')
