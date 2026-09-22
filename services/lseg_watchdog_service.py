"""
LSEG Bridge & NordLayer VPN Watchdog Service
============================================
Continuously monitors connectivity to the LSEG Bridge over the NordLayer VPN tunnel.
Tracks latency, session status, and consecutive failures, providing early alerting
before downstream news and candle ingestion tasks fail.
"""

import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import requests

from config.settings import settings

logger = logging.getLogger("LSEGWatchdog")


class LSEGWatchdogService:
    """
    Singleton service monitoring the LSEG Bridge and VPN connection.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self.base_url = settings.lseg_bridge_url.rstrip("/")
        # If url ends with /api/v1, health is /health
        if self.base_url.endswith("/api/v1"):
            self.health_url = f"{self.base_url}/health"
        else:
            self.health_url = f"{self.base_url}/api/v1/health"

        self.timeout = 5  # seconds
        self.status = "UNKNOWN"
        self.lseg_session_open = False
        self.latency_ms = 0.0
        self.last_checked_at: Optional[str] = None
        self.consecutive_failures = 0
        self.last_error: Optional[str] = None
        self.details: Dict[str, Any] = {}

    def check_health(self) -> Dict[str, Any]:
        """
        Executes a healthcheck probe against the LSEG Bridge server.
        Updates internal state and returns a summary dict.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        self.last_checked_at = now_iso
        t0 = time.time()

        try:
            resp = requests.get(self.health_url, timeout=self.timeout)
            latency = round((time.time() - t0) * 1000, 2)
            self.latency_ms = latency

            if resp.status_code == 200:
                data = resp.json()
                self.lseg_session_open = bool(data.get("lseg_session_open", False))
                self.consecutive_failures = 0
                self.last_error = None
                self.details = data

                if self.lseg_session_open:
                    self.status = "HEALTHY"
                else:
                    self.status = "DEGRADED"  # Server reachable, but LSEG desktop session closed
                    logger.warning("[LSEG WATCHDOG] Bridge is online, but LSEG desktop session is CLOSED.")

            else:
                self.status = "DEGRADED"
                self.consecutive_failures += 1
                self.last_error = f"HTTP {resp.status_code}"
                logger.warning(f"[LSEG WATCHDOG] Health probe returned HTTP {resp.status_code}")

        except requests.exceptions.Timeout:
            self.status = "OFFLINE"
            self.consecutive_failures += 1
            self.latency_ms = 0.0
            self.last_error = "Connection timed out (VPN tunnel may be degraded or offline)"
            logger.error(f"[LSEG WATCHDOG] Timeout reaching {self.health_url} ({self.consecutive_failures} failures)")

        except requests.exceptions.ConnectionError as e:
            self.status = "OFFLINE"
            self.consecutive_failures += 1
            self.latency_ms = 0.0
            self.last_error = f"Connection refused (NordLayer VPN tunnel is likely down): {e}"
            logger.error(f"[LSEG WATCHDOG] Connection error: {self.last_error}")

        except Exception as e:
            self.status = "OFFLINE"
            self.consecutive_failures += 1
            self.last_error = str(e)
            logger.error(f"[LSEG WATCHDOG] Unexpected probe error: {e}")

        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        """Returns the latest watchdog status."""
        return {
            "status": self.status,
            "lseg_session_open": self.lseg_session_open,
            "latency_ms": self.latency_ms,
            "last_checked_at": self.last_checked_at,
            "consecutive_failures": self.consecutive_failures,
            "last_error": self.last_error,
            "health_url": self.health_url,
            "details": self.details
        }


# Singleton instance
lseg_watchdog = LSEGWatchdogService()
