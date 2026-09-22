"""
LSEG Candlestick Client
=======================
Interfaces with the LSEG Flask Bridge to collect OHLCV candlestick data.
Maps standard US equity tickers to Refinitiv RIC codes and normalizes candle fields.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
import requests

from config.settings import settings
from services.logging_service import logger

# Field mapping dictionary for LSEG intraday and daily bars
FIELD_MAP = {
    "open": ["OPEN_PRC", "OPEN", "Open", "open"],
    "high": ["HIGH_1", "HIGH", "High", "high"],
    "low": ["LOW_1", "LOW", "Low", "low"],
    "close": ["TRDPRC_1", "CLOSE", "Close", "close"],
    "volume": ["ACVOL_UNS", "VOLUME", "Volume", "volume", "ACVOL_DEC"],
    "vwap": ["VWAP", "vwap"],
}


class LSEGCandleClient:
    """Client for retrieving candlestick data from the LSEG Bridge Server."""

    def __init__(
        self,
        primary_url: Optional[str] = None,
        backup_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.primary_url = (primary_url or settings.lseg_bridge_url).rstrip("/")
        self.backup_url = (backup_url or settings.lseg_backup_url).rstrip("/")
        self.timeout = timeout or settings.lseg_bridge_timeout

    @staticmethod
    def to_ric(ticker: str, exchange: Optional[str] = None) -> str:
        """
        Convert a standard equity ticker symbol to its Refinitiv RIC instrument code.
        Examples:
          AAPL (NASDAQ) -> AAPL.O
          JPM (NYSE)    -> JPM.N
          BAC (NYSE)    -> BAC.N
          MSFT (NASDAQ) -> MSFT.O
        """
        clean_ticker = ticker.strip().upper()
        if "." in clean_ticker or "=" in clean_ticker:
            return clean_ticker

        ex = (exchange or "").strip().upper()
        if ex in ["ARCA", "ARCX", "AMEX"]:
            return f"{clean_ticker}.P"
        elif ex in ["NYSE", "NYQ"]:
            return f"{clean_ticker}.N"
        elif ex in ["NASDAQ", "BATS", "OTC", "NAQ"]:
            return f"{clean_ticker}.O"
        else:
            # Default to NASDAQ suffix .O if unknown
            return f"{clean_ticker}.O"

    def _get_target_endpoints(self) -> List[str]:
        """Return list of candidate base endpoints to query in priority order."""
        candidates = [
            self.primary_url,
            "http://lseghost.dufercohellasgr.nordlayerconnect.net:5000/api/v1",
            self.backup_url,
            "http://127.0.0.1:5000/api/v1",
        ]
        valid_urls = []
        for u in candidates:
            if not u:
                continue
            base = u.rstrip("/")
            if not base.endswith("/api/v1"):
                base = f"{base}/api/v1"
            if base not in valid_urls:
                valid_urls.append(base)
        return valid_urls

    def fetch_raw_bars(
        self,
        ric: str,
        start_str: str,
        end_str: str,
        interval: str,
    ) -> List[Dict[str, Any]]:
        """
        Query the LSEG Flask Bridge for historical bars.
        Supported native intervals: '5min', '60min', '1D'.
        """
        endpoints = self._get_target_endpoints()
        last_error = None

        payload = {
            "universe": ric,
            "start": start_str,
            "end": end_str,
            "interval": interval,
        }

        for base in endpoints:
            url = f"{base}/pricing/historical"
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout)
                if resp.status_code == 200:
                    res_json = resp.json()
                    data = res_json.get("data", [])
                    logger.info(f"LSEG Bridge ({base}) returned {len(data)} raw bars for {ric} ({interval}).")
                    # Promote this working endpoint
                    self.primary_url = base
                    return data
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:150]}"
                    logger.warning(f"Bridge {url} returned {last_error}")
            except Exception as ex:
                last_error = str(ex)
                logger.warning(f"Could not reach {url}: {ex}")

        logger.error(f"Failed to fetch candles for {ric} across all servers. Last error: {last_error}")
        raise ConnectionError(f"Failed to fetch candles for {ric} across all servers. Last error: {last_error}")

    @staticmethod
    def parse_timestamp(ts_val: Any) -> Optional[datetime]:
        """Parse various date/time representations from LSEG into a naive or UTC datetime."""
        if not ts_val:
            return None
        if isinstance(ts_val, datetime):
            return ts_val

        ts_str = str(ts_val).strip()
        # Formats:
        # 1. ISO format: '2026-08-03T09:30:00'
        # 2. RFC format: 'Mon, 03 Aug 2026 05:00:00 GMT'
        # 3. Date format: '2026-08-03'
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(ts_str, fmt)
            except ValueError:
                continue

        try:
            # Fallback ISO parser
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None

    def standardize_bars(
        self,
        raw_bars: List[Dict[str, Any]],
        ticker: str,
        ric: str,
        timeframe: str,
    ) -> List[Dict[str, Any]]:
        """
        Normalize raw LSEG bars into standardized candle dictionaries matching the MySQL schema:
        [ticker, ric, timeframe, timestamp, open, high, low, close, volume, vwap, source]
        """
        normalized = []
        for bar in raw_bars:
            raw_ts = bar.get("Timestamp") or bar.get("Date") or bar.get("timestamp")
            dt = self.parse_timestamp(raw_ts)
            if not dt:
                continue

            def get_val(keys: List[str]) -> Optional[float]:
                for k in keys:
                    v = bar.get(k)
                    if v is not None:
                        try:
                            f = float(v)
                            if not (f != f):  # Check for NaN
                                return f
                        except (ValueError, TypeError):
                            pass
                return None

            c_open = get_val(FIELD_MAP["open"])
            c_high = get_val(FIELD_MAP["high"])
            c_low = get_val(FIELD_MAP["low"])
            c_close = get_val(FIELD_MAP["close"])
            c_vol = get_val(FIELD_MAP["volume"])
            c_vwap = get_val(FIELD_MAP["vwap"])

            # Only record bar if at least close price is available
            if c_close is None:
                continue

            normalized.append({
                "ticker": ticker.upper(),
                "ric": ric.upper(),
                "timeframe": timeframe,
                "timestamp": dt,
                "open": c_open or c_close,
                "high": c_high or c_close,
                "low": c_low or c_close,
                "close": c_close,
                "volume": c_vol or 0.0,
                "vwap": c_vwap or c_close,
                "source": "lseg",
            })

        return normalized

    def collect_candles_multi_year(
        self,
        ticker: str,
        exchange: Optional[str] = None,
        reference_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Execute the 3-year collection strategy for a stock:
          - Year 1 (now - 365d to now): 5-minute candles
          - Year 2 (now - 730d to now - 365d): 1-hour candles if available, else 1-day
          - Year 3 (now - 1095d to now - 730d): 1-hour candles if available, else 1-day

        Returns a dictionary summarizing bars collected per year and the standardized bars.
        """
        ric = self.to_ric(ticker, exchange)
        now = reference_date or datetime.now(timezone.utc).replace(tzinfo=None)

        d_now = now.strftime("%Y-%m-%dT23:59:59")
        d_1y_ago = (now - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00")
        d_2y_ago = (now - timedelta(days=730)).strftime("%Y-%m-%dT00:00:00")
        d_3y_ago = (now - timedelta(days=1095)).strftime("%Y-%m-%dT00:00:00")

        all_bars: List[Dict[str, Any]] = []

        summary = {
            "ticker": ticker,
            "ric": ric,
            "year_1": {"timeframe": "5 min", "status": "PENDING", "count": 0},
            "year_2": {"timeframe": None, "status": "PENDING", "count": 0},
            "year_3": {"timeframe": None, "status": "PENDING", "count": 0},
            "total_candles": 0,
            "errors": [],
        }

        # ── Year 1: 5-minute candles ──
        try:
            logger.info(f"[{ticker}] Fetching Year 1 (5min): {d_1y_ago} to {d_now}")
            raw_y1 = self.fetch_raw_bars(ric, start_str=d_1y_ago, end_str=d_now, interval="5min")
            std_y1 = self.standardize_bars(raw_y1, ticker=ticker, ric=ric, timeframe="5 min")
            summary["year_1"]["count"] = len(std_y1)
            summary["year_1"]["status"] = "SUCCESS" if std_y1 else "EMPTY"
            all_bars.extend(std_y1)
        except Exception as e:
            err = f"Year 1 5m error: {str(e)}"
            summary["year_1"]["status"] = "FAILED"
            summary["errors"].append(err)
            logger.error(f"[{ticker}] {err}")

        # ── Year 2: Hourly -> Fallback Daily ──
        try:
            logger.info(f"[{ticker}] Fetching Year 2 (hourly check): {d_2y_ago} to {d_1y_ago}")
            raw_y2 = self.fetch_raw_bars(ric, start_str=d_2y_ago, end_str=d_1y_ago, interval="60min")
            std_y2 = self.standardize_bars(raw_y2, ticker=ticker, ric=ric, timeframe="1 hour")

            if std_y2:
                summary["year_2"]["timeframe"] = "1 hour"
                summary["year_2"]["count"] = len(std_y2)
                summary["year_2"]["status"] = "SUCCESS"
                all_bars.extend(std_y2)
            else:
                logger.info(f"[{ticker}] Year 2 hourly empty, falling back to 1D daily bars...")
                start_date_only = (now - timedelta(days=730)).strftime("%Y-%m-%d")
                end_date_only = (now - timedelta(days=365)).strftime("%Y-%m-%d")
                raw_y2_daily = self.fetch_raw_bars(ric, start_str=start_date_only, end_str=end_date_only, interval="1D")
                std_y2_daily = self.standardize_bars(raw_y2_daily, ticker=ticker, ric=ric, timeframe="1 day")
                summary["year_2"]["timeframe"] = "1 day"
                summary["year_2"]["count"] = len(std_y2_daily)
                summary["year_2"]["status"] = "SUCCESS" if std_y2_daily else "EMPTY"
                all_bars.extend(std_y2_daily)
        except Exception as e:
            err = f"Year 2 error: {str(e)}"
            summary["year_2"]["status"] = "FAILED"
            summary["errors"].append(err)
            logger.error(f"[{ticker}] {err}")

        # ── Year 3: Hourly -> Fallback Daily ──
        try:
            logger.info(f"[{ticker}] Fetching Year 3 (hourly check): {d_3y_ago} to {d_2y_ago}")
            raw_y3 = self.fetch_raw_bars(ric, start_str=d_3y_ago, end_str=d_2y_ago, interval="60min")
            std_y3 = self.standardize_bars(raw_y3, ticker=ticker, ric=ric, timeframe="1 hour")

            if std_y3:
                summary["year_3"]["timeframe"] = "1 hour"
                summary["year_3"]["count"] = len(std_y3)
                summary["year_3"]["status"] = "SUCCESS"
                all_bars.extend(std_y3)
            else:
                logger.info(f"[{ticker}] Year 3 hourly empty, falling back to 1D daily bars...")
                start_date_only = (now - timedelta(days=1095)).strftime("%Y-%m-%d")
                end_date_only = (now - timedelta(days=730)).strftime("%Y-%m-%d")
                raw_y3_daily = self.fetch_raw_bars(ric, start_str=start_date_only, end_str=end_date_only, interval="1D")
                std_y3_daily = self.standardize_bars(raw_y3_daily, ticker=ticker, ric=ric, timeframe="1 day")
                summary["year_3"]["timeframe"] = "1 day"
                summary["year_3"]["count"] = len(std_y3_daily)
                summary["year_3"]["status"] = "SUCCESS" if std_y3_daily else "EMPTY"
                all_bars.extend(std_y3_daily)
        except Exception as e:
            err = f"Year 3 error: {str(e)}"
            summary["year_3"]["status"] = "FAILED"
            summary["errors"].append(err)
            logger.error(f"[{ticker}] {err}")

        summary["total_candles"] = len(all_bars)
        return {"summary": summary, "bars": all_bars}


# Singleton client instance
lseg_candle_client = LSEGCandleClient()
