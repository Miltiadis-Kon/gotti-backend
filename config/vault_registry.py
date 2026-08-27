from dataclasses import dataclass
from config.settings import settings


@dataclass
class VaultConfig:
    """Configuration for a single ETF vault backed by a dedicated Alpaca paper account."""
    risk_level: int
    name: str
    symbol: str
    description: str

    @property
    def api_key(self) -> str:
        try:
            key, _ = settings.get_alpaca_keys(self.risk_level)
            return key
        except ValueError:
            return ""

    @property
    def secret_key(self) -> str:
        try:
            _, secret = settings.get_alpaca_keys(self.risk_level)
            return secret
        except ValueError:
            return ""

    @property
    def annual_fee(self) -> float:
        return settings.default_annual_fee


VAULT_REGISTRY: dict[int, VaultConfig] = {
    1: VaultConfig(
        risk_level=1,
        name='Boomer Haven ETF',
        symbol='ETF-LVL1',
        description='S&P 500 Dividend Aristocrats, Mega-Cap Value & Defensive Tech. Pure buy & hold, quarterly rebalance drift. Target: 5%–9%, Beta: < 0.75.',
    ),
    2: VaultConfig(
        risk_level=2,
        name='Steady Grind ETF',
        symbol='ETF-LVL2',
        description='Large & Mid-Cap Growth Leaders, Systematic Sector Momentum. Multi-month swings with monthly momentum rebalancing. Target: 10%–18%, Beta: 0.85–1.25.',
    ),
    3: VaultConfig(
        risk_level=3,
        name='Diamond Hands ETF',
        symbol='ETF-LVL3',
        description='High-Beta Equities, Emerging Small/Micro-Caps, Dynamic Breakout Stocks. Tactical momentum and high-turnover swing allocation. Target: 20%+, Beta: > 1.35.',
    ),
}

