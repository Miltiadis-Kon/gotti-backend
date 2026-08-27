import io
import logging
import sys
from datetime import datetime, timezone


# ANSI color codes for terminal output
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'


class LoggingService:
    """Structured console logger with colored prefixes for Module 4 operations."""

    def __init__(self):
        self._logger = logging.getLogger('gotti-m4')
        self._logger.setLevel(logging.DEBUG)
        if not self._logger.handlers:
            # Safe UTF-8 stream handler for Windows console
            try:
                if hasattr(sys.stdout, "reconfigure"):
                    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter('%(message)s'))
            self._logger.addHandler(handler)

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime('%H:%M:%S')

    def _log(self, prefix: str, color: str, message: str) -> None:
        ts = self._timestamp()
        safe_msg = str(message).replace("→", "->").replace("€", "EUR").replace("•", "*")
        self._logger.info(
            f'{Colors.GRAY}{ts}{Colors.RESET} '
            f'{color}{Colors.BOLD}[{prefix}]{Colors.RESET} {safe_msg}'
        )

    def navpu(self, message: str) -> None:
        """Log NAVPU sync events."""
        self._log('NAVPU', Colors.BLUE, message)

    def deposit(self, message: str) -> None:
        """Log deposit events."""
        self._log('DEPOSIT', Colors.GREEN, message)

    def withdraw(self, message: str) -> None:
        """Log withdrawal events."""
        self._log('WITHDRAW', Colors.YELLOW, message)

    def signal(self, message: str) -> None:
        """Log incoming signals from stock-alchemist."""
        self._log('SIGNAL', Colors.CYAN, message)

    def risk(self, message: str) -> None:
        """Log risk classification results."""
        self._log('RISK', Colors.MAGENTA, message)

    def trade(self, message: str) -> None:
        """Log trade commands dispatched to gotti-visualize."""
        self._log('TRADE', Colors.GREEN, message)

    def error(self, message: str) -> None:
        """Log errors."""
        self._log('ERROR', Colors.RED, message)

    def info(self, message: str) -> None:
        """Log general info."""
        self._log('INFO', Colors.WHITE, message)

    def startup(self, message: str) -> None:
        """Log startup events."""
        self._log('STARTUP', Colors.GREEN, message)

    def shutdown(self, message: str) -> None:
        """Log shutdown events."""
        self._log('SHUTDOWN', Colors.YELLOW, message)


# Singleton logger instance
logger = LoggingService()
