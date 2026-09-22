"""
Candle Collection Service
=========================
Manages sector universes, cross-evaluates tickers against the MySQL `available_tickers`
database whitelist, and orchestrates multi-timeframe candlestick collection:
  - Year 1: 5-minute candles
  - Year 2: 1-hour candles if available, else daily (1D)
  - Year 3: 1-hour candles if available, else daily (1D)
"""

import uuid
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from config.settings import settings
from db.repository import repo
from services.logging_service import logger
from services.lseg_candle_client import lseg_candle_client

# ══════════════════════════════════════════════════════════════════════════════
# TOP 50 LIQUID STOCKS ACROSS 11 GICS SECTORS
# ══════════════════════════════════════════════════════════════════════════════
SECTOR_UNIVERSE_50: Dict[str, List[str]] = {
    "Information Technology": [
        "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "CSCO", "AMD", "ACN",
        "INTC", "TXN", "QCOM", "IBM", "AMAT", "NOW", "LRCX", "ADI", "MU", "KLAC",
        "PANW", "SNPS", "CDNS", "CRWD", "FTNT", "MCHP", "NXPI", "APH", "MSI", "ROP",
        "ANET", "TEL", "ON", "MPWR", "WDAY", "CTSH", "GLW", "HPQ", "HPE", "FICO",
        "TDY", "ZBRA", "TER", "KEYS", "SWKS", "NTAP", "WDC", "STX", "PTC", "GEN"
    ],
    "Financials": [
        "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "SPGI", "AXP", "PGR",
        "CB", "MMC", "SCHW", "MCO", "AON", "CME", "ICE", "USB", "PNC", "TRV",
        "AJG", "AFL", "ALL", "PRU", "MET", "BK", "AIG", "AMP", "COF", "TFC",
        "SYF", "MSCI", "HIG", "FITB", "WTW", "MTB", "ACGL", "BRO", "RJF", "NTRS",
        "HBAN", "CINF", "RF", "CFG", "KEY", "PFG", "L", "WRB", "EG", "FDS"
    ],
    "Healthcare": [
        "LLY", "UNH", "JNJ", "ABBV", "MRK", "TMO", "ABT", "DHR", "PFE", "AMGN",
        "ISRG", "SYK", "MDT", "ELV", "GILD", "VRTX", "REGN", "CI", "BSX", "ZTS",
        "BDX", "HCA", "MCK", "EW", "COR", "A", "IDXX", "IQV", "HUM", "DXCM",
        "CNC", "BIIB", "MTD", "CAH", "RMD", "BAX", "ALNY", "ILMN", "STE", "WAT",
        "PODD", "WST", "ZBH", "ALGN", "MOH", "COO", "HOLX", "VTRS", "TECH", "DGX"
    ],
    "Consumer Discretionary": [
        "AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "BKNG", "SBUX", "TJX", "TGT",
        "ABNB", "MAR", "ORLY", "AZO", "LULU", "ROST", "CMG", "HLT", "YUM", "DHI",
        "LEN", "F", "GM", "APTV", "EBAY", "DRI", "EXPE", "ULTA", "GPC", "RCL",
        "NVR", "CCL", "BBY", "KMX", "LVS", "DPZ", "TSCO", "POOL", "CZR", "MGM",
        "PHM", "WYNN", "BWA", "BURL", "HAS", "TPR", "RL", "NCLH", "LKQ", "LEG"
    ],
    "Consumer Staples": [
        "PG", "COST", "KO", "PEP", "WMT", "PM", "MDLZ", "MO", "CL", "EL",
        "ADM", "KMB", "STZ", "GIS", "SYY", "HSY", "K", "KR", "CLX", "MKC",
        "TSN", "CAG", "CHD", "SJM", "HRL", "CPB", "TAP", "LW", "BG", "MNST",
        "KVUE", "TGT", "DLTR", "DG", "CCEP", "POST", "INGR", "DAR", "FLO", "CASY",
        "SFM", "USFD", "PPC", "CELH", "CALM", "JJSF", "HAIN", "SAM", "FIZZ", "BGS"
    ],
    "Industrials": [
        "GE", "CAT", "UNP", "RTX", "HON", "BA", "DE", "LMT", "ETN", "UPS",
        "NOC", "WM", "ITW", "GD", "CSX", "NSC", "EMR", "PH", "FDX", "TT",
        "TDG", "CTAS", "PCAR", "CARR", "ROK", "GWW", "VMC", "MLM", "URI", "OTIS",
        "AME", "IR", "FAST", "XYL", "LHX", "PWR", "HWM", "DOV", "WAB", "EXPD",
        "JBHT", "HUBB", "SNA", "TXT", "IEX", "MAS", "NDSN", "CHRW", "ALLE", "AOS"
    ],
    "Energy": [
        "XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PSX", "VLO", "OXY", "CIVI",
        "WMB", "KMI", "HAL", "BKR", "DVN", "FANG", "OKE", "CTRA", "CRC", "TRGP",
        "EQT", "APA", "OVV", "CHRD", "MTDR", "AR", "RRC", "SM", "XPRO", "PR",
        "VIST", "PBF", "DK", "MUR", "MGY", "CRK", "CNX", "HP", "NBR", "VAL",
        "RIG", "NOV", "TDW", "RES", "PTEN", "WHD", "OII", "LBRT", "HLX", "OIS"
    ],
    "Materials": [
        "LIN", "SHW", "APD", "ECL", "NEM", "FCX", "CTVA", "NUE", "DOW", "DD",
        "ALB", "PPG", "IFF", "BALL", "PKG", "IP", "CE", "CF", "FMC", "MOS",
        "EMN", "STLD", "AVY", "AMCR", "AA", "SEE", "RPM", "CC", "OLN", "ASH",
        "MP", "ATR", "SON", "HUN", "KWR", "NEU", "GPRE", "CRS", "ATI", "CMC",
        "CLF", "KNTK", "RS", "MDU", "EXP", "CENX", "USLM", "KALU", "MATV", "VMC"
    ],
    "Utilities": [
        "NEE", "SO", "DUK", "CEG", "SRE", "AEP", "D", "EXC", "PCG", "XEL",
        "ED", "WEC", "ES", "AWK", "EIX", "ETR", "FE", "PPL", "CMS", "CNP",
        "ATO", "DTE", "LNT", "NI", "EVRG", "NRG", "AES", "PNW", "OGE", "IDA",
        "SR", "POR", "SWX", "BKH", "NWE", "UGI", "NJR", "ALE", "MGEE", "OGS",
        "OTTR", "AVA", "CWT", "AWR", "YORW", "MSEX", "NWN", "UTL", "CPK", "AEE"
    ],
    "Real Estate": [
        "PLD", "AMT", "EQIX", "CCI", "PSA", "O", "WELL", "DLR", "SPG", "VICI",
        "AVB", "EQR", "WY", "SBAC", "INVH", "EXR", "MAA", "VTR", "ARE", "UDR",
        "CPT", "HST", "KIM", "REG", "BXP", "FRT", "AMH", "ESS", "NNN", "TRNO",
        "EPR", "CUBE", "GLPI", "STAG", "COLD", "OUT", "MAC", "SKT", "SLG", "HIW",
        "PGRE", "JBGS", "DEI", "VNO", "KRC", "ESRT", "CUZ", "IRM", "ELS", "SUI"
    ],
    "Communication Services": [
        "GOOGL", "META", "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS", "CHTR", "EA",
        "TTWO", "OMC", "IPG", "LYV", "FOXA", "FOX", "NWSA", "NWS", "MTCH", "LBRDA",
        "LBRDK", "SIRI", "WBD", "ROKU", "PINS", "SNAP", "SPOT", "IAC", "NYT", "TGNA",
        "CABO", "IRDM", "GOGO", "BAND", "CNXC", "MSGS", "MANU", "FUBO", "VLY", "IQ",
        "HUYA", "DOX", "LUMN", "FYBR", "APP", "IMAX", "MGNI", "TRIP", "YELP", "CARG"
    ]
}


class CandleCollectionService:
    """Orchestrates sector stock cross-evaluation and historical candle collection."""

    def __init__(self):
        self._is_running = False
        self._current_task: Optional[asyncio.Task] = None
        self._in_flight_signal_fetches: set = set()

    def get_cross_evaluated_stock_list(self) -> Dict[str, Any]:
        """
        Cross-evaluates the 50 stocks for each of the 11 sectors against
        the MySQL `available_tickers` whitelist table.

        Returns:
          - Overall metrics (total_sectors, total_target_stocks, matched_in_db, missing_from_db)
          - Sector breakdown with per-stock metadata, DB match status, exchange, and Refinitiv RIC code.
        """
        # Collect all unique tickers across all sectors
        all_tickers = []
        for sector, stocks in SECTOR_UNIVERSE_50.items():
            all_tickers.extend(stocks)
        unique_tickers = list(dict.fromkeys(all_tickers))

        # Query batch from DB available_tickers table
        db_tickers_map = repo.get_available_tickers_batch(unique_tickers)

        sector_results = {}
        total_matched = 0
        total_missing = 0

        for sector, stocks in SECTOR_UNIVERSE_50.items():
            sector_stocks_data = []
            sec_matched = 0
            sec_missing = 0

            for ticker in stocks:
                db_record = db_tickers_map.get(ticker.upper())
                in_db = db_record is not None
                is_active = bool(db_record.get("is_active")) if db_record else False
                exchange = db_record.get("exchange", "NASDAQ") if db_record else "NASDAQ"
                name = db_record.get("name", ticker) if db_record else ticker
                ric = lseg_candle_client.to_ric(ticker, exchange)

                if in_db:
                    sec_matched += 1
                    total_matched += 1
                else:
                    sec_missing += 1
                    total_missing += 1

                sector_stocks_data.append({
                    "ticker": ticker,
                    "name": name,
                    "exchange": exchange,
                    "ric": ric,
                    "in_db": in_db,
                    "is_active": is_active,
                    "strategy": {
                        "year_1": "5 min (Last 365 Days)",
                        "year_2": "1 hour [fallback 1 day] (Days 366-730)",
                        "year_3": "1 hour [fallback 1 day] (Days 731-1095)",
                    }
                })

            sector_results[sector] = {
                "sector_name": sector,
                "target_count": len(stocks),
                "matched_in_db": sec_matched,
                "missing_from_db": sec_missing,
                "stocks": sector_stocks_data,
            }

        return {
            "total_sectors": len(SECTOR_UNIVERSE_50),
            "total_target_stocks": len(all_tickers),
            "matched_in_db": total_matched,
            "missing_from_db": total_missing,
            "sectors": sector_results,
        }

    def collect_stock_candles(
        self,
        ticker: str,
        sector: str,
        exchange: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Collect multi-year candles for a single stock:
          - Year 1: 5min
          - Year 2: 1h -> fallback 1D
          - Year 3: 1h -> fallback 1D
        Saves candles into MySQL and updates candle_collection_jobs.
        """
        clean_ticker = ticker.strip().upper()
        ric = lseg_candle_client.to_ric(clean_ticker, exchange)
        active_job_id = job_id or str(uuid.uuid4())

        repo.save_candle_job(
            job_id=active_job_id,
            sector=sector,
            ticker=clean_ticker,
            ric=ric,
            status="RUNNING",
        )

        try:
            logger.info(f"Starting 3-year collection for {clean_ticker} ({ric}) in sector '{sector}'...")
            res = lseg_candle_client.collect_candles_multi_year(ticker=clean_ticker, exchange=exchange)
            summary = res["summary"]
            bars = res["bars"]

            # Save bars to DB
            inserted = 0
            if bars:
                inserted = repo.upsert_candles(bars)
                logger.info(f"Saved {inserted} candle rows to MySQL for {clean_ticker}.")

            # Update job record in MySQL
            err_msg = "; ".join(summary["errors"]) if summary["errors"] else None
            # Compute accurate overall status
            if len(bars) == 0:
                overall_status = "FAILED" if summary["errors"] else "NO_DATA"
            elif summary["errors"]:
                overall_status = "COMPLETED_WITH_WARNINGS"
            else:
                overall_status = "COMPLETED"

            repo.update_candle_job(
                job_id=active_job_id,
                year_1_status=summary["year_1"]["status"],
                year_1_candles=summary["year_1"]["count"],
                year_2_status=summary["year_2"]["status"],
                year_2_tf=summary["year_2"]["timeframe"],
                year_2_candles=summary["year_2"]["count"],
                year_3_status=summary["year_3"]["status"],
                year_3_tf=summary["year_3"]["timeframe"],
                year_3_candles=summary["year_3"]["count"],
                total_candles=len(bars),
                overall_status=overall_status,
                error_message=err_msg,
                completed_at=datetime.now(timezone.utc),
            )

            return {
                "status": "success",
                "job_id": active_job_id,
                "ticker": clean_ticker,
                "ric": ric,
                "sector": sector,
                "summary": summary,
                "inserted_db_rows": inserted,
            }

        except Exception as ex:
            logger.error(f"Failed candlestick collection for {clean_ticker}: {ex}")
            repo.update_candle_job(
                job_id=active_job_id,
                overall_status="FAILED",
                error_message=str(ex),
                completed_at=datetime.now(timezone.utc),
            )
            return {
                "status": "error",
                "job_id": active_job_id,
                "ticker": clean_ticker,
                "ric": ric,
                "sector": sector,
                "error": str(ex),
            }

    def inspect_ticker_db_status(self, ticker: str) -> Dict[str, Any]:
        """
        Check database FIRST to determine:
          1. When was the ticker last updated (last_synced_at)?
          2. Does the ticker already have full 1-year historical 5m candles in DB?
          3. Whether an external call to LSEG is genuinely required.

        Returns a detailed status dictionary:
          - ticker: str
          - in_db: bool
          - candle_count: int
          - first_date: str | None
          - last_date: str | None
          - last_synced_at: str | None
          - has_1y_history: bool
          - is_recently_synced: bool
          - action_needed: bool
          - fetch_type: str ("none", "full_1_year", "historical_1y_backfill", "incremental_fill")
          - reason: str
          - segments: list of (seg_mode, start_str, end_str)
        """
        clean_ticker = ticker.strip().upper()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        one_year_ago = now - timedelta(days=365)

        coverage = repo.get_candle_coverage(clean_ticker, "5 min")

        # 1. Ticker has NO coverage or 0 candles in DB -> Needs full 1-year historical data
        if not coverage or coverage.get("candle_count", 0) == 0 or not coverage.get("first_date"):
            start_str = one_year_ago.strftime("%Y-%m-%dT00:00:00")
            end_str = now.strftime("%Y-%m-%dT%H:%M:%S")
            return {
                "ticker": clean_ticker,
                "in_db": False,
                "candle_count": 0,
                "first_date": None,
                "last_date": None,
                "last_synced_at": None,
                "has_1y_history": False,
                "is_recently_synced": False,
                "action_needed": True,
                "fetch_type": "full_1_year",
                "reason": f"No 5m candles in DB for {clean_ticker}. Must fetch 1-year history from LSEG.",
                "segments": [("initial_1_year", start_str, end_str)],
            }

        first_dt = coverage["first_date"]
        last_dt = coverage["last_date"]
        last_synced = coverage.get("last_synced_at")
        count = int(coverage.get("candle_count", 0))

        if isinstance(first_dt, str):
            try:
                first_dt = datetime.fromisoformat(first_dt)
            except Exception:
                pass
        if isinstance(last_dt, str):
            try:
                last_dt = datetime.fromisoformat(last_dt)
            except Exception:
                pass
        if isinstance(last_synced, str):
            try:
                last_synced = datetime.fromisoformat(last_synced)
            except Exception:
                pass

        # Check 1: When was it last updated?
        sync_age_seconds = (now - last_synced).total_seconds() if (last_synced and isinstance(last_synced, datetime)) else 999999
        is_recently_synced = sync_age_seconds < 900  # within last 15 minutes

        # Check 2: Does it have 1-year historical data in DB?
        # A full year means first_date starts around 365 days ago (allowing 35-day window for market holidays/weekends)
        # and has at least 1,000 candles.
        has_1y_history = False
        if isinstance(first_dt, datetime):
            has_1y_history = (first_dt <= one_year_ago + timedelta(days=35)) and count >= 1000

        segments = []

        # If historical data is missing in DB (e.g. only 3 months exist), backfill the older portion
        if not has_1y_history and isinstance(first_dt, datetime):
            if (first_dt - one_year_ago).total_seconds() > 86400 * 30:
                hist_start = one_year_ago.strftime("%Y-%m-%dT00:00:00")
                hist_end = first_dt.strftime("%Y-%m-%dT%H:%M:%S")
                segments.append(("historical_1y_backfill", hist_start, hist_end))

        # Check if US market is currently closed on weekends (Saturday=5, Sunday=6)
        is_weekend = now.weekday() in (5, 6)

        # If recently updated within 15 minutes AND 1-year history is present, skip completely
        if is_recently_synced and has_1y_history:
            return {
                "ticker": clean_ticker,
                "in_db": True,
                "candle_count": count,
                "first_date": str(first_dt),
                "last_date": str(last_dt),
                "last_synced_at": str(last_synced) if last_synced else None,
                "has_1y_history": True,
                "is_recently_synced": True,
                "action_needed": False,
                "fetch_type": "none",
                "reason": f"Recently updated ({int(sync_age_seconds)}s ago). Full 1y historical data present in DB ({count} candles).",
                "segments": [],
            }

        # If weekend and we already have 1y history up to Friday market close, market is closed
        if is_weekend and has_1y_history:
            return {
                "ticker": clean_ticker,
                "in_db": True,
                "candle_count": count,
                "first_date": str(first_dt),
                "last_date": str(last_dt),
                "last_synced_at": str(last_synced) if last_synced else None,
                "has_1y_history": True,
                "is_recently_synced": is_recently_synced,
                "action_needed": False,
                "fetch_type": "none",
                "reason": f"Full 1y historical data present in DB ({count} candles) up to Friday close ({last_dt}). Market closed on weekends.",
                "segments": [],
            }

        # If during trading days, check if incremental forward fill is needed
        if isinstance(last_dt, datetime):
            diff_seconds = (now - last_dt).total_seconds()
            if diff_seconds >= 300 and sync_age_seconds >= 300:
                inc_start = last_dt.strftime("%Y-%m-%dT%H:%M:%S")
                inc_end = now.strftime("%Y-%m-%dT%H:%M:%S")
                segments.append(("incremental_fill", inc_start, inc_end))

        if not segments:
            return {
                "ticker": clean_ticker,
                "in_db": True,
                "candle_count": count,
                "first_date": str(first_dt),
                "last_date": str(last_dt),
                "last_synced_at": str(last_synced) if last_synced else None,
                "has_1y_history": has_1y_history,
                "is_recently_synced": is_recently_synced,
                "action_needed": False,
                "fetch_type": "none",
                "reason": f"Already up to date in DB ({count} candles, {first_dt} -> {last_dt}).",
                "segments": [],
            }

        fetch_type = "historical_1y_backfill" if not has_1y_history else "incremental_fill"
        return {
            "ticker": clean_ticker,
            "in_db": True,
            "candle_count": count,
            "first_date": str(first_dt),
            "last_date": str(last_dt),
            "last_synced_at": str(last_synced) if last_synced else None,
            "has_1y_history": has_1y_history,
            "is_recently_synced": is_recently_synced,
            "action_needed": True,
            "fetch_type": fetch_type,
            "reason": (f"Missing full 1-year historical data in DB (only {count} candles since {first_dt})" if not has_1y_history else f"Needs latest incremental fill ({len(segments)} segment)"),
            "segments": segments,
        }

    def collect_5min_candles_for_signal(
        self,
        ticker: str,
        exchange: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Collect 5-minute candles for a ticker (triggered by news or signal).
        FIRST checks the database:
          - If the ticker already has full 1-year historical data and was updated recently,
            skips LSEG pull completely.
          - If the ticker is missing 1-year historical data, fetches it from LSEG.
          - If the ticker has 1-year historical data but is missing recent bars, only fetches
            incremental bars up to now.
        """
        clean_ticker = ticker.strip().upper()

        # Exclude crypto or non-equity symbols
        if "/" in clean_ticker or "+" in clean_ticker or "=" in clean_ticker:
            logger.info(f"[CANDLES] Skipping non-standard equity ticker: {clean_ticker}")
            return {"status": "skipped", "ticker": clean_ticker, "reason": "non_equity_symbol"}

        # 1. Check DB FIRST
        db_status = self.inspect_ticker_db_status(clean_ticker)
        if not db_status["action_needed"]:
            logger.info(f"[CANDLES DB CHECK] {clean_ticker}: {db_status['reason']} -> No LSEG fetch required.")
            return {
                "status": "already_up_to_date",
                "ticker": clean_ticker,
                "candle_count": db_status.get("candle_count", 0),
                "first_date": db_status.get("first_date"),
                "last_date": db_status.get("last_date"),
                "last_synced_at": db_status.get("last_synced_at"),
                "reason": db_status["reason"],
            }

        logger.info(f"[CANDLES DB CHECK] {clean_ticker}: {db_status['reason']} -> Proceeding with LSEG fetch ({db_status['fetch_type']}).")

        if clean_ticker in self._in_flight_signal_fetches:
            logger.info(f"[CANDLES] Fetch already in progress for {clean_ticker}, skipping concurrent duplicate.")
            return {"status": "skipped", "ticker": clean_ticker, "reason": "already_in_progress"}

        self._in_flight_signal_fetches.add(clean_ticker)
        try:
            # Resolve exchange from available_tickers if not provided
            if not exchange:
                db_record = repo.get_available_ticker(clean_ticker)
                if db_record and db_record.get("exchange"):
                    exchange = db_record["exchange"]

            primary_ric = lseg_candle_client.to_ric(clean_ticker, exchange)
            candidate_rics = [primary_ric]
            for suffix in [".O", ".N", ".P"]:
                cand = f"{clean_ticker}{suffix}"
                if cand not in candidate_rics:
                    candidate_rics.append(cand)

            segments_to_fetch = db_status["segments"]
            coverage = repo.get_candle_coverage(clean_ticker, "5 min")

            total_inserted = 0
            total_bars_collected = 0
            modes_executed = []
            final_ric = primary_ric

            for seg_mode, start_str, end_str in segments_to_fetch:
                raw_bars = []
                used_ric = primary_ric
                for candidate in candidate_rics:
                    logger.info(
                        f"[SIGNAL CANDLES] {clean_ticker} ({seg_mode}): Fetching 5-min candles "
                        f"using RIC {candidate} from {start_str} to {end_str}..."
                    )
                    try:
                        raw_bars = lseg_candle_client.fetch_raw_bars(
                            ric=candidate,
                            start_str=start_str,
                            end_str=end_str,
                            interval="5min"
                        )
                        if raw_bars:
                            used_ric = candidate
                            final_ric = candidate
                            break
                    except Exception as try_err:
                        logger.debug(f"RIC candidate {candidate} failed: {try_err}")

                std_bars = lseg_candle_client.standardize_bars(
                    raw_bars,
                    ticker=clean_ticker,
                    ric=used_ric,
                    timeframe="5 min"
                )

                if std_bars:
                    inserted = repo.upsert_candles(std_bars)
                    total_inserted += inserted
                    total_bars_collected += len(std_bars)
                    modes_executed.append(seg_mode)

                    bar_timestamps = [b["timestamp"] for b in std_bars if isinstance(b.get("timestamp"), datetime)]
                    if bar_timestamps:
                        new_min = min(bar_timestamps)
                        new_max = max(bar_timestamps)
                        prev_first = coverage["first_date"] if coverage and coverage.get("first_date") else new_min
                        prev_last = coverage["last_date"] if coverage and coverage.get("last_date") else new_max
                        if isinstance(prev_first, str):
                            prev_first = datetime.fromisoformat(prev_first)
                        if isinstance(prev_last, str):
                            prev_last = datetime.fromisoformat(prev_last)
                        first_date = min(prev_first, new_min)
                        last_date = max(prev_last, new_max)
                        total_count = (coverage.get("candle_count", 0) if coverage else 0) + len(std_bars)
                        repo.update_candle_coverage(
                            ticker=clean_ticker,
                            timeframe="5 min",
                            first_date=first_date,
                            last_date=last_date,
                            candle_count=total_count,
                        )
                        # Update local coverage for subsequent segments
                        coverage = {
                            "ticker": clean_ticker,
                            "timeframe": "5 min",
                            "first_date": first_date,
                            "last_date": last_date,
                            "candle_count": total_count,
                        }
                        logger.info(
                            f"[SIGNAL CANDLES] [OK] Saved {len(std_bars)} 5m bars for {clean_ticker} "
                            f"(Segment: {seg_mode}, Range: {first_date} -> {last_date}, Total: {total_count})"
                        )
                else:
                    logger.info(f"[SIGNAL CANDLES] No 5m bars returned for {clean_ticker} on segment {seg_mode}.")

            if total_bars_collected == 0:
                # If LSEG returned 0 bars across attempted segments (e.g. no intraday data on LSEG, foreign ticker, or delisted),
                # record or touch candle_coverage so it will NOT be repeatedly re-polled in subsequent batches today!
                now_fallback = datetime.now(timezone.utc).replace(tzinfo=None)
                prev_first = coverage["first_date"] if coverage and coverage.get("first_date") else now_fallback
                prev_last = coverage["last_date"] if coverage and coverage.get("last_date") else now_fallback
                if isinstance(prev_first, str):
                    prev_first = datetime.fromisoformat(prev_first)
                if isinstance(prev_last, str):
                    prev_last = datetime.fromisoformat(prev_last)
                prev_count = coverage.get("candle_count", 0) if coverage else 0
                repo.update_candle_coverage(
                    ticker=clean_ticker,
                    timeframe="5 min",
                    first_date=prev_first,
                    last_date=prev_last,
                    candle_count=prev_count,
                )

            return {
                "status": "success",
                "ticker": clean_ticker,
                "ric": final_ric,
                "modes": modes_executed,
                "bars_collected": total_bars_collected,
                "inserted_db_rows": total_inserted,
            }
        except Exception as e:
            logger.error(f"[SIGNAL CANDLES] Error collecting 5m candles for {clean_ticker}: {e}")
            return {
                "status": "error",
                "ticker": clean_ticker,
                "error": str(e)
            }
        finally:
            self._in_flight_signal_fetches.discard(clean_ticker)

    async def run_full_backfill_async(
        self,
        target_sectors: Optional[List[str]] = None,
        db_only: bool = True,
        delay_seconds: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Background worker that iterates through target sectors and stocks,
        executing multi-timeframe candle retrieval and database persistence.
        """
        if self._is_running:
            return {"status": "already_running", "message": "A backfill job is currently executing."}

        self._is_running = True
        cross_eval = self.get_cross_evaluated_stock_list()
        sectors_to_run = target_sectors or list(SECTOR_UNIVERSE_50.keys())

        logger.info(f"[BACKFILL] Starting collection across {len(sectors_to_run)} sectors (db_only={db_only})...")

        total_processed = 0
        total_candles = 0

        try:
            for sec_name in sectors_to_run:
                sec_data = cross_eval["sectors"].get(sec_name)
                if not sec_data:
                    continue

                stocks_list = sec_data["stocks"]
                for s in stocks_list:
                    if db_only and not s["in_db"]:
                        logger.info(f"[BACKFILL] Skipping {s['ticker']} (not in available_tickers).")
                        continue

                    # Execute single stock collection in a worker thread
                    res = await asyncio.to_thread(
                        self.collect_stock_candles,
                        ticker=s["ticker"],
                        sector=sec_name,
                        exchange=s["exchange"],
                    )
                    total_processed += 1
                    total_candles += res.get("summary", {}).get("total_candles", 0)

                    # Polite rate-limiting between successive stocks
                    await asyncio.sleep(delay_seconds)

            logger.info(f"[BACKFILL] Completed backfill: {total_processed} stocks, {total_candles} total candles.")
            return {
                "status": "completed",
                "processed_stocks": total_processed,
                "total_candles": total_candles,
            }
        except Exception as e:
            logger.error(f"[BACKFILL] Error during execution: {e}")
            return {"status": "error", "error": str(e), "processed_stocks": total_processed}
        finally:
            self._is_running = False

    def get_remaining_stocks(self) -> List[Dict[str, Any]]:
        """
        Return the ordered list of stocks across all sectors that have NOT yet
        completed candlestick collection.
        """
        completed = repo.get_completed_candle_tickers()
        cross_eval = self.get_cross_evaluated_stock_list()

        remaining = []
        for sec_name, sec_data in cross_eval["sectors"].items():
            for s in sec_data["stocks"]:
                if s["ticker"].upper() not in completed:
                    remaining.append({
                        "ticker": s["ticker"],
                        "sector": sec_name,
                        "exchange": s["exchange"],
                        "ric": s["ric"],
                    })
        return remaining

    def process_next_batch_sync(
        self,
        batch_size: int = 50,
        delay_seconds: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Synchronously processes the next N uncompleted stocks.
        Suitable for CLI executions, direct scripts, or threadpool tasks.
        """
        remaining = self.get_remaining_stocks()
        if not remaining:
            logger.info("[BATCH] All 550 stocks across all 11 sectors are completed! None left.")
            return {
                "status": "finished",
                "processed_count": 0,
                "remaining_count": 0,
                "message": "All stocks have already completed collection.",
            }

        batch = remaining[:batch_size]
        logger.info(f"[BATCH] Starting batch of {len(batch)} stocks ({len(remaining)} total remaining)...")

        import time
        results = []
        total_candles = 0

        for idx, item in enumerate(batch, 1):
            logger.info(f"[BATCH] [{idx}/{len(batch)}] Collecting candles for {item['ticker']} ({item['sector']})...")
            try:
                res = self.collect_stock_candles(
                    ticker=item["ticker"],
                    sector=item["sector"],
                    exchange=item["exchange"],
                )
                results.append(res)
                c_cnt = res.get("summary", {}).get("total_candles", 0)
                total_candles += c_cnt
                if c_cnt == 0:
                    logger.warning(f"[BATCH] 0 candles collected for {item['ticker']}. Skipping ticker and continuing...")
            except Exception as ex:
                logger.error(f"[BATCH] Error collecting candles for {item['ticker']}: {ex}. Skipping ticker and continuing...")
                results.append({
                    "status": "error",
                    "ticker": item["ticker"],
                    "sector": item["sector"],
                    "error": str(ex),
                })

            time.sleep(delay_seconds)

        new_remaining = self.get_remaining_stocks()
        logger.info(f"[BATCH] Batch finished: {len(batch)} processed, {total_candles} candles added. Remaining: {len(new_remaining)}")

        return {
            "status": "batch_completed",
            "processed_count": len(batch),
            "total_candles": total_candles,
            "remaining_count": len(new_remaining),
            "processed_tickers": [item["ticker"] for item in batch],
            "results": results,
        }

    async def process_next_batch_async(
        self,
        batch_size: int = 50,
        delay_seconds: float = 0.5,
    ) -> Dict[str, Any]:
        """Async wrapper for processing next batch."""
        return await asyncio.to_thread(self.process_next_batch_sync, batch_size, delay_seconds)

    def trigger_next_batch_in_background(self, batch_size: int = 50) -> Dict[str, Any]:
        """Trigger processing of the next batch in background task."""
        if self._is_running:
            return {"status": "already_running", "message": "A backfill or batch job is currently executing."}

        try:
            loop = asyncio.get_running_loop()
            self._current_task = loop.create_task(self.process_next_batch_async(batch_size=batch_size))
        except RuntimeError:
            import threading
            threading.Thread(target=self.process_next_batch_sync, args=(batch_size,), daemon=True).start()

        return {
            "status": "started",
            "message": f"Processing next batch of {batch_size} stocks in the background."
        }

    def trigger_backfill_in_background(
        self,
        target_sectors: Optional[List[str]] = None,
        db_only: bool = True,
    ) -> Dict[str, str]:
        """Trigger backfill task in the background."""
        if self._is_running:
            return {"status": "already_running", "message": "Backfill job is already active in background."}

        try:
            loop = asyncio.get_running_loop()
            self._current_task = loop.create_task(
                self.run_full_backfill_async(target_sectors=target_sectors, db_only=db_only)
            )
        except RuntimeError:
            import threading
            def _runner():
                asyncio.run(self.run_full_backfill_async(target_sectors=target_sectors, db_only=db_only))
            threading.Thread(target=_runner, daemon=True).start()

        return {"status": "started", "message": "Candlestick backfill started in the background."}

    def get_status(self) -> Dict[str, Any]:
        """Fetch live status of the backfill worker and summary of jobs in the database."""
        jobs = repo.get_candle_jobs(limit=100)
        remaining = self.get_remaining_stocks()
        completed = repo.get_completed_candle_tickers()
        return {
            "is_running": self._is_running,
            "total_universe": 550,
            "completed_count": len(completed),
            "remaining_count": len(remaining),
            "recent_jobs_count": len(jobs),
            "recent_jobs": jobs[:20],
        }

    def get_signaled_stocks_remaining(self) -> List[Dict[str, Any]]:
        """
        Return the list of tickers that have generated signals in MySQL
        and need 5-minute candlestick collection (missing, under-covered, or older than 1 day).
        """
        signaled_tickers = repo.get_all_signaled_tickers()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        one_year_ago = now - timedelta(days=365)
        coverage_map = repo.get_all_candle_coverage(timeframe="5 min")

        remaining = []
        for ticker in signaled_tickers:
            cov = coverage_map.get(ticker)
            needs_collection = False
            reason = "missing_coverage"

            if not cov:
                needs_collection = True
                reason = "no_coverage"
            else:
                last_synced = cov.get("last_synced_at")
                if isinstance(last_synced, str):
                    try:
                        last_synced = datetime.fromisoformat(last_synced)
                    except Exception:
                        last_synced = None

                # CRITICAL: If this ticker was already synced or checked within the last 18 hours,
                # skip it completely so we process ONLY fresh, unvisited tickers!
                if last_synced and (now - last_synced).total_seconds() < 18 * 3600:
                    continue

                # If candle_count is 0 and it was already attempted/checked, skip it (no LSEG data)
                candle_count = cov.get("candle_count", 0)
                if candle_count == 0:
                    continue

                first_dt = cov.get("first_date")
                last_dt = cov.get("last_date")

                if isinstance(first_dt, str):
                    try:
                        first_dt = datetime.fromisoformat(first_dt)
                    except Exception:
                        first_dt = None
                if isinstance(last_dt, str):
                    try:
                        last_dt = datetime.fromisoformat(last_dt)
                    except Exception:
                        last_dt = None

                if not first_dt or not last_dt or candle_count < 100:
                    needs_collection = True
                    reason = "insufficient_candles"
                elif (first_dt - one_year_ago).total_seconds() > 86400 * 30:
                    needs_collection = True
                    reason = "missing_1y_historical_depth"
                elif (now - last_dt).total_seconds() >= 86400:
                    needs_collection = True
                    reason = "needs_incremental_fill"

            if needs_collection:
                remaining.append({
                    "ticker": ticker,
                    "reason": reason,
                    "existing_coverage": {
                        "first_date": str(cov.get("first_date")) if cov else None,
                        "last_date": str(cov.get("last_date")) if cov else None,
                        "candle_count": cov.get("candle_count", 0) if cov else 0,
                    } if cov else None
                })

        return remaining

    @property
    def is_running(self) -> bool:
        return self._is_running

    def process_signaled_batch_sync(
        self,
        batch_size: int = 50,
        delay_seconds: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Synchronously processes the next N signaled stocks needing 1-year 5m candles.
        """
        if self._is_running:
            logger.info("[SIGNAL BATCH] A collection job is already running, skipping overlapping batch.")
            return {"status": "already_running", "message": "A collection job is already executing."}

        self._is_running = True
        try:
            remaining = self.get_signaled_stocks_remaining()
            if not remaining:
                logger.info("[SIGNAL BATCH] All signaled stocks have complete up-to-date 1y 5m candles! None left.")
                return {
                    "status": "finished",
                    "processed_count": 0,
                    "remaining_count": 0,
                    "message": "All signaled stocks have already completed 1y 5m candle collection.",
                }

            batch = remaining[:batch_size]
            logger.info(f"[SIGNAL BATCH] Starting batch of {len(batch)} signaled stocks ({len(remaining)} total remaining)...")

            import time
            results = []
            total_candles = 0

            for idx, item in enumerate(batch, 1):
                ticker = item["ticker"]
                logger.info(f"[SIGNAL BATCH] [{idx}/{len(batch)}] Collecting 1y 5m candles for signaled stock {ticker} ({item['reason']})...")
                try:
                    res = self.collect_5min_candles_for_signal(ticker=ticker)
                    results.append(res)
                    c_cnt = res.get("bars_collected", 0)
                    total_candles += c_cnt
                except Exception as ex:
                    logger.error(f"[SIGNAL BATCH] Error collecting candles for {ticker}: {ex}")
                    results.append({
                        "status": "error",
                        "ticker": ticker,
                        "error": str(ex),
                    })

                time.sleep(delay_seconds)

            new_remaining = self.get_signaled_stocks_remaining()
            logger.info(f"[SIGNAL BATCH] Batch finished: {len(batch)} processed, {total_candles} candles added. Remaining: {len(new_remaining)}")

            return {
                "status": "batch_completed",
                "processed_count": len(batch),
                "total_candles": total_candles,
                "remaining_count": len(new_remaining),
                "processed_tickers": [item["ticker"] for item in batch],
                "results": results,
            }
        finally:
            self._is_running = False

    async def process_signaled_batch_async(
        self,
        batch_size: int = 50,
        delay_seconds: float = 0.5,
    ) -> Dict[str, Any]:
        """Async wrapper for processing signaled stocks batch."""
        return await asyncio.to_thread(self.process_signaled_batch_sync, batch_size, delay_seconds)

    def trigger_signaled_batch_in_background(self, batch_size: int = 50) -> Dict[str, Any]:
        """Trigger processing of the signaled stocks batch in background task."""
        if self._is_running:
            return {"status": "already_running", "message": "A backfill or batch job is currently executing."}

        try:
            loop = asyncio.get_running_loop()
            self._current_task = loop.create_task(self.process_signaled_batch_async(batch_size=batch_size))
        except RuntimeError:
            import threading
            threading.Thread(target=self.process_signaled_batch_sync, args=(batch_size,), daemon=True).start()

        return {
            "status": "started",
            "message": f"Processing next batch of {batch_size} signaled stocks (1y 5m candles) in the background."
        }


# Central service singleton
candle_collection_service = CandleCollectionService()
