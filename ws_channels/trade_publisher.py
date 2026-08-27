import asyncio
import json
from datetime import datetime, timezone
from websockets.asyncio.server import serve
from services.logging_service import logger
from config.settings import settings
from config.vault_registry import VAULT_REGISTRY


class TradePublisher:
    """
    WebSocket server that publishes trade commands to gotti-visualize.
    Broadcasts trade instructions with hierarchical trading permissions (L..5).
    """

    def __init__(self):
        self._clients: set = set()
        self._server = None
        self._port = settings.trade_ws_port

    async def start(self) -> None:
        """Start the WebSocket server."""
        self._server = await serve(self._handler, '0.0.0.0', self._port)
        logger.startup(
            f'Trade publisher WebSocket server started on port {self._port}'
        )

    async def _handler(self, websocket) -> None:
        """Handle a new gotti-visualize client connection."""
        self._clients.add(websocket)
        remote = websocket.remote_address
        logger.info(f'Trade subscriber connected: {remote}')
        try:
            # Keep connection alive, listen for pings/acks
            async for message in websocket:
                logger.info(f'Received from subscriber {remote}: {message}')
        except Exception as e:
            logger.info(f'Trade subscriber disconnected: {remote} ({e})')
        finally:
            self._clients.discard(websocket)

    async def publish_trade_command(
        self,
        ticker: str,
        risk_level: int,
        signal_position: str,
        evaluation_score: float | None = None,
        eligible_levels: list[int] | None = None,
        eligible_vaults: list[str] | None = None
    ) -> int:
        """
        Broadcast a trade command to all connected gotti-visualize instances.
        Includes base risk level and all eligible upward strategy tiers (L..3).
        """
        vault_config = VAULT_REGISTRY.get(risk_level)
        vault_name = vault_config.name if vault_config else f'Level {risk_level}'

        levels = eligible_levels or list(range(risk_level, 4))
        vaults = eligible_vaults or [VAULT_REGISTRY[lvl].name for lvl in levels if lvl in VAULT_REGISTRY]


        command = {
            'type': 'TRADE_COMMAND',
            'ticker': ticker,
            'base_risk_level': risk_level,
            'signal_position': signal_position,
            'vault_name': vault_name,
            'evaluation_score': evaluation_score,
            'eligible_risk_levels': levels,
            'eligible_vaults': vaults,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        message = json.dumps(command)
        sent_count = 0

        if not self._clients:
            logger.trade(
                f'{ticker} {signal_position} -> Base Level {risk_level} ({vault_name}) '
                f'| Eligible in Levels {levels} — no subscribers connected'
            )
            return 0

        # Broadcast to all connected clients
        disconnected = set()
        for client in self._clients:
            try:
                await client.send(message)
                sent_count += 1
            except Exception:
                disconnected.add(client)

        self._clients -= disconnected

        logger.trade(
            f'{ticker} {signal_position} -> Base Level {risk_level} ({vault_name}) '
            f'| Eligible in Levels {levels} — sent to {sent_count} subscriber(s)'
        )
        return sent_count

    async def stop(self) -> None:
        """Shut down the WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for client in list(self._clients):
            await client.close()
        self._clients.clear()
        logger.shutdown('Trade publisher stopped')


# Singleton publisher instance
trade_publisher = TradePublisher()
