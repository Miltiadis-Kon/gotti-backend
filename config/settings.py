import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """
    Centralized Settings supporting both environment variables (.env)
    and dynamic synchronization from the shared MySQL `system_config` table.
    
    STRICT SECURITY RULE:
    There are NO fallback or default mock API keys or passwords.
    Missing credentials strictly raise errors when requested.
    """
    # ── 1. Database (MySQL Shared 'gotti' Schema) ────────────────────
    db_host: str = field(default_factory=lambda: os.getenv('DB_HOST', 'localhost'))
    db_port: int = field(default_factory=lambda: int(os.getenv('DB_PORT', '3306')))
    db_user: str = field(default_factory=lambda: os.getenv('DB_USER', os.getenv('DB_USERNAME', 'root')))
    db_password: str = field(default_factory=lambda: os.getenv('DB_PASSWORD', ''))
    db_name: str = field(default_factory=lambda: os.getenv('DB_NAME', os.getenv('DB_DATABASE', 'gotti')))

    # ── 2. Alpaca Keys per Strategy Level (1-3) ─────────────────────
    alpaca_key_lvl1: str = field(default_factory=lambda: os.getenv('ALPACA_KEY_LVL1', ''))
    alpaca_secret_lvl1: str = field(default_factory=lambda: os.getenv('ALPACA_SECRET_LVL1', ''))
    alpaca_key_lvl2: str = field(default_factory=lambda: os.getenv('ALPACA_KEY_LVL2', ''))
    alpaca_secret_lvl2: str = field(default_factory=lambda: os.getenv('ALPACA_SECRET_LVL2', ''))
    alpaca_key_lvl3: str = field(default_factory=lambda: os.getenv('ALPACA_KEY_LVL3', ''))
    alpaca_secret_lvl3: str = field(default_factory=lambda: os.getenv('ALPACA_SECRET_LVL3', ''))

    # ── 3. Stock Alchemist & AI Valuation ───────────────────────────
    alpaca_api_key: str = field(default_factory=lambda: os.getenv('ALPACA_API_KEY', ''))
    alpaca_api_secret: str = field(default_factory=lambda: os.getenv('ALPACA_API_SECRET', ''))
    gemini_api_key: str = field(default_factory=lambda: os.getenv('GEMINI_API_KEY', ''))
    gemini_model: str = field(default_factory=lambda: os.getenv('GEMINI_MODEL', 'gemini-2.0-flash'))
    marketaux_api_token: str = field(default_factory=lambda: os.getenv('MARKETAUX_API_TOKEN', ''))
    lseg_enabled: bool = field(default_factory=lambda: os.getenv('LSEG_ENABLED', 'true').lower() == 'true')
    lseg_bridge_url: str = field(default_factory=lambda: os.getenv('LSEG_BRIDGE_URL', 'http://127.0.0.1:5000/api/v1'))
    lseg_bridge_timeout: int = field(default_factory=lambda: int(os.getenv('LSEG_BRIDGE_TIMEOUT', '10')))

    # ── 4. Telegram Notifications ────────────────────────────────────
    telegram_enabled: bool = field(default_factory=lambda: os.getenv('TELEGRAM_ENABLED', 'false').lower() == 'true')
    telegram_signals_bot_token: str = field(default_factory=lambda: os.getenv('TELEGRAM_SIGNALS_BOT_TOKEN', ''))
    telegram_signals_chat_id: str = field(default_factory=lambda: os.getenv('TELEGRAM_SIGNALS_CHAT_ID', ''))
    telegram_errors_bot_token: str = field(default_factory=lambda: os.getenv('TELEGRAM_ERRORS_BOT_TOKEN', ''))
    telegram_errors_chat_id: str = field(default_factory=lambda: os.getenv('TELEGRAM_ERRORS_CHAT_ID', ''))

    # ── 5. Networking & WebSocket Ports ──────────────────────────────
    port: int = field(default_factory=lambda: int(os.getenv('PORT', os.getenv('BACKEND_PORT', '10000'))))
    trade_ws_port: int = field(default_factory=lambda: int(os.getenv('TRADE_WS_PORT', '8001')))
    sa_ws_url: str = field(default_factory=lambda: os.getenv('SA_WS_URL', 'ws://localhost:8080/ws/signals'))
    healthcheck_port: int = field(default_factory=lambda: int(os.getenv('HEALTHCHECK_PORT', '8080')))
    next_public_api_url: str = field(default_factory=lambda: os.getenv('NEXT_PUBLIC_API_URL', 'http://localhost:10000/api'))
    api_secret: str = field(default_factory=lambda: os.getenv('API_SECRET', ''))

    # ── 6. Simulation & Strategy Parameters ──────────────────────────
    nav_sync_interval: int = field(default_factory=lambda: int(os.getenv('NAV_SYNC_INTERVAL', '300')))
    default_annual_fee: float = field(default_factory=lambda: float(os.getenv('DEFAULT_ANNUAL_FEE', '0.015')))

    # Dynamic DB configs cache
    _db_configs: dict[str, str] = field(default_factory=dict)

    def load_from_db(self) -> None:
        """
        Dynamically fetch all credentials and configurations from the MySQL `system_config` table
        and update active settings.
        """
        try:
            from db.repository import repo
            configs = repo.get_all_configs()
            if not configs:
                return

            self._db_configs = configs

            # Map database keys to settings attributes
            mapping = {
                'DB_HOST': 'db_host',
                'DB_PORT': 'db_port',
                'DB_USER': 'db_user',
                'DB_USERNAME': 'db_user',
                'DB_PASSWORD': 'db_password',
                'DB_NAME': 'db_name',
                'DB_DATABASE': 'db_name',
                'ALPACA_KEY_LVL1': 'alpaca_key_lvl1',
                'ALPACA_SECRET_LVL1': 'alpaca_secret_lvl1',
                'ALPACA_KEY_LVL2': 'alpaca_key_lvl2',
                'ALPACA_SECRET_LVL2': 'alpaca_secret_lvl2',
                'ALPACA_KEY_LVL3': 'alpaca_key_lvl3',
                'ALPACA_SECRET_LVL3': 'alpaca_secret_lvl3',
                'ALPACA_API_KEY': 'alpaca_api_key',
                'ALPACA_API_SECRET': 'alpaca_api_secret',
                'GEMINI_API_KEY': 'gemini_api_key',
                'GEMINI_MODEL': 'gemini_model',
                'MARKETAUX_API_TOKEN': 'marketaux_api_token',
                'API_SECRET': 'api_secret',
                'SA_WS_URL': 'sa_ws_url',
                'TRADE_WS_PORT': 'trade_ws_port',
                'PORT': 'port',
                'BACKEND_PORT': 'port',
                'NAV_SYNC_INTERVAL': 'nav_sync_interval',
                'DEFAULT_ANNUAL_FEE': 'default_annual_fee',
            }

            for db_key, val in configs.items():
                attr = mapping.get(db_key.upper())
                if attr and hasattr(self, attr):
                    curr_type = type(getattr(self, attr))
                    if curr_type == int:
                        try:
                            setattr(self, attr, int(val))
                        except ValueError:
                            pass
                    elif curr_type == float:
                        try:
                            setattr(self, attr, float(val))
                        except ValueError:
                            pass
                    elif curr_type == bool:
                        setattr(self, attr, val.lower() == 'true')
                    else:
                        setattr(self, attr, str(val))
        except Exception:
            # If DB is not yet available or pool uninitialized, retain env values
            pass

    def get_alpaca_keys(self, level: int) -> tuple[str, str]:
        """
        Return (api_key, secret_key) for the given risk level.
        Strict check: Raises ValueError if credentials are not configured.
        NO fallback or default fake keys are permitted.
        """
        keys = {
            1: (self.alpaca_key_lvl1, self.alpaca_secret_lvl1),
            2: (self.alpaca_key_lvl2, self.alpaca_secret_lvl2),
            3: (self.alpaca_key_lvl3, self.alpaca_secret_lvl3),
        }
        if level not in keys:
            raise ValueError(f"Invalid ETF risk level: {level}. Must be 1-3.")

        key, secret = keys[level]
        if not key or not secret:
            raise ValueError(
                f"Alpaca credentials for Level {level} are missing! "
                f"Please configure ALPACA_KEY_LVL{level} and ALPACA_SECRET_LVL{level} in the MySQL system_config table or .env"
            )
        return key, secret


    def require(self, key_name: str) -> str:
        """Fetch a required configuration or raise an explicit error."""
        val = getattr(self, key_name.lower(), None) or self._db_configs.get(key_name) or os.getenv(key_name)
        if not val:
            raise ValueError(f"Missing required credential: {key_name}. Configure in MySQL system_config or .env")
        return str(val)


# Central settings singleton
settings = Settings()
