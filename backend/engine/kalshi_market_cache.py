import asyncio
import base64
import json
import logging
import os
import re
import sqlite3
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Set

import requests
import websockets
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

logger = logging.getLogger("kalshi_market_cache")

# Flag controlling market cache usage
USE_MARKET_CACHE = os.getenv("USE_MARKET_CACHE", "1").lower() in ("1", "true", "yes")

WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
REST_BASE_URL = "https://external-api.kalshi.com"
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "kalshi_markets_cache.db")


class TokenBucket:
    """Token-bucket rate limiter to strictly cap REST requests per second."""
    def __init__(self, capacity: float = 20.0, fill_rate: float = 18.0):
        self.capacity = capacity
        self.fill_rate = fill_rate
        self.tokens = capacity
        self.last_update = time.time()
        self._lock = threading.Lock()

    def acquire(self, tokens: float = 1.0):
        while True:
            with self._lock:
                now = time.time()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.fill_rate)
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                wait_time = (tokens - self.tokens) / self.fill_rate
            time.sleep(max(0.01, wait_time))


_FINANCIAL_SERIES_PREFIXES = (
    "KXBTC", "KXETH", "KXSOL", "KXDOGE", "KXINX", "KXNASDAQ", "KXGOLD",
    "KXEURUSD", "KXGBPUSD", "KXUSDJPY", "KXAUDUSD", "KXMVE",
)
_EXACT_SPORTS_SERIES = frozenset({
    "KXNPBGAME", "KXNPBSPREAD", "KXNPBTOTAL",
    "KXKBOGAME", "KXKBOSPREAD", "KXKBOTOTAL",
    "KXNFLSPREAD", "KXNFLTOTAL", "KXNFLWINS", "KXNFLGAME", "KXNFLTD", "KXNFLPASS", "KXNFLRUSH", "KXNFLREC",
    "KXNFLRSHYDS", "KXNFLPASSYDS", "KXNFLRECYDS", "KXNFLFIRSTTD",
    "KXMLBGAME", "KXMLBSPREAD", "KXMLBTOTAL", "KXMLBF5", "KXMLBHRR",
    "KXMLBHR", "KXMLBKS", "KXMLBTB", "KXMLBHIT", "KXMLBRBI",
    "KXNHLGAME", "KXNHLSPREAD", "KXNHLTOTAL", "KXNHLTEAMTOTAL", "KXNHLF10G",
    "KXNHL1P", "KXNHL2P", "KXNHL3P", "KXNHL1PSPREAD", "KXNHL2PSPREAD", "KXNHL3PSPREAD",
    "KXNHL1PTOTAL", "KXNHL2PTOTAL", "KXNHL3PTOTAL", "KXNHLOT",
    "KXNHLGOAL", "KXNHLAST", "KXNHLPTS", "KXNHLFIRSTGOAL", "KXNHLSAVE",
    "KXEPLGAME", "KXMLSGAME", "KXUEFAGAME", "KXUCLGAME", "KXWC", "KXBUNDESLIGA", "KXLALIGA",
    "KXMLSTOTAL", "KXUCLTOTAL", "KXEPLTOTAL", "KXLALIGATOTAL", "KXBUNDESLIGATOTAL", "KXSERIEATOTAL",
    "KXLIGUE1TOTAL", "KXLIGAMXTOTAL", "KXEFLCHAMPIONSHIPTOTAL", "KXUSLTOTAL", "KXCONMEBOLLIBTOTAL",
    "KXCONMEBOLSUDTOTAL", "KXARGPREMDIVTOTAL", "KXDIMAYORTOTAL", "KXBRASILEIROTOTAL", "KXEREDIVISIETOTAL",
    "KXSAUDIPLTOTAL", "KXSCOTTISHPREMTOTAL", "KXUELTOTAL", "KXUECLTOTAL",
    "KXMLS1HTOTAL", "KXMLS2HTOTAL", "KXMLSTEAMTOTAL",
    "KXEFLCHAMPIONSHIP1HTOTAL", "KXEFLCHAMPIONSHIP2HTOTAL", "KXEFLCHAMPIONSHIPTEAMTOTAL",
    "KXUCL1HTOTAL", "KXUCL2HTOTAL", "KXUCLTEAMTOTAL",
    "KXCONMEBOLLIB1HTOTAL", "KXCONMEBOLLIB2HTOTAL", "KXCONMEBOLLIBTEAMTOTAL",
    "KXCONMEBOLSUD1HTOTAL", "KXARGPREMDIV1HTOTAL", "KXUSL1HTOTAL",
    "KXEPL1HTOTAL", "KXEPL2HTOTAL", "KXEPLTEAMTOTAL",
    "KXLALIGA1HTOTAL", "KXLALIGA2HTOTAL", "KXLALIGATEAMTOTAL",
    "KXBUNDESLIGA1HTOTAL", "KXBUNDESLIGA2HTOTAL", "KXBUNDESLIGATEAMTOTAL",
    "KXSERIEA1HTOTAL", "KXSERIEA2HTOTAL", "KXSERIEATEAMTOTAL",
    "KXLIGUE11HTOTAL", "KXLIGUE12HTOTAL", "KXLIGUE1TEAMTOTAL",
    "KXEPLBTTS", "KXEPLCORNERS", "KXEPLFTTS", "KXEPLSCORE",
    "KXMLSBTTS", "KXMLSCORNERS", "KXMLSFTTS", "KXMLSSCORE",
    "KXUFCMIDDLEWEIGHTTITLE", "KXUFCLHEAVYWEIGHTTITLE", "KXUFCBANTAMWEIGHTTITLE", "KXUFCFIGHT", "KXUFC",
    "KXUFCDISTANCE", "KXUFCMOF", "KXUFCMOV", "KXUFCVICROUND",
    "KXATPMATCH", "KXWTAMATCH", "KXATP", "KXWTA",
    "KXNBAGAME", "KXNBASPREAD", "KXNBATOTAL", "KXNBAPTS", "KXNBAREB", "KXNBAAST", "KXNBATHREE", "KXNBA3PT", "KXNBABLK", "KXNBASTL",
    "KXNCAAFGAME", "KXNCAAFSPREAD", "KXNCAAFTOTAL",
})


class KalshiMarketCache:
    """
    In-memory live market cache for Kalshi.
    - Filtered strictly to supported Financial & Sports series (~27,000 markets instead of 184,000+ unrelated markets).
    - Real-time updates via Kalshi WebSocket v2 ('ticker' & 'market_lifecycle_v2').
    - Persistent SQLite backing for instantaneous boot (<1.5s) on restart.
    """
    _instance = None
    _singleton_lock = threading.Lock()

    @staticmethod
    def _is_relevant_series(series_ticker: str) -> bool:
        st = str(series_ticker or "").upper()
        if not st:
            return False
        return (st in _EXACT_SPORTS_SERIES) or st.startswith(_FINANCIAL_SERIES_PREFIXES)

    @classmethod
    def _is_relevant_ticker(cls, ticker: str) -> bool:
        tkr = str(ticker or "").upper()
        if not tkr:
            return False
        st = tkr.split("-")[0]
        return cls._is_relevant_series(st)

    @classmethod
    def get_instance(cls):
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self._lock = threading.RLock()
        
        # Primary In-Memory Indices
        self._markets: Dict[str, Dict[str, Any]] = {}
        self._by_event: Dict[str, List[Dict[str, Any]]] = {}
        self._by_series: Dict[str, List[Dict[str, Any]]] = {}
        
        # Sports Events and Milestones
        self._milestones: Dict[str, Dict[str, Any]] = {}
        self._last_milestone_fetch = 0.0
        
        # Diagnostics and Status
        self._last_snapshot_at: Optional[str] = None
        self._last_snapshot_time: float = 0.0
        self._snapshot_seconds: float = 0.0
        self._ws_connected: bool = False
        self._last_ws_msg_time: float = 0.0
        self._resyncs: int = 0
        self._updates_window: deque = deque(maxlen=5000)    # bounded 60s update window
        self._rest_429s: deque = deque(maxlen=250)          # timestamps of 429 errors in last hour
        
        # Sequence tracking
        self._last_seq_per_sid: Dict[int, int] = {}
        
        # Rate Limiting & REST Session
        self._limiter = TokenBucket(capacity=20.0, fill_rate=18.0)
        self._session = requests.Session()
        from requests.adapters import HTTPAdapter
        adapter = HTTPAdapter(pool_connections=12, pool_maxsize=24, max_retries=0)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
        
        # Background worker management
        self._started = False
        self._is_snapshotting = False
        self._ws_thread: Optional[threading.Thread] = None

        # Ensure database directory exists
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self._init_sqlite()
        try:
            self.load_from_sqlite()
        except Exception as e:
            logger.warning(f"[MarketCache] Initial sqlite load warning: {e}")

    # ---------------------------------------------------------
    # SQLite Persistence Layer
    # ---------------------------------------------------------
    def _init_sqlite(self):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS kalshi_markets (
                        ticker TEXT PRIMARY KEY,
                        event_ticker TEXT,
                        series_ticker TEXT,
                        title TEXT,
                        yes_sub_title TEXT,
                        no_sub_title TEXT,
                        floor_strike REAL,
                        strike_type TEXT,
                        custom_strike TEXT,
                        status TEXT,
                        open_time TEXT,
                        close_time TEXT,
                        expected_expiration_time TEXT,
                        yes_bid REAL,
                        yes_ask REAL,
                        no_bid REAL,
                        no_ask REAL,
                        last_price REAL,
                        volume REAL,
                        volume_24h REAL,
                        open_interest REAL,
                        updated_ts REAL,
                        paused INTEGER DEFAULT 0
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_mkt_event ON kalshi_markets(event_ticker)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_mkt_series ON kalshi_markets(series_ticker)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_mkt_close ON kalshi_markets(close_time)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_mkt_status ON kalshi_markets(status)")
                conn.commit()
        except Exception as e:
            logger.error(f"[MarketCache] Failed to initialize SQLite cache table: {e}")

    def load_from_sqlite(self) -> int:
        """Loads previous non-expired Financial & Sports snapshot from SQLite immediately on boot."""
        try:
            t0 = time.time()
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            with sqlite3.connect(DB_PATH, timeout=15.0) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM kalshi_markets WHERE status IN ('active', 'open') AND (close_time IS NULL OR close_time = '' OR close_time >= ?)",
                    (now_iso,)
                ).fetchall()
                
            markets = {}
            by_event = {}
            by_series = {}
            
            for r in rows:
                st = r["series_ticker"] or ""
                if not self._is_relevant_series(st):
                    continue
                d = dict(r)
                d["paused"] = bool(d.get("paused", 0))
                tkr = d["ticker"]
                markets[tkr] = d
                
                et = d.get("event_ticker")
                if et:
                    by_event.setdefault(et, []).append(d)
                if st:
                    by_series.setdefault(st, []).append(d)
                    
            if markets:
                with self._lock:
                    self._markets = markets
                    self._by_event = by_event
                    self._by_series = by_series
                    self._last_snapshot_at = "Loaded from SQLite"
                    self._last_snapshot_time = time.time()
                logger.info(f"[MarketCache] Loaded {len(markets)} warm markets from SQLite in {time.time()-t0:.2f}s.")
                return len(markets)
        except Exception as e:
            logger.warning(f"[MarketCache] Could not load from SQLite: {e}")
        return 0

    def _persist_to_sqlite(self, markets_list: List[Dict[str, Any]]):
        """Batch-writes relevant markets to SQLite and prunes expired markets."""
        try:
            filtered_list = [m for m in markets_list if self._is_relevant_series(m.get("series_ticker") or "")]
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            with sqlite3.connect(DB_PATH, timeout=30.0) as conn:
                conn.execute("BEGIN TRANSACTION")
                conn.execute("DELETE FROM kalshi_markets WHERE close_time IS NOT NULL AND close_time != '' AND close_time < ?", (now_iso,))
                conn.executemany("""
                    INSERT OR REPLACE INTO kalshi_markets (
                        ticker, event_ticker, series_ticker, title, yes_sub_title, no_sub_title,
                        floor_strike, strike_type, custom_strike, status, open_time, close_time,
                        expected_expiration_time, yes_bid, yes_ask, no_bid, no_ask, last_price,
                        volume, volume_24h, open_interest, updated_ts, paused
                    ) VALUES (
                        :ticker, :event_ticker, :series_ticker, :title, :yes_sub_title, :no_sub_title,
                        :floor_strike, :strike_type, :custom_strike, :status, :open_time, :close_time,
                        :expected_expiration_time, :yes_bid, :yes_ask, :no_bid, :no_ask, :last_price,
                        :volume, :volume_24h, :open_interest, :updated_ts, :paused
                    )
                """, filtered_list)
                conn.commit()
            logger.debug(f"[MarketCache] Persisted {len(filtered_list)} markets to SQLite.")
        except Exception as e:
            logger.error(f"[MarketCache] Error persisting snapshot to SQLite: {e}")

    # ---------------------------------------------------------
    # Parsing Helpers
    # ---------------------------------------------------------
    @staticmethod
    def _parse_market_dict(m: Dict[str, Any]) -> Dict[str, Any]:
        """Parses a raw market object from REST or WS into the canonical schema."""
        ticker = m.get("ticker") or m.get("market_ticker") or ""
        event_ticker = m.get("event_ticker") or ""
        series_ticker = event_ticker.split("-")[0] if "-" in event_ticker else (m.get("series_ticker") or ticker.split("-")[0])
        
        # Primary: dollars strings -> float, fallback to cents / 100.0
        def to_float(val, fallback_cents=None):
            if val is not None and str(val).strip() != "":
                try: return float(val)
                except (ValueError, TypeError): pass
            if fallback_cents is not None:
                try: return float(fallback_cents) / 100.0
                except (ValueError, TypeError): pass
            return 0.0

        yes_bid = to_float(m.get("yes_bid_dollars"), m.get("yes_bid"))
        yes_ask = to_float(m.get("yes_ask_dollars"), m.get("yes_ask"))
        no_bid = to_float(m.get("no_bid_dollars"), m.get("no_bid"))
        no_ask = to_float(m.get("no_ask_dollars"), m.get("no_ask"))
        last_price = to_float(m.get("last_price_dollars"), m.get("last_price") or m.get("price"))

        # Derive NO side if not directly provided
        if yes_bid > 0 and (no_ask == 0.0 or no_ask == 1.0):
            no_ask = round(1.0 - yes_bid, 4)
        if yes_ask > 0 and (no_bid == 0.0 or no_bid == 1.0):
            no_bid = round(1.0 - yes_ask, 4)

        # Volumes
        volume = to_float(m.get("volume_fp"), m.get("volume"))
        volume_24h = to_float(m.get("volume_24h_fp"), m.get("volume_24h"))
        open_interest = to_float(m.get("open_interest_fp"), m.get("open_interest"))

        # Strike info
        floor_strike = None
        if m.get("floor_strike") is not None:
            try: floor_strike = float(m["floor_strike"])
            except: pass

        custom_strike_val = m.get("custom_strike")
        if isinstance(custom_strike_val, (dict, list)):
            custom_strike = json.dumps(custom_strike_val)
        else:
            custom_strike = str(custom_strike_val) if custom_strike_val is not None else None

        now_ts = time.time()
        updated_ts = now_ts
        if m.get("updated_time"):
            try:
                dt = datetime.fromisoformat(m["updated_time"].replace("Z", "+00:00"))
                updated_ts = dt.timestamp()
            except:
                pass
        elif m.get("ts_ms"):
            updated_ts = float(m["ts_ms"]) / 1000.0

        status = str(m.get("status") or "active").lower()

        return {
            "ticker": ticker,
            "event_ticker": event_ticker,
            "series_ticker": series_ticker,
            "title": m.get("title") or "",
            "yes_sub_title": m.get("yes_sub_title") or "",
            "no_sub_title": m.get("no_sub_title") or "",
            "floor_strike": floor_strike,
            "strike_type": m.get("strike_type") or "",
            "custom_strike": custom_strike,
            "status": status,
            "open_time": m.get("open_time") or "",
            "close_time": m.get("close_time") or "",
            "expected_expiration_time": m.get("expected_expiration_time") or m.get("latest_expiration_time") or "",
            "yes_bid": yes_bid,
            "yes_ask": yes_ask,
            "no_bid": no_bid,
            "no_ask": no_ask,
            "last_price": last_price,
            "volume": volume,
            "volume_24h": volume_24h,
            "open_interest": open_interest,
            "updated_ts": updated_ts,
            "paused": False
        }

    # ---------------------------------------------------------
    # REST Snapshot Fetcher
    # ---------------------------------------------------------
    def fetch_snapshot(self) -> bool:
        """
        Executes an authenticated REST snapshot across all open single markets.
        Paginates using cursor with token-bucket limiter and exponential backoff.
        Target: < 15 s.
        """
        if self._is_snapshotting:
            logger.info("[MarketCache] Snapshot already in progress. Skipping.")
            return False

        self._is_snapshotting = True
        t0 = time.time()
        logger.info("[MarketCache] Starting full REST market snapshot...")

        try:
            from backend.btc.kalshi_trader import kalshi_trader
            if not kalshi_trader or not kalshi_trader.is_authenticated():
                logger.error("[MarketCache] Cannot fetch snapshot: kalshi_trader unauthenticated.")
                self._is_snapshotting = False
                return False

            path = "/trade-api/v2/markets"
            cursor = None
            page = 0
            all_parsed: Dict[str, Dict[str, Any]] = {}
            by_event: Dict[str, List[Dict[str, Any]]] = {}
            by_series: Dict[str, List[Dict[str, Any]]] = {}

            while True:
                self._limiter.acquire(1.0)
                page += 1

                params = {
                    "status": "open",
                    "limit": 1000,
                    "mve_filter": "exclude"
                }
                if cursor:
                    params["cursor"] = cursor

                # Retry loop with exponential backoff on 429/5xx
                resp = None
                backoff = 0.5
                for attempt in range(4):
                    try:
                        headers = kalshi_trader._sign_headers("GET", path)
                        resp = self._session.get(
                            f"{REST_BASE_URL}{path}",
                            params=params,
                            headers=headers,
                            timeout=8.0
                        )
                        if resp.status_code == 200:
                            break
                        elif resp.status_code == 429:
                            self._rest_429s.append(time.time())
                            logger.warning(f"[MarketCache] Rate limit 429 on page {page}, attempt {attempt+1}. Retrying in {backoff:.2f}s...")
                            time.sleep(backoff)
                            backoff *= 2.0
                        elif resp.status_code in (500, 502, 503, 504):
                            time.sleep(backoff)
                            backoff *= 2.0
                        else:
                            logger.error(f"[MarketCache] Unexpected HTTP {resp.status_code} on page {page}: {resp.text}")
                            break
                    except Exception as req_err:
                        time.sleep(backoff)
                        backoff *= 2.0

                if not resp or resp.status_code != 200:
                    logger.error(f"[MarketCache] Failed to fetch page {page}. Snapshot aborted.")
                    self._is_snapshotting = False
                    return False

                data = resp.json()
                raw_markets = data.get("markets", [])
                
                for rm in raw_markets:
                    raw_tkr = rm.get("ticker") or rm.get("market_ticker") or ""
                    if not self._is_relevant_ticker(raw_tkr):
                        continue
                    parsed = self._parse_market_dict(rm)
                    tkr = parsed["ticker"]
                    if tkr and self._is_relevant_series(parsed.get("series_ticker") or ""):
                        all_parsed[tkr] = parsed
                        et = parsed["event_ticker"]
                        if et:
                            by_event.setdefault(et, []).append(parsed)
                        st = parsed["series_ticker"]
                        if st:
                            by_series.setdefault(st, []).append(parsed)

                cursor = data.get("cursor")
                if not cursor:
                    break

            snapshot_duration = time.time() - t0
            iso_now = datetime.now(timezone.utc).isoformat()

            # Swap in-memory tables atomically
            with self._lock:
                self._markets = all_parsed
                self._by_event = by_event
                self._by_series = by_series
                self._last_snapshot_at = iso_now
                self._last_snapshot_time = time.time()
                self._snapshot_seconds = round(snapshot_duration, 2)

            logger.info(
                f"[MarketCache] Full snapshot complete: {len(all_parsed)} open markets "
                f"across {page} pages in {snapshot_duration:.2f}s."
            )

            # Persist to SQLite in background
            threading.Thread(
                target=self._persist_to_sqlite,
                args=(list(all_parsed.values()),),
                daemon=True,
                name="KalshiSQLitePersist"
            ).start()

            self._is_snapshotting = False
            return True

        except Exception as e:
            logger.error(f"[MarketCache] Exception during snapshot fetch: {e}")
            self._is_snapshotting = False
            return False

    # ---------------------------------------------------------
    # Single Market REST Fetcher
    # ---------------------------------------------------------
    def fetch_single_market(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetches a single market by REST (e.g. upon 'created' lifecycle event)."""
        try:
            from backend.btc.kalshi_trader import kalshi_trader
            if not kalshi_trader or not kalshi_trader.is_authenticated():
                return None
            path = f"/trade-api/v2/markets/{ticker}"
            headers = kalshi_trader._sign_headers("GET", path)
            r = self._session.get(f"{REST_BASE_URL}{path}", headers=headers, timeout=5.0)
            if r.status_code == 200:
                raw = r.json().get("market")
                if raw:
                    parsed = self._parse_market_dict(raw)
                    with self._lock:
                        tkr = parsed["ticker"]
                        self._markets[tkr] = parsed
                        et = parsed["event_ticker"]
                        if et:
                            self._by_event.setdefault(et, []).append(parsed)
                        st = parsed["series_ticker"]
                        if st:
                            self._by_series.setdefault(st, []).append(parsed)
                    return parsed
        except Exception as e:
            logger.debug(f"[MarketCache] fetch_single_market failed for {ticker}: {e}")
        return None

    # ---------------------------------------------------------
    # Sports Milestones and Events Cache
    # ---------------------------------------------------------
    def update_milestones_and_sports(self):
        """Refreshes sports milestone metadata every 10 min."""
        try:
            now = time.time()
            if now - self._last_milestone_fetch < 300 and self._milestones:
                return

            from datetime import timedelta
            start_iso = (datetime.now(timezone.utc) - timedelta(hours=36)).strftime("%Y-%m-%dT%H:%M:%SZ")
            m_map = {}
            cursor = None
            for _ in range(12):
                url = f"{REST_BASE_URL}/trade-api/v2/milestones?limit=500&category=Sports&minimum_start_date={start_iso}"
                if cursor:
                    url += f"&cursor={cursor}"
                r = self._session.get(url, timeout=10.0)
                if r.status_code != 200:
                    break
                data = r.json()
                ms = data.get("milestones", [])
                for m in ms:
                    mid = m.get("id") or m.get("milestone_id")
                    if mid:
                        m_map[mid] = m
                    for ev in m.get("primary_event_tickers", []) or []:
                        m_map[ev] = m
                        if "-" in ev:
                            suf = ev.split("-", 1)[1]
                            if suf and f"SUFFIX:{suf}" not in m_map:
                                m_map[f"SUFFIX:{suf}"] = m
                    for ev in m.get("related_event_tickers", []) or []:
                        m_map[ev] = m
                        if "-" in ev:
                            suf = ev.split("-", 1)[1]
                            if suf and f"SUFFIX:{suf}" not in m_map:
                                m_map[f"SUFFIX:{suf}"] = m
                    details = m.get("details", {})
                    if isinstance(details, dict):
                        main_tk = details.get("main_game_event_ticker")
                        if main_tk:
                            m_map[main_tk] = m
                            if "-" in main_tk:
                                suf = main_tk.split("-", 1)[1]
                                if suf:
                                    m_map[f"SUFFIX:{suf}"] = m
                cursor = data.get("cursor")
                if not cursor or not ms:
                    break

            with self._lock:
                self._milestones = m_map
                self._last_milestone_fetch = now
            logger.info(f"[MarketCache] Updated {len(m_map)} sports milestones.")
        except Exception as e:
            logger.debug(f"[MarketCache] Milestone fetch error: {e}")

    # ---------------------------------------------------------
    # Live WebSocket Feed Loop
    # ---------------------------------------------------------
    async def _ws_loop(self):
        """Asynchronous WebSocket client loop with auto-reconnection and delta resync."""
        from backend.btc.kalshi_trader import kalshi_trader
        backoff = 1.0

        while True:
            try:
                if not kalshi_trader or not kalshi_trader.is_authenticated():
                    logger.warning("[MarketCache] WebSocket waiting for Kalshi credentials...")
                    await asyncio.sleep(5)
                    continue

                # 1. Sign WebSocket handshake headers
                timestamp = str(int(time.time() * 1000))
                msg_string = timestamp + "GET" + "/trade-api/ws/v2"
                signature = kalshi_trader._private_key_obj.sign(
                    msg_string.encode("utf-8"),
                    padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                    hashes.SHA256()
                )
                headers = {
                    "KALSHI-ACCESS-KEY": kalshi_trader.key_id,
                    "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("utf-8"),
                    "KALSHI-ACCESS-TIMESTAMP": timestamp
                }

                logger.info(f"[MarketCache] Connecting to WebSocket: {WS_URL}...")
                import inspect
                ws_kwargs = {"ping_interval": 20, "ping_timeout": 20}
                if "additional_headers" in inspect.signature(websockets.connect).parameters:
                    ws_kwargs["additional_headers"] = headers
                else:
                    ws_kwargs["extra_headers"] = headers

                async with websockets.connect(WS_URL, **ws_kwargs) as ws:
                    self._active_ws = ws
                    self._ws_loop_obj = asyncio.get_running_loop()
                    self._ws_connected = True
                    backoff = 1.0
                    logger.info("[MarketCache] Connected & Authenticated to Kalshi v2 WebSocket!")

                    # 2. Subscribe to 'ticker' and 'market_lifecycle_v2' with NO market list (receives all markets)
                    sub_msg = {
                        "id": int(time.time() * 1000),
                        "cmd": "subscribe",
                        "params": {
                            "channels": ["ticker", "market_lifecycle_v2"]
                        }
                    }
                    await ws.send(json.dumps(sub_msg))
                    logger.info("[MarketCache] Subscribed to channels: ['ticker', 'market_lifecycle_v2'] (full market stream).")

                    # 3. Message receiver loop
                    while True:
                        try:
                            # 60-second inactivity check
                            raw_msg = await asyncio.wait_for(ws.recv(), timeout=60.0)
                        except asyncio.TimeoutError:
                            logger.warning("[MarketCache] No WebSocket message received for 60s. Reconnecting & resyncing...")
                            break

                        now_ts = time.time()
                        self._last_ws_msg_time = now_ts
                        data = json.loads(raw_msg)
                        msg_type = data.get("type")
                        sid = data.get("sid", 0)
                        seq = data.get("seq")

                        # Sequence gap tracking
                        if seq is not None and sid:
                            last_seq = self._last_seq_per_sid.get(sid)
                            if last_seq is not None and seq > last_seq + 1:
                                logger.warning(f"[MarketCache] Sequence gap detected on sid {sid} (got {seq}, expected {last_seq+1}). Triggering delta resync.")
                                self._resyncs += 1
                                threading.Thread(target=self.fetch_snapshot, daemon=True).start()
                            self._last_seq_per_sid[sid] = seq

                        # Route message
                        if msg_type == "ticker":
                            msg = data.get("msg", {})
                            tkr = msg.get("market_ticker")
                            if tkr:
                                self._on_ws_ticker_update(tkr, msg, now_ts)
                        elif msg_type == "market_lifecycle_v2":
                            msg = data.get("msg", {})
                            self._on_ws_lifecycle_event(msg)
                        elif msg_type == "subscribed":
                            logger.debug(f"[MarketCache] Subscription acknowledged: {data}")
                        elif msg_type == "error":
                            logger.error(f"[MarketCache] WebSocket error received: {data}")

            except Exception as e:
                self._ws_connected = False
                logger.warning(f"[MarketCache] WebSocket disconnected ({e}). Reconnecting in {backoff:.1f}s...")
                self._resyncs += 1
                await asyncio.sleep(backoff)
                backoff = min(30.0, backoff * 2.0)
                # Run background snapshot to fill any gap during disconnect
                threading.Thread(target=self.fetch_snapshot, daemon=True).start()

    def _on_ws_ticker_update(self, ticker: str, msg: Dict[str, Any], now_ts: float):
        """Applies in-place ticker update and derives NO side."""
        self._updates_window.append(now_ts)
        
        with self._lock:
            m = self._markets.get(ticker)
            if not m:
                # If market not present in open cache, ignore or add skeleton
                return

            if "price_dollars" in msg and msg["price_dollars"] is not None:
                try: m["last_price"] = float(msg["price_dollars"])
                except: pass
            if "yes_bid_dollars" in msg and msg["yes_bid_dollars"] is not None:
                try:
                    yb = float(msg["yes_bid_dollars"])
                    m["yes_bid"] = yb
                    if yb > 0:
                        m["no_ask"] = round(1.0 - yb, 4)
                except: pass
            if "yes_ask_dollars" in msg and msg["yes_ask_dollars"] is not None:
                try:
                    ya = float(msg["yes_ask_dollars"])
                    m["yes_ask"] = ya
                    if ya > 0:
                        m["no_bid"] = round(1.0 - ya, 4)
                except: pass
            if "volume_fp" in msg and msg["volume_fp"] is not None:
                try: m["volume"] = float(msg["volume_fp"])
                except: pass
            if "open_interest_fp" in msg and msg["open_interest_fp"] is not None:
                try: m["open_interest"] = float(msg["open_interest_fp"])
                except: pass
            m["updated_ts"] = now_ts

    def _on_ws_lifecycle_event(self, msg: Dict[str, Any]):
        """Handles market_lifecycle_v2 updates."""
        event_type = msg.get("event_type")
        ticker = msg.get("market_ticker")
        if not ticker or not self._is_relevant_ticker(ticker):
            return

        logger.info(f"[MarketCache] Market lifecycle event: {event_type} on {ticker}")

        if event_type == "created":
            # Fetch single market via REST and insert
            threading.Thread(target=self.fetch_single_market, args=(ticker,), daemon=True).start()

        elif event_type == "close_date_updated":
            close_time = msg.get("close_time") or msg.get("close_ts")
            with self._lock:
                m = self._markets.get(ticker)
                if m and close_time:
                    m["close_time"] = str(close_time)

        elif event_type in ("determined", "settled"):
            with self._lock:
                m = self._markets.get(ticker)
                if m:
                    m["status"] = "closed"
                    # Remove from open lists
                    et = m.get("event_ticker")
                    if et and et in self._by_event:
                        self._by_event[et] = [x for x in self._by_event[et] if x.get("ticker") != ticker]
                    st = m.get("series_ticker")
                    if st and st in self._by_series:
                        self._by_series[st] = [x for x in self._by_series[st] if x.get("ticker") != ticker]

            # Fire immediate asynchronous settlement pass for concluded market.
            # Debounced: a burst of settle events (e.g. hourly crypto strikes) coalesces
            # into a single run instead of spawning one thread per event.
            def _trigger_instant_settlement():
                time.sleep(5.0)  # let the burst finish
                self._settle_pending = False
                try:
                    from backend.saas_settler import settle_saas_trades
                    settle_saas_trades(blocking=False)
                except Exception as _se:
                    logger.debug(f"[MarketCache] Instant SaaS settlement trigger: {_se}")
                try:
                    from backend.sports_bridge.executor import SportsBridgeExecutor
                    SportsBridgeExecutor().settle_all_open_trades()
                except Exception as _spe:
                    logger.debug(f"[MarketCache] Instant Sports settlement trigger: {_spe}")

            if not getattr(self, "_settle_pending", False):
                self._settle_pending = True
                threading.Thread(target=_trigger_instant_settlement, daemon=True, name="InstantWsSettler").start()

        elif event_type == "deactivated":
            with self._lock:
                m = self._markets.get(ticker)
                if m: m["paused"] = True

        elif event_type == "activated":
            with self._lock:
                m = self._markets.get(ticker)
                if m: m["paused"] = False

        elif event_type == "metadata_updated":
            threading.Thread(target=self.fetch_single_market, args=(ticker,), daemon=True).start()

    # ---------------------------------------------------------
    # Public Cache Accessors & Diagnostic Status
    # ---------------------------------------------------------
    def is_cache_healthy(self) -> bool:
        """Evaluates whether the market cache is sufficiently warm and healthy."""
        with self._lock:
            has_markets = len(self._markets) >= 1000
            snapshot_fresh = (time.time() - self._last_snapshot_time) < 86400
            ws_ok = self._ws_connected or (time.time() - self._last_ws_msg_time < 120.0) or (self._last_snapshot_time > 0 and (time.time() - self._last_snapshot_time < 3600))
            return bool(has_markets and snapshot_fresh and ws_ok)

    def get_cache_status(self) -> Dict[str, Any]:
        """Returns JSON metrics for /api/engine/markets/cache-status."""
        now = time.time()
        with self._lock:
            # Clean old update timestamps
            cutoff_1m = now - 60.0
            updates_last_min = sum(1 for ts in self._updates_window if ts >= cutoff_1m)

            # Clean old 429 timestamps
            cutoff_1h = now - 3600.0
            rest_429s_last_hour = sum(1 for ts in self._rest_429s if ts >= cutoff_1h)

            last_msg_age = round(now - self._last_ws_msg_time, 1) if self._last_ws_msg_time > 0 else None
            open_count = sum(1 for m in self._markets.values() if m.get("status") in ("active", "open") and not m.get("paused"))

            return {
                "markets_open": open_count,
                "total_cached": len(self._markets),
                "last_snapshot_at": self._last_snapshot_at,
                "snapshot_seconds": self._snapshot_seconds,
                "ws_connected": self._ws_connected,
                "last_ws_msg_age_s": last_msg_age,
                "updates_last_min": updates_last_min,
                "resyncs": self._resyncs,
                "rest_429s_last_hour": rest_429s_last_hour,
                "is_healthy": self.is_cache_healthy()
            }

    def force_disconnect_ws(self) -> bool:
        """Diagnostic helper to simulate socket kill and verify reconnect/resync."""
        if getattr(self, "_active_ws", None) and getattr(self, "_ws_loop_obj", None):
            try:
                asyncio.run_coroutine_threadsafe(self._active_ws.close(), self._ws_loop_obj)
                return True
            except Exception as e:
                logger.error(f"[MarketCache] Error closing WS: {e}")
        return False

    def get_market(self, ticker: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._markets.get(ticker)

    def get_markets_for_event(self, event_ticker: str) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._by_event.get(event_ticker, []))

    def get_markets_for_series(self, series_ticker: str) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._by_series.get(series_ticker, []))

    def get_series_events(self, series_ticker: str) -> List[Dict[str, Any]]:
        now_dt = datetime.now(timezone.utc)
        with self._lock:
            markets = self.get_markets_for_series(series_ticker)
            if not markets:
                return []
            
            by_evt: Dict[str, List[Dict[str, Any]]] = {}
            for m in markets:
                m_status = str(m.get("status") or "").lower()
                if m_status in ("closed", "settled", "determined") or m.get("paused"):
                    continue
                ct_str = m.get("close_time")
                if ct_str:
                    try:
                        ct_dt = datetime.fromisoformat(ct_str.replace("Z", "+00:00"))
                        if ct_dt < now_dt:
                            continue
                    except:
                        pass
                et = m.get("event_ticker")
                if et:
                    # Normalize prices into dollars (0.0 to 1.0)
                    ya = float(m.get("yes_ask") or 0.0)
                    na = float(m.get("no_ask") or 0.0)
                    yb = float(m.get("yes_bid") or 0.0)
                    nb = float(m.get("no_bid") or 0.0)
                    lp = float(m.get("last_price") or 0.0)
                    if ya == 0.0 and nb > 0.0:
                        ya = round(1.0 - nb, 4)
                    if na == 0.0 and yb > 0.0:
                        na = round(1.0 - yb, 4)
                    if ya > 0.0 and na <= 0.0:
                        na = round(1.0 - ya, 4)
                    elif na > 0.0 and ya <= 0.0:
                        ya = round(1.0 - na, 4)
                    if ya <= 0.0 and lp > 0.0:
                        ya = lp
                        na = round(1.0 - lp, 4)
                    elif ya <= 0.0 and na <= 0.0:
                        ya = 0.50
                        na = 0.50
                    if ya > 0.0 and na > 0.0:
                        book_sum = ya + na
                        if book_sum > 1.05 or book_sum < 0.98:
                            na = round(max(0.01, min(0.99, 1.0 - ya)), 4)
                    m["yes_ask"] = ya
                    m["no_ask"] = na
                    by_evt.setdefault(et, []).append(m)
                    
            events = []
            for et, mkts in by_evt.items():
                first = mkts[0]
                milestone = self._milestones.get(et) or (self._milestones.get(f"SUFFIX:{et.split('-', 1)[1]}") if "-" in et else None)
                
                # Restore pre-cache "Away vs Home" title format
                ev_title = ""
                if milestone and milestone.get("title"):
                    m_title = milestone["title"].strip()
                    # Convert "Team A at Team B" -> "Team A vs Team B"
                    ev_title = re.sub(r'\s+(?:at|@)\s+', ' vs ', m_title, flags=re.IGNORECASE)
                
                if not ev_title or " vs " not in ev_title:
                    first_title = (first.get("title") or "").strip()
                    if ":" in first_title:
                        prefix_part = first_title.split(":", 1)[0].strip()
                        if re.search(r'\s+(?:vs\.?|at|@)\s+', prefix_part, flags=re.IGNORECASE):
                            ev_title = re.sub(r'\s+(?:vs\.?|at|@)\s+', ' vs ', prefix_part, flags=re.IGNORECASE)

                if not ev_title or " vs " not in ev_title:
                    # Extract participants from markets
                    participants = []
                    for m in mkts:
                        cand = (m.get("yes_sub_title") or "").strip()
                        if not cand or cand.lower() in ("yes", "no"):
                            cand = re.sub(r'\s+wins\??$', '', m.get("title", ""), flags=re.IGNORECASE).strip()
                        if cand and re.search(r'(?:^over\s|^under\s|goals?\s+scored|runs?\s+scored|points?\s+scored|total\s+|wins?\s+by|reg\s+time:|1st\s+half|2nd\s+half|1st\s+period|2nd\s+period|3rd\s+period)', cand, flags=re.IGNORECASE):
                            continue
                        if cand and cand.lower() not in ("tie", "draw", "tie is the result", "draw is the result") and cand not in participants:
                            participants.append(cand)
                    
                    if len(participants) >= 2:
                        # Kalshi tickers format: AWAY team first, HOME team second (e.g. -26OCT100100HOKSAI -> HOK away, SAI home)
                        # Check custom_strike against milestone if available
                        if milestone and milestone.get("details"):
                            det = milestone["details"]
                            away_id = det.get("away_team_id")
                            home_id = det.get("home_team_id")
                            p_away, p_home = None, None
                            for m in mkts:
                                cs = m.get("custom_strike")
                                yst = m.get("yes_sub_title")
                                if cs and yst:
                                    try:
                                        cs_dict = json.loads(cs) if isinstance(cs, str) else cs
                                        t_id = next((v for k, v in cs_dict.items() if "team" in k or k == "id"), None)
                                        if t_id == away_id: p_away = yst
                                        elif t_id == home_id: p_home = yst
                                    except: pass
                            if p_away and p_home:
                                ev_title = f"{p_away} vs {p_home}"
                        if not ev_title:
                            ev_title = f"{participants[0]} vs {participants[1]}"
                    elif len(participants) == 1:
                        ev_title = participants[0]
                    else:
                        raw_t = first.get("title") or et
                        if ":" in raw_t and re.search(r'\s+(?:vs\.?|at|@)\s+', raw_t.split(":", 1)[0], flags=re.IGNORECASE):
                            raw_t = raw_t.split(":", 1)[0].strip()
                        ev_title = re.sub(r'\s+wins\??$', '', raw_t, flags=re.IGNORECASE).strip()

                sub_t = first.get("yes_sub_title") or ""
                strike_det = first.get("yes_sub_title") or first.get("title") or ""
                events.append({
                    "event_ticker": et,
                    "series_ticker": series_ticker,
                    "title": ev_title,
                    "sub_title": sub_t,
                    "strike_details": strike_det,
                    "markets": mkts,
                    "milestone": milestone
                })
            return events

    def get_milestone_map(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._milestones)

    # ---------------------------------------------------------
    # 90¢+ Scanner & Combo Builder Query Engine
    # ---------------------------------------------------------
    def scan_markets(
        self,
        min_price: float = 0.90,
        max_price: float = 0.99,
        side: str = "any",
        require_bid: int = 1,
        min_volume: float = 1.0,
        min_volume_24h: float = 0.0,
        max_close_hours: Optional[float] = None,
        series: Optional[str] = None,
        limit: int = 200,
        sort: str = "close_time"
    ) -> Dict[str, Any]:
        """
        Fast in-memory scanner for 90¢+ contracts and combo builder.
        - 'side=any' returns the favored side whose ask is within the range.
        - 'require_bid=1' drops stray asks with no bid behind them.
        """
        now_dt = datetime.now(timezone.utc)
        side_lower = (side or "any").lower().strip()
        series_set = {s.strip().upper() for s in series.split(",") if s.strip()} if series else None

        results = []
        with self._lock:
            for m in self._markets.values():
                if m.get("status") not in ("active", "open") or m.get("paused"):
                    continue

                # Series filter
                if series_set and m.get("series_ticker", "").upper() not in series_set:
                    continue

                # Volume filters
                vol = float(m.get("volume") or 0.0)
                if min_volume > 0 and vol < min_volume:
                    continue
                vol_24h = float(m.get("volume_24h") or 0.0)
                if min_volume_24h > 0 and vol_24h < min_volume_24h:
                    continue

                # Close time filter
                hours_to_close = None
                ct_str = m.get("close_time")
                if ct_str:
                    try:
                        ct_dt = datetime.fromisoformat(ct_str.replace("Z", "+00:00"))
                        hours_to_close = (ct_dt - now_dt).total_seconds() / 3600.0
                    except:
                        pass

                if max_close_hours is not None:
                    if hours_to_close is None or hours_to_close < 0 or hours_to_close > max_close_hours:
                        continue

                yes_ask = float(m.get("yes_ask") or 0.0)
                yes_bid = float(m.get("yes_bid") or 0.0)
                no_ask = float(m.get("no_ask") or 0.0)
                no_bid = float(m.get("no_bid") or 0.0)

                # Qualification checks
                yes_qualifies = (min_price <= yes_ask <= max_price) and (yes_bid > 0.0 if require_bid else True)
                no_qualifies = (min_price <= no_ask <= max_price) and (no_bid > 0.0 if require_bid else True)

                chosen_side = None
                chosen_price = 0.0
                chosen_bid = 0.0

                if side_lower == "yes":
                    if yes_qualifies:
                        chosen_side = "yes"
                        chosen_price = yes_ask
                        chosen_bid = yes_bid
                elif side_lower == "no":
                    if no_qualifies:
                        chosen_side = "no"
                        chosen_price = no_ask
                        chosen_bid = no_bid
                else:  # "any" -> Favored side
                    if yes_qualifies and no_qualifies:
                        if yes_ask >= no_ask:
                            chosen_side, chosen_price, chosen_bid = "yes", yes_ask, yes_bid
                        else:
                            chosen_side, chosen_price, chosen_bid = "no", no_ask, no_bid
                    elif yes_qualifies:
                        chosen_side, chosen_price, chosen_bid = "yes", yes_ask, yes_bid
                    elif no_qualifies:
                        chosen_side, chosen_price, chosen_bid = "no", no_ask, no_bid

                if chosen_side:
                    results.append({
                        "ticker": m.get("ticker"),
                        "event_ticker": m.get("event_ticker"),
                        "series": m.get("series_ticker"),
                        "title": m.get("title"),
                        "side": chosen_side,
                        "price": round(chosen_price, 4),
                        "bid": round(chosen_bid, 4),
                        "last_price": round(float(m.get("last_price") or chosen_price), 4),
                        "volume": vol,
                        "volume_24h": vol_24h,
                        "open_interest": float(m.get("open_interest") or 0.0),
                        "close_time": ct_str,
                        "hours_to_close": round(hours_to_close, 1) if hours_to_close is not None else None,
                        "yes_sub_title": m.get("yes_sub_title")
                    })

        # Sorting
        sort_key = (sort or "close_time").lower().strip()
        if sort_key == "price":
            results.sort(key=lambda x: x["price"], reverse=True)
        elif sort_key == "volume":
            results.sort(key=lambda x: x["volume"], reverse=True)
        else:  # close_time default
            results.sort(key=lambda x: (x["hours_to_close"] if x["hours_to_close"] is not None else 999999))

        return {
            "count": len(results[:limit]),
            "total_matches": len(results),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "markets": results[:limit]
        }

    # ---------------------------------------------------------
    # Lifecycle Runner
    # ---------------------------------------------------------
    def start(self):
        """Starts the startup snapshot and WebSocket client in background daemon threads."""
        if self._started:
            return
        self._started = True

        # 1. Warm cache immediately from SQLite
        loaded_count = self.load_from_sqlite()

        # 2. Launch background milestone update first, then fresh REST snapshot
        def run_initial_snapshot():
            time.sleep(0.5)
            try:
                self.update_milestones_and_sports()
            except Exception:
                pass
            if loaded_count >= 15000:
                # SQLite cache is already warm; wait 60s before full REST resync so boot requests are instant
                time.sleep(60.0)
            self.fetch_snapshot()

        threading.Thread(target=run_initial_snapshot, daemon=True, name="KalshiInitialSnapshot").start()

        # 3. Launch WebSocket thread
        def run_ws():
            asyncio.run(self._ws_loop())

        self._ws_thread = threading.Thread(target=run_ws, daemon=True, name="KalshiLiveMarketCacheWS")
        self._ws_thread.start()

        # 4. Launch periodic milestones update (every 10 min)
        def run_milestone_loop():
            while True:
                time.sleep(600)
                try: self.update_milestones_and_sports()
                except: pass

        threading.Thread(target=run_milestone_loop, daemon=True, name="KalshiMilestonesLoop").start()
        logger.info("[MarketCache] Kalshi Live Market Cache engine started.")


# Global Accessor
def get_market_cache_instance() -> KalshiMarketCache:
    return KalshiMarketCache.get_instance()
