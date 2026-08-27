from decimal import Decimal
from alpaca.trading.client import TradingClient
from config.vault_registry import VAULT_REGISTRY
from services.logging_service import logger


class AlpacaClientFactory:
    """Factory that creates and caches Alpaca TradingClient instances per vault."""

    def __init__(self):
        self._clients: dict[int, TradingClient] = {}

    def get_client(self, risk_level: int) -> TradingClient:
        """Get or create the Alpaca TradingClient for a given risk level."""
        if risk_level not in self._clients:
            config = VAULT_REGISTRY.get(risk_level)
            if not config:
                raise ValueError(f'No vault config for risk level {risk_level}')
            if not config.api_key or not config.secret_key:
                raise ValueError(
                    f'Alpaca credentials not configured for level {risk_level} '
                    f'({config.name}). Set ALPACA_KEY_LVL{risk_level} and '
                    f'ALPACA_SECRET_LVL{risk_level} in .env'
                )
            self._clients[risk_level] = TradingClient(
                api_key=config.api_key,
                secret_key=config.secret_key,
                paper=True,
            )
            logger.info(f'Alpaca client created for Level {risk_level} ({config.name})')
        return self._clients[risk_level]

    def get_account_equity(self, risk_level: int) -> Decimal:
        """Fetch the current paper account equity for a vault."""
        client = self.get_client(risk_level)
        account = client.get_account()
        return Decimal(str(account.equity))

    def get_account_info(self, risk_level: int) -> dict:
        """Fetch account summary for a vault."""
        client = self.get_client(risk_level)
        account = client.get_account()
        return {
            'equity': str(account.equity),
            'cash': str(account.cash),
            'buying_power': str(account.buying_power),
            'portfolio_value': str(account.portfolio_value),
        }


# Singleton factory instance
alpaca_factory = AlpacaClientFactory()
