"""
Kalshi Authenticated Trading Service
Handles RSA-PSS signed API communications, portfolio balance checks,
market discovery for KXBTC15M contracts, and live/paper order execution.
"""

import logging

logger = logging.getLogger(__name__)
import base64
import json
import math
import os
import threading
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key

# Kalshi's documented production Trade API host.
BASE_URL = "https://external-api.kalshi.com"
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kalshi_credentials.json")

# Paper-fill realism knobs. Kalshi's public market endpoint only ever exposes top-of-book
# yes/no bid & ask - no order-book depth ladder - so there is no way to simulate a paper fill
# against a *real* depth snapshot. These constants instead approximate "how thin is a KXBTC15M/
# KXETH15M market usually" so a paper order behaves like a real one would: it can be too big
# for the book, and by the time a real order would land, the price has usually drifted a hair.
PAPER_LATENCY_TAX_DOLLARS = 0.01   # stands in for adverse price drift during a live order's network round-trip
PAPER_MIN_SIM_DEPTH = 8            # thinnest plausible top-of-book size on these markets
PAPER_MAX_SIM_DEPTH = 60           # thickest plausible top-of-book size on these markets
PAPER_NO_FILL_CHANCE = 0.03        # occasional fully-missed IOC, same as a live order can suffer


def _simulated_book_depth(ticker: str, side: str) -> int:
    """A deterministic-but-varying stand-in for real order-book depth, since Kalshi's market
    endpoint doesn't expose one. Deterministic per (ticker, side, current minute) so repeated
    calls within the same trading decision don't jitter, but different markets/minutes do.
    Occasionally returns 0 to model a fully-missed IOC fill, same risk a live order carries."""
    import hashlib
    bucket = int(time.time() // 60)
    h = hashlib.sha256(f"{ticker}|{side}|{bucket}".encode()).hexdigest()
    roll = int(h[:8], 16) / 0xFFFFFFFF
    if roll < PAPER_NO_FILL_CHANCE:
        return 0
    span = PAPER_MAX_SIM_DEPTH - PAPER_MIN_SIM_DEPTH
    return PAPER_MIN_SIM_DEPTH + int(((roll - PAPER_NO_FILL_CHANCE) / (1.0 - PAPER_NO_FILL_CHANCE)) * span)


# ── Real order book for paper fills (Fix D) ───────────────────────────────────────────
# Kalshi's public GET /markets/{ticker}/orderbook returns resting BIDS per side as
# [[price_dollars, qty], ...] sorted ascending (best bid last). Buying YES lifts NO bids
# (YES ask = 1 - NO bid) and vice versa; selling YES hits YES bids. Paper orders walk these
# levels exactly like a live IOC would, so size beyond the visible book is partially filled.
PAPER_BOOK_CACHE_SEC = 1.0
_paper_book_cache: Dict[str, Any] = {}
_paper_book_lock = threading.Lock()


def _fetch_order_book(ticker: str) -> Optional[Dict[str, list]]:
    """{'yes': [(price, qty) best-first], 'no': [...]} of resting bids, or None on any failure."""
    t = str(ticker or "").upper()
    if not t or "_SYNTH" in t:
        return None
    now = time.time()
    with _paper_book_lock:
        hit = _paper_book_cache.get(t)
        if hit and now - hit[0] < PAPER_BOOK_CACHE_SEC:
            return hit[1]
    try:
        from urllib.parse import quote
        r = requests.get(f"{BASE_URL}/trade-api/v2/markets/{quote(t, safe='')}/orderbook", timeout=2.0)
        if r.status_code != 200:
            return None
        ob = (r.json() or {}).get("orderbook_fp") or {}
        book = {}
        is_empty = True
        for side in ("yes", "no"):
            levels = []
            for p, q in (ob.get(f"{side}_dollars") or []):
                try:
                    p, q = float(p), float(q)
                except (TypeError, ValueError):
                    continue
                if 0.0 < p < 1.0 and q > 0:
                    levels.append((p, q))
                    is_empty = False
            levels.sort(key=lambda x: x[0], reverse=True)  # best bid first
            book[side] = levels
        if is_empty:
            return None
        with _paper_book_lock:
            _paper_book_cache[t] = (now, book)
        return book
    except Exception:
        return None


def _walk_book(levels, count: float, price_ok) -> tuple:
    """Fill up to `count` across (price, qty) levels in order while price_ok(price).
    Returns (filled_count, total_cost)."""
    filled, cost = 0.0, 0.0
    for price, qty in levels:
        if filled >= count or not price_ok(price):
            break
        take = min(qty, count - filled)
        filled += take
        cost += take * price
    return filled, cost


def paper_buy_from_book(ticker: str, side: str, count: int, limit_price: float):
    """Simulated IOC buy against the real book. Returns (filled_int, vwap) or None if no book."""
    book = _fetch_order_book(ticker)
    if not book:
        return None
    opp = "no" if side.lower() == "yes" else "yes"
    asks = [(round(1.0 - p, 4), q) for p, q in book.get(opp, [])]  # cheapest ask first
    filled, cost = _walk_book(asks, float(count), lambda px: px <= limit_price + 1e-9)
    filled_int = int(filled)
    if filled_int <= 0:
        return (0, 0.0)
    # recompute cost for the whole-contract quantity actually filled
    _, cost = _walk_book(asks, float(filled_int), lambda px: px <= limit_price + 1e-9)
    return (filled_int, cost / filled_int)


def paper_sell_from_book(ticker: str, side: str, count: float, floor_price: float):
    """Simulated IOC sell of `side` contracts into the real bids. Returns (filled, vwap) or None."""
    book = _fetch_order_book(ticker)
    if not book:
        return None
    filled, cost = _walk_book(book.get(side.lower(), []), float(count), lambda px: px >= floor_price - 1e-9)
    if filled <= 0:
        return (0.0, 0.0)
    return (filled, cost / filled)


def paper_exit_price(ticker: str, side: str, count: float, best_bid: float, cushion: float = 0.03) -> float:
    """Realistic per-contract exit price for closing a whole paper position now.
    Walks the real bids down to `best_bid - cushion` (what a live reduce-only exit crosses);
    any size the book can't absorb there is priced at that floor (the worst a live retry
    accepts). Minus the same latency tax as entries. Falls back to best_bid - tax."""
    try:
        best_bid = float(best_bid)
        count = float(count)
    except (TypeError, ValueError):
        return 0.0
    if not (0.0 < best_bid < 1.0) or count <= 0:
        return round(max(0.0, best_bid), 4)
    floor = max(0.01, best_bid - cushion)
    px = best_bid
    res = paper_sell_from_book(ticker, side, count, floor)
    if res is not None and res[0] > 0:
        filled, vwap = res
        px = (filled * vwap + max(0.0, count - filled) * floor) / count
    return round(max(0.01, px - PAPER_LATENCY_TAX_DOLLARS), 4)


class KalshiTrader:
    def __init__(self, key_id: Optional[str] = None, private_key_pem: Optional[str] = None, fail_fast: bool = False):
        self.key_id = key_id or os.environ.get("KALSHI_KEY_ID")
        self.private_key_pem = private_key_pem or os.environ.get("KALSHI_PRIVATE_KEY")
        self.fail_fast = fail_fast
        self._private_key_obj = None
        self._order_submit_lock = threading.Lock()

        if not self.key_id or not self.private_key_pem:
            self._load_from_credentials_file()

        self._cached_balance = None
        self._cached_balance_time = 0.0
        self._cached_markets = {}
        self._cached_market_times = {}
        self._lock = threading.Lock()

        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=1)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Dedicated session for order-mutating endpoints (place_order, close_position)
        # with max_retries=0 to prevent duplicate fills on network timeouts.
        self.order_session = requests.Session()
        order_adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=0)
        self.order_session.mount("https://", order_adapter)
        self.order_session.mount("http://", order_adapter)

        if self.private_key_pem:
            try:
                self._private_key_obj = load_pem_private_key(self.private_key_pem.encode("utf-8"), password=None)
            except Exception as e:
                logger.error(f"[KalshiTrader] Error loading private key: {e}")

    def _load_from_credentials_file(self):
        if os.path.exists(CREDENTIALS_FILE):
            try:
                with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.key_id = data.get("key_id", self.key_id)
                    self.private_key_pem = data.get("private_key", self.private_key_pem)
            except Exception as e:
                logger.error(f"[KalshiTrader] Error reading credentials file: {e}")

    def is_authenticated(self) -> bool:
        return bool(self.key_id and self._private_key_obj)

    def _sign_headers(self, method: str, path: str) -> Dict[str, str]:
        if not self.is_authenticated():
            raise ValueError("Kalshi API credentials not configured or private key invalid.")

        timestamp = str(int(time.time() * 1000))
        msg_string = timestamp + method.upper() + path

        signature = self._private_key_obj.sign(
            msg_string.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        signature_b64 = base64.b64encode(signature).decode("utf-8")

        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-SIGNATURE": signature_b64,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def get_balance(self, force_refresh: bool = False, fail_fast: Optional[bool] = None) -> Dict[str, Any]:
        """
        Retrieves live portfolio balance and dollar breakdown (cached for 4.0s for sub-ms polling).
        Protected with exponential backoff on HTTP 429 and network errors, or immediate fail-fast.
        """
        use_fail_fast = self.fail_fast if fail_fast is None else fail_fast
        now = time.time()
        with self._lock:
            if not force_refresh and self._cached_balance and (now - self._cached_balance_time < 4.0):
                return self._cached_balance

        path = "/trade-api/v2/portfolio/balance"
        max_attempts = 1 if use_fail_fast else 3
        backoff = 1.0
        for attempt in range(1, max_attempts + 1):
            try:
                headers = self._sign_headers("GET", path)
                resp = self.session.get(f"{BASE_URL}{path}", headers=headers, timeout=5.0)
                if resp.status_code == 429 or resp.status_code in [502, 503, 504]:
                    if resp.status_code == 429 and use_fail_fast:
                        logger.warning("[KalshiTrader] get_balance received HTTP 429 (fail_fast=True). Failing fast without sleep.")
                        return {
                            "success": False,
                            "error": f"Kalshi 429 rate limit exceeded: {resp.text}",
                            "status_code": 429,
                            "balance_dollars": 0.0,
                            "balance_cents": 0
                        }
                    if attempt < max_attempts:
                        logger.warning(
                            f"[KalshiTrader] get_balance received HTTP {resp.status_code}, "
                            f"retrying in {backoff:.1f}s (attempt {attempt}/{max_attempts})..."
                        )
                        time.sleep(backoff)
                        backoff *= 2.0
                        continue
                if resp.status_code == 200:
                    data = resp.json()
                    dollars = float(data.get("balance_dollars", int(data.get("balance", 0)) / 100.0))
                    cents = int(data.get("balance", 0))
                    # Kalshi returns portfolio_value in cents
                    port_val = float(data.get("portfolio_value", 0.0)) / 100.0
                    res = {
                        "success": True,
                        "balance_dollars": dollars,
                        "balance_cents": cents,
                        "portfolio_value": port_val,
                        "updated_ts": data.get("updated_ts"),
                        "raw": data
                    }
                    with self._lock:
                        self._cached_balance = res
                        self._cached_balance_time = now
                    return res
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}: {resp.text}",
                    "balance_dollars": 0.0,
                    "balance_cents": 0
                }
            except (requests.exceptions.RequestException, requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if use_fail_fast:
                    logger.warning(f"[KalshiTrader] get_balance network error ({e}) with fail_fast=True. Failing fast without sleep.")
                    return {
                        "success": False,
                        "error": str(e),
                        "balance_dollars": 0.0,
                        "balance_cents": 0
                    }
                if attempt < max_attempts:
                    logger.warning(
                        f"[KalshiTrader] get_balance network error ({e}), "
                        f"retrying in {backoff:.1f}s (attempt {attempt}/{max_attempts})..."
                    )
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue
                return {
                    "success": False,
                    "error": str(e),
                    "balance_dollars": 0.0,
                    "balance_cents": 0
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "balance_dollars": 0.0,
                    "balance_cents": 0
                }

    def get_exchange_breakdown(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Retrieves per-exchange shard balance breakdown (e.g. Exchange 0 vs Exchange 2).
        """
        bal_res = self.get_balance(force_refresh=force_refresh)
        if not bal_res.get("success"):
            return {
                "success": False,
                "error": bal_res.get("error", "Failed to fetch balance"),
                "total_balance": 0.0,
                "exchanges": []
            }

        raw = bal_res.get("raw", {})
        breakdown = raw.get("balance_breakdown", [])

        exchanges = []
        exchange_names = {
            0: "Exchange 0 (Main / Cash)",
            1: "Exchange 1 (Rates / Yields)",
            2: "Exchange 2 (Crypto 15M & Commodities)",
            3: "Exchange 3 (Specialty)"
        }
        for b_item in breakdown:
            idx = b_item.get("exchange_index")
            try:
                bal = float(b_item.get("balance", 0.0))
            except (ValueError, TypeError):
                bal = 0.0
            exchanges.append({
                "exchange_index": idx,
                "name": exchange_names.get(idx, f"Exchange {idx}"),
                "balance": round(bal, 4)
            })

        return {
            "success": True,
            "total_balance": bal_res.get("balance_dollars", 0.0),
            "exchanges": exchanges
        }

    def transfer_between_exchanges(
        self,
        source_exchange: int = 0,
        destination_exchange: int = 2,
        amount_dollars: float = 0.0
    ) -> Dict[str, Any]:
        """
        Transfers funds between Kalshi exchange matching engine shards 
        (e.g., Shard 0 main balance to Shard 2 crypto trading engine).
        Amount is converted to centicents (1 dollar = 10,000 centicents).
        """
        try:
            amt = round(float(amount_dollars), 2)
            if amt <= 0:
                return {"success": False, "error": "Transfer amount must be greater than $0.00."}
        except (ValueError, TypeError):
            return {"success": False, "error": "Invalid transfer amount."}

        # Verify source exchange balance
        bal_res = self.get_exchange_breakdown(force_refresh=True)
        if not bal_res.get("success"):
            return {"success": False, "error": bal_res.get("error", "Could not verify exchange balances before transfer.")}

        source_bal = 0.0
        for ex in bal_res.get("exchanges", []):
            if ex.get("exchange_index") == source_exchange:
                source_bal = float(ex.get("balance", 0.0))
                break

        if source_bal < amt:
            return {
                "success": False,
                "error": f"Insufficient funds in Exchange {source_exchange}: ${source_bal:.2f} available, but requested ${amt:.2f}."
            }

        amount_centicents = int(round(amt * 10000))
        path = "/trade-api/v2/portfolio/intra_exchange_instance_transfer"
        payload = {
            "source": "event_contract",
            "destination": "event_contract",
            "source_exchange_shard": int(source_exchange),
            "destination_exchange_shard": int(destination_exchange),
            "amount": amount_centicents
        }

        try:
            headers = self._sign_headers("POST", path)
            resp = self.session.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=10.0)
            if resp.status_code != 200:
                err_msg = resp.text
                try:
                    err_json = resp.json()
                    err_msg = err_json.get("error", {}).get("message", err_msg)
                except Exception as e:
                    logger.debug(f"Ignored exception: {e}")
                return {"success": False, "error": f"Kalshi transfer rejected (HTTP {resp.status_code}): {err_msg}"}

            data = resp.json()
            transfer_id = data.get("transfer_id", str(uuid.uuid4()))

            # Invalidate balance cache so fresh balances are immediately reported
            with self._lock:
                self._cached_balance = None
                self._cached_balance_time = 0.0

            fresh_res = self.get_exchange_breakdown(force_refresh=True)
            logger.info(f"[KalshiTrader] Transferred ${amt:.2f} from Exchange {source_exchange} to Exchange {destination_exchange} (Transfer ID: {transfer_id})")

            return {
                "success": True,
                "transfer_id": transfer_id,
                "amount_dollars": amt,
                "source_exchange": source_exchange,
                "destination_exchange": destination_exchange,
                "exchanges": fresh_res.get("exchanges", [])
            }
        except Exception as e:
            logger.error(f"[KalshiTrader] Transfer exception: {e}")
            return {"success": False, "error": f"Transfer failed: {str(e)}"}

    def get_active_15m_market(
        self,
        series_ticker: str = "KXBTC15M",
        allow_synthetic: bool = True,
        force_refresh: bool = False,
        min_seconds_left: int = 45
    ) -> Optional[Dict[str, Any]]:
        """
        Finds the active KXBTC15M market (cached for 2.5s for ultra-low latency real-time feeds).
        """
        now_ts = time.time()
        with self._lock:
            if not force_refresh and self._cached_markets.get(series_ticker) and (now_ts - self._cached_market_times.get(series_ticker, 0.0) < 2.5):
                # Synthetic contracts are useful only for paper trading. Never
                # surface one to the live-order path from the short-lived cache.
                if allow_synthetic or not self._cached_markets[series_ticker].get("is_synthetic"):
                    cached_close = self._cached_markets[series_ticker].get("close_time")
                    if cached_close and min_seconds_left > 0:
                        try:
                            ct = datetime.fromisoformat(cached_close.replace("Z", "+00:00"))
                            if (ct - datetime.now(timezone.utc)).total_seconds() > min_seconds_left:
                                return self._cached_markets.get(series_ticker)
                        except Exception:
                            return self._cached_markets.get(series_ticker)
                    else:
                        return self._cached_markets.get(series_ticker)

        path = "/trade-api/v2/markets"
        try:
            # Retrieve market list with signed authentication
            headers = self._sign_headers('GET', path)
            resp = self.session.get(
                f"{BASE_URL}{path}",
                params={"series_ticker": series_ticker, "status": "open", "limit": 100},
                headers=headers,
                timeout=5.0,
            )
            if resp.status_code != 200:
                raise Exception(f"Market list request failed with status {resp.status_code}")
            data = resp.json()
            markets = data.get("markets", [])
            now_utc = datetime.now(timezone.utc)
            valid = []
            for m in markets:
                ct_str = m.get("close_time")
                if ct_str:
                    try:
                        ct = datetime.fromisoformat(ct_str.replace("Z", "+00:00"))
                        seconds_left = (ct - now_utc).total_seconds()
                        if (min_seconds_left <= 0 or seconds_left > min_seconds_left) and m.get("status") in ["active", "open"]:
                            valid.append((ct, m))
                    except Exception as e:
                        logger.debug(f"Quote parse error: {e}")
            if valid:
                ct, active_m = min(valid, key=lambda x: x[0])

                def _to_dollars(val):
                    """Convert a Kalshi bid/ask value: if > 1.0 assume cents, divide by 100."""
                    try:
                        v = float(val or 0.0)
                        return round(v / 100.0, 4) if v > 1.0 else v
                    except Exception:
                        return 0.0

                yes_bid = _to_dollars(active_m.get("yes_bid") or active_m.get("yes_bid_dollars"))
                yes_ask = _to_dollars(active_m.get("yes_ask") or active_m.get("yes_ask_dollars"))
                no_bid  = _to_dollars(active_m.get("no_bid")  or active_m.get("no_bid_dollars"))
                no_ask  = _to_dollars(active_m.get("no_ask")  or active_m.get("no_ask_dollars"))
                last_price = _to_dollars(active_m.get("last_price") or active_m.get("last_price_dollars"))

                # If the authenticated API returned all zeros, fallback to public client
                if yes_bid == 0.0 and yes_ask == 0.0:
                    try:
                        from backend.btc.kalshi_client import \
                            get_kalshi_15m_market
                        pub = get_kalshi_15m_market()
                        if pub:
                            yes_bid    = float(pub.get("yes_bid")  or yes_bid)
                            yes_ask    = float(pub.get("yes_ask")  or yes_ask)
                            no_bid     = float(pub.get("no_bid")   or no_bid)
                            no_ask     = float(pub.get("no_ask")   or no_ask)
                            last_price = float(pub.get("last_price") or pub.get("yes_bid") or last_price)
                    except Exception as e:
                        logger.debug(f"Quote parse error: {e}")

                floor_strike = active_m.get("floor_strike")
                strike_price = active_m.get("strike_price")
                if not strike_price and floor_strike is not None:
                    strike_price = floor_strike

                res_market = {
                    "ticker": active_m.get("ticker") or active_m.get("event_ticker"),
                    "event_ticker": active_m.get("event_ticker", ""),
                    "title": active_m.get("title", ""),
                    "strike_price": float(strike_price or 0.0),
                    "close_time": active_m.get("close_time", ""),
                    "yes_bid": yes_bid,
                    "yes_ask": yes_ask,
                    "no_bid": no_bid,
                    "no_ask": no_ask,
                    "last_price": last_price,
                    "volume_24h": float(active_m.get("volume_24h_fp") or 0.0),
                    "status": active_m.get("status", "open"),
                    "exchange_index": active_m.get("exchange_index"),
                    "is_synthetic": False,
                }
                with self._lock:
                    self._cached_markets[series_ticker] = res_market
                    self._cached_market_times[series_ticker] = now_ts
                return res_market
        except Exception as e:
            logger.error(f"[KalshiTrader] Error getting active 15M market: {e}")
        # Synthetic fallback if allowed — enrich with public client data for live P&L
        if allow_synthetic:
            pub_yes_bid, pub_yes_ask, pub_no_bid, pub_no_ask = 0.0, 0.0, 0.0, 0.0
            pub_strike = 0.0
            try:
                from backend.btc.kalshi_client import get_kalshi_15m_market
                from backend.engine.multi_asset_fetcher import get_asset_ticker
                pub = get_kalshi_15m_market()
                if pub:
                    pub_yes_bid = float(pub.get("yes_bid") or 0.0)
                    pub_yes_ask = float(pub.get("yes_ask") or 0.0)
                    pub_no_bid  = float(pub.get("no_bid")  or 0.0)
                    pub_no_ask  = float(pub.get("no_ask")  or 0.0)
                    pub_strike  = float(pub.get("target_price") or pub.get("strike") or pub.get("floor_strike") or 0.0)
                
                if pub_strike <= 0.0:
                    pub_strike = float(get_asset_ticker(series_ticker.replace("KX", "").replace("15M", "")).get("price", 0.0))
            except Exception as e:
                logger.debug(f"Ignored exception: {e}")
            return {
                "ticker": f"{series_ticker}_SYNTH",
                "title": f"Synthetic {series_ticker} 15M",
                "strike_price": pub_strike,
                "close_time": "",
                "yes_bid": pub_yes_bid,
                "yes_ask": pub_yes_ask,
                "no_bid": pub_no_bid,
                "no_ask": pub_no_ask,
                "last_price": pub_yes_bid,
                "volume_24h": 0.0,
                "status": "synthetic",
                "is_synthetic": True,
            }
        return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=1, max=5),
        retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout, requests.exceptions.ConnectionError)),
        retry_error_callback=lambda retry_state: {
            "success": False,
            "result": "",
            "error": f"Kalshi API retries exhausted: {retry_state.outcome.exception()}",
        }
    )
    def get_market_result(self, ticker: str) -> Dict[str, Any]:
        """Return Kalshi's official result for one exact market ticker."""
        clean_ticker = str(ticker or "").strip()
        if not clean_ticker or clean_ticker.endswith("_SYNTH"):
            return {"success": False, "result": "", "error": "No official Kalshi ticker available."}

        path = f"/trade-api/v2/markets/{quote(clean_ticker, safe='')}"
        try:
            resp = self.session.get(
                f"{BASE_URL}{path}",
                headers={"Accept": "application/json", "User-Agent": "ApexProps-Trader/1.0"},
                timeout=5.0,
            )
            if resp.status_code == 429 or resp.status_code in [502, 503, 504]:
                logger.warning(f"[KalshiTrader] get_market_result {ticker} received HTTP {resp.status_code}, retrying with backoff...")
                raise requests.exceptions.RequestException(f"HTTP {resp.status_code} Rate Limit / Server Error: {resp.text}")
            if resp.status_code != 200:
                return {
                    "success": False,
                    "result": "",
                    "error": f"HTTP {resp.status_code}: {resp.text}",
                }
            market = resp.json().get("market", {})
            result = str(market.get("result") or "").strip().lower()
            return {
                "success": True,
                "result": result if result in {"yes", "no"} else "",
                "status": str(market.get("status") or "").lower(),
                "market": market,
            }
        except requests.exceptions.RequestException:
            raise
        except Exception as e:
            return {"success": False, "result": "", "error": str(e)}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=1, max=5),
        retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout, requests.exceptions.ConnectionError)),
        retry_error_callback=lambda retry_state: {
            "success": False,
            "error": f"Kalshi API retries exhausted: {retry_state.outcome.exception()}",
        }
    )
    def get_market_quote(self, ticker: str) -> Dict[str, Any]:
        """Return executable YES/NO bid prices for one exact open market."""
        clean_ticker = str(ticker or "").strip()
        if not clean_ticker or clean_ticker.endswith("_SYNTH"):
            return {"success": False, "error": "No official Kalshi ticker available."}

        def as_dollars(market: Dict[str, Any], field: str) -> float:
            value = market.get(f"{field}_dollars")
            if value is None:
                value = market.get(field)
            try:
                price = float(value)
                return round(price / 100.0, 4) if price > 1.0 else round(price, 4)
            except (TypeError, ValueError):
                return 0.0

        path = f"/trade-api/v2/markets/{quote(clean_ticker, safe='')}"
        try:
            headers = {"Accept": "application/json", "User-Agent": "ApexProps-Trader/1.0"}
            if self.is_authenticated():
                try:
                    headers = self._sign_headers("GET", path)
                except Exception:
                    pass
            resp = self.session.get(
                f"{BASE_URL}{path}",
                headers=headers,
                timeout=5.0,
            )
            if resp.status_code == 429 or resp.status_code in [502, 503, 504]:
                logger.warning(f"[KalshiTrader] get_market_quote {ticker} received HTTP {resp.status_code}, retrying with backoff...")
                raise requests.exceptions.RequestException(f"HTTP {resp.status_code} Rate Limit / Server Error: {resp.text}")
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
            market = resp.json().get("market", {})
            status = str(market.get("status") or "").lower()
            if status not in {"active", "open"}:
                return {"success": False, "error": f"Market is not open (status: {status or 'unknown'})."}
            return {
                "success": True,
                "ticker": clean_ticker,
                "yes_bid": as_dollars(market, "yes_bid"),
                "no_bid": as_dollars(market, "no_bid"),
                "exchange_index": market.get("exchange_index"),
                "market": market,
            }
        except requests.exceptions.RequestException:
            raise
        except Exception as e:
            return {"success": False, "error": str(e)}

    def close_position(
        self,
        ticker: str,
        purchased_side: str,
        count: float,
        dry_run: bool = True,
        estimated_exit_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Exit an existing YES/NO position at its current executable bid.

        Event-market V2 orders are quoted on the YES price scale.  Reducing a
        YES position means submitting an ask at the YES bid; reducing a NO
        position means submitting a bid at ``1 - no_bid``.  ``reduce_only``
        prevents this endpoint from opening an opposite position on a stale or
        partially closed trade.
        """
        side = str(purchased_side or "").upper().strip()
        if side not in {"YES", "NO"}:
            return {"success": False, "error": "Position side must be YES or NO."}
        try:
            requested_count = float(count)
        except (TypeError, ValueError):
            return {"success": False, "error": "Position count is invalid."}
        if requested_count <= 0:
            return {"success": False, "error": "Position count must be positive."}

        quote_data = self.get_market_quote(ticker)
        exit_price = 0.0
        if quote_data.get("success"):
            raw_exit_price = quote_data.get("yes_bid") if side == "YES" else quote_data.get("no_bid")
            try:
                exit_price = float(raw_exit_price or 0.0)
            except (TypeError, ValueError):
                exit_price = 0.0

        if dry_run:
            source = "kalshi_public_bid" if quote_data.get("success") else "simulated_dynamic_quote"
            if not (0.0 < exit_price < 1.0):
                if estimated_exit_price is not None and 0.0 < estimated_exit_price < 1.0:
                    exit_price = float(estimated_exit_price)
                else:
                    exit_price = 0.50
            # Same small latency tax as the entry side, and rounded to whole cents - a real bid
            # can never be crossed at a fractional-cent price the way the synthetic fallback quote
            # above can produce.
            from backend.btc.fees import kalshi_order_fee
            best_bid = exit_price
            exit_price = round(max(0.01, exit_price - PAPER_LATENCY_TAX_DOLLARS), 2)

            sim_depth = _simulated_book_depth(ticker, f"exit_{side}")
            filled_count = min(requested_count, sim_depth) if sim_depth > 0 else requested_count

            # Fix D: sell into Kalshi's real resting bids, down to the same 3c cushion a live
            # reduce-only exit crosses (see book_price below). Partial fills leave the rest open
            # for the next check cycle, exactly like a live exit.
            if 0.0 < best_bid < 1.0:
                book_fill = paper_sell_from_book(ticker, side, requested_count, max(0.01, best_bid - 0.03))
                if book_fill is not None and book_fill[0] > 0:
                    filled_count = round(book_fill[0], 4)
                    exit_price = round(max(0.01, book_fill[1] - PAPER_LATENCY_TAX_DOLLARS), 4)
                    source = "kalshi_order_book"
                    sim_depth = None
            # A missed exit isn't modeled as "stuck open forever" (unlike a missed entry, which
            # simply never happened) - a real stop/take-profit exit that fails to fill immediately
            # gets retried on the next check cycle, same as the live retry-with-fresh-quote path
            # above, so we fall back to a full fill here rather than blocking the exit outright.
            if filled_count <= 0:
                filled_count = requested_count

            fee_paid = round(kalshi_order_fee(exit_price, filled_count), 4)
            return {
                "success": True,
                "mode": "PAPER",
                "filled_count": filled_count,
                "remaining_count": max(0.0, round(requested_count - filled_count, 4)),
                "exit_price": exit_price,
                "fee_paid": fee_paid,
                "simulated_depth": sim_depth,
                "source": source,
            }

        if not quote_data.get("success"):
            return quote_data
        if not 0.0 < exit_price < 1.0:
            return {"success": False, "error": f"No executable {side} bid is available to close this position."}

        if not self.is_authenticated():
            return {"success": False, "error": "Kalshi credentials are not configured."}

        # V2 prices always use the YES-price scale. See Kalshi's event order API:
        # To sell YES: submit an ask at YES bid (with 0.02 slippage cushion to cross book immediately)
        # To sell NO: submit a bid on YES at 1 - no_bid (with 0.02 slippage cushion)
        book_side = "ask" if side == "YES" else "bid"
        if side == "YES":
            book_price = max(0.01, min(0.99, exit_price - 0.03))
        else:
            book_price = min(0.99, max(0.01, (1.0 - exit_price) + 0.03))

        pre_positions = []
        try:
            pre_res = self.get_positions()
            if pre_res.get("success"):
                pre_positions = pre_res.get("positions", [])
        except Exception as pre_err:
            logger.warning(f"[KalshiTrader] Failed to snapshot pre-close positions: {pre_err}")

        # Self-healing: if Kalshi reports the position is already flat (0.00), return success
        matching_pos = [p for p in pre_positions if p.get("ticker") == quote_data.get("ticker")]
        if matching_pos:
            actual_side_qty = self._extract_side_position(matching_pos[0], side)
            if actual_side_qty <= 0.0:
                logger.info(f"[KalshiTrader] Position for {quote_data.get('ticker')} ({side}) is already flat on Kalshi (0.00). Reconciling as closed.")
                return {
                    "success": True,
                    "mode": "LIVE",
                    "filled_count": requested_count,
                    "remaining_count": 0.0,
                    "exit_price": exit_price if exit_price > 0 else 0.50,
                    "fee_paid": 0.0,
                    "source": "kalshi_reconciled_flat",
                }
            # Clamp requested count to actual position held so Kalshi's reduce_only doesn't reject if position is smaller
            requested_count = min(requested_count, actual_side_qty)

        client_order_id = str(uuid.uuid4())
        path = "/trade-api/v2/portfolio/events/orders"
        payload = {
            "ticker": quote_data["ticker"],
            "client_order_id": client_order_id,
            "side": book_side,
            "count": f"{requested_count:.2f}",
            "price": f"{book_price:.4f}",
            "time_in_force": "immediate_or_cancel",
            "self_trade_prevention_type": "taker_at_cross",
            "post_only": False,
            "cancel_order_on_pause": True,
            "reduce_only": True,
        }
        if quote_data.get("exchange_index") is not None:
            payload["exchange_index"] = quote_data["exchange_index"]
        try:
            resp = self.order_session.post(f"{BASE_URL}{path}", json=payload, headers=self._sign_headers("POST", path), timeout=5.0)
            if resp.status_code not in {200, 201}:
                err_text = resp.text.lower()
                if "reduce_only" in err_text or "no open position" in err_text or "cannot increase position" in err_text or "position is 0" in err_text:
                    logger.info(f"[KalshiTrader] Kalshi confirmed position already flat via reduce_only check: {resp.text}")
                    return {
                        "success": True,
                        "mode": "LIVE",
                        "filled_count": requested_count,
                        "remaining_count": 0.0,
                        "exit_price": exit_price if exit_price > 0 else 0.50,
                        "fee_paid": 0.0,
                        "source": "kalshi_confirmed_flat_reduce_only",
                    }
                return {"success": False, "error": f"Kalshi close rejected (HTTP {resp.status_code}): {resp.text}"}
            data = resp.json()
            filled_count = float(data.get("fill_count", "0") or "0")
            if filled_count <= 0:
                # Fast retry with fresh quote and wider buffer
                try:
                    fresh_quote = self.get_market_quote(ticker)
                    if fresh_quote.get("success"):
                        fresh_exit = float((fresh_quote.get("yes_bid") if side == "YES" else fresh_quote.get("no_bid")) or 0.0)
                        if 0.01 < fresh_exit < 0.99:
                            retry_book_price = max(0.01, min(0.99, fresh_exit - 0.05)) if side == "YES" else min(0.99, max(0.01, (1.0 - fresh_exit) + 0.05))
                            retry_cid = str(uuid.uuid4())
                            retry_payload = dict(payload)
                            retry_payload["client_order_id"] = retry_cid
                            retry_payload["price"] = f"{retry_book_price:.4f}"
                            logger.info(f"[KalshiTrader] Close unfilled for {ticker} ({side}). Retrying once with fresh bid ${fresh_exit:.2f} (book_price={retry_book_price:.4f})...")
                            retry_resp = self.order_session.post(f"{BASE_URL}{path}", json=retry_payload, headers=self._sign_headers("POST", path), timeout=5.0)
                            if retry_resp.status_code in [200, 201]:
                                retry_data = retry_resp.json()
                                retry_filled = float(retry_data.get("fill_count", "0") or "0")
                                if retry_filled > 0:
                                    avg_bp = float(retry_data.get("average_fill_price", str(retry_book_price)) or retry_book_price)
                                    realized_exit = avg_bp if side == "YES" else (1.0 - avg_bp)
                                    avg_fee = float(retry_data.get("average_fee_paid", "0") or "0")
                                    self._cached_balance_time = 0.0
                                    logger.info(f"[KalshiTrader] Close retry SUCCEEDED: filled {retry_filled} contracts @ ${realized_exit:.4f}")
                                    return {
                                        "success": True,
                                        "mode": "LIVE",
                                        "order_id": retry_data.get("order_id", retry_cid),
                                        "client_order_id": retry_data.get("client_order_id", retry_cid),
                                        "filled_count": retry_filled,
                                        "remaining_count": max(0.0, requested_count - retry_filled),
                                        "exit_price": round(realized_exit, 4),
                                        "fee_paid": round(avg_fee * retry_filled, 4),
                                        "source": "kalshi_reduce_only_exit_retry",
                                    }
                except Exception as _re_err:
                    logger.warning(f"[KalshiTrader] Close retry error: {_re_err}")

                return {"success": False, "error": "Close order received no fill; the local trade remains open."}
            average_book_price = float(data.get("average_fill_price", str(book_price)) or book_price)
            realized_exit_price = average_book_price if side == "YES" else (1.0 - average_book_price)
            average_fee = float(data.get("average_fee_paid", "0") or "0")
            self._cached_balance_time = 0.0
            return {
                "success": True,
                "mode": "LIVE",
                "order_id": data.get("order_id", client_order_id),
                "client_order_id": data.get("client_order_id", client_order_id),
                "filled_count": filled_count,
                "remaining_count": max(0.0, requested_count - filled_count),
                "exit_price": round(realized_exit_price, 4),
                "fee_paid": round(average_fee * filled_count, 4),
                "source": "kalshi_reduce_only_exit",
            }
        except requests.exceptions.RequestException as e:
            logger.warning(
                f"[KalshiTrader] Close request timed out for {ticker} (client_order_id={client_order_id}). "
                f"Attempting reconciliation against live positions..."
            )
            reconciled = self._reconcile_after_timeout(
                ticker=quote_data.get("ticker", ticker),
                client_order_id=client_order_id,
                side=side,
                pre_positions=pre_positions,
                requested_count=requested_count,
                action="CLOSE",
                price=exit_price
            )
            if reconciled is not None:
                return reconciled
            return {
                "success": False,
                "error": f"Kalshi close request timed out and could not be confirmed against Kalshi positions: {e}. "
                         f"MANUAL VERIFICATION REQUIRED — check Kalshi positions before retrying.",
                "ambiguous": True,
                "client_order_id": client_order_id,
                "ticker": ticker,
            }
        except Exception as e:
            return {"success": False, "error": f"Kalshi close request failed: {e}"}

    def get_positions(self, fail_fast: Optional[bool] = None) -> Dict[str, Any]:
        """
        Fetch current portfolio open positions.
        Protected with exponential backoff on HTTP 429 and network errors, or immediate fail-fast.
        """
        use_fail_fast = self.fail_fast if fail_fast is None else fail_fast
        path = "/trade-api/v2/portfolio/positions"
        max_attempts = 1 if use_fail_fast else 3
        backoff = 1.0
        for attempt in range(1, max_attempts + 1):
            try:
                headers = self._sign_headers("GET", path)
                resp = self.session.get(f"{BASE_URL}{path}", headers=headers, timeout=5.0)
                if resp.status_code == 429 or resp.status_code in [502, 503, 504]:
                    if resp.status_code == 429 and use_fail_fast:
                        logger.warning("[KalshiTrader] get_positions received HTTP 429 (fail_fast=True). Failing fast without sleep.")
                        return {"success": False, "error": f"Kalshi 429 rate limit exceeded: {resp.text}", "status_code": 429, "positions": []}
                    if attempt < max_attempts:
                        logger.warning(
                            f"[KalshiTrader] get_positions received HTTP {resp.status_code}, "
                            f"retrying in {backoff:.1f}s (attempt {attempt}/{max_attempts})..."
                        )
                        time.sleep(backoff)
                        backoff *= 2.0
                        continue
                if resp.status_code == 200:
                    data = resp.json()
                    return {"success": True, "positions": data.get("market_positions", [])}
                return {"success": False, "error": resp.text, "positions": []}
            except (requests.exceptions.RequestException, requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if use_fail_fast:
                    logger.warning(f"[KalshiTrader] get_positions network error ({e}) with fail_fast=True. Failing fast without sleep.")
                    return {"success": False, "error": str(e), "positions": []}
                if attempt < max_attempts:
                    logger.warning(
                        f"[KalshiTrader] get_positions network error ({e}), "
                        f"retrying in {backoff:.1f}s (attempt {attempt}/{max_attempts})..."
                    )
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue
                return {"success": False, "error": str(e), "positions": []}
            except Exception as e:
                return {"success": False, "error": str(e), "positions": []}

    def _extract_side_position(self, pos_entry: Dict[str, Any], side: str) -> float:
        """
        Extract contract count for the specified side (YES or NO) from a Kalshi position object.
        Supports both split sub-positions (yes_sub_position / no_sub_position) and net signed positions.
        """
        if not pos_entry or not isinstance(pos_entry, dict):
            return 0.0

        side_upper = str(side or "").upper().strip()
        if side_upper == "YES":
            if "yes_sub_position" in pos_entry and pos_entry["yes_sub_position"] is not None:
                try:
                    return float(pos_entry["yes_sub_position"] or 0)
                except (ValueError, TypeError):
                    pass
        elif side_upper == "NO":
            if "no_sub_position" in pos_entry and pos_entry["no_sub_position"] is not None:
                try:
                    return float(pos_entry["no_sub_position"] or 0)
                except (ValueError, TypeError):
                    pass

        pos_side = str(pos_entry.get("side", "")).upper().strip()
        raw_val = pos_entry.get("position_fp", pos_entry.get("position", pos_entry.get("position_count", pos_entry.get("count", 0))))
        try:
            val = float(raw_val or 0)
        except (ValueError, TypeError):
            val = 0.0

        if pos_side == side_upper:
            return abs(val)
        elif pos_side and pos_side != side_upper:
            return 0.0

        # Signed convention without explicit side: positive = YES, negative = NO
        if side_upper == "YES":
            return max(0.0, val)
        else:
            return max(0.0, -val)

    def _reconcile_after_timeout(
        self,
        ticker: str,
        client_order_id: str,
        side: str,
        pre_positions: Optional[list] = None,
        requested_count: float = 1.0,
        action: str = "BUY",
        price: Optional[float] = None,
        slippage_buffer: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Reconciles order status against live exchange positions following a network timeout.
        If a position change matching the attempted order is verified, returns a success
        response matching the standard fill response shape with source='reconciled_after_timeout'.
        Returns None if no matching exchange position change can be confirmed.
        """
        try:
            post_res = self.get_positions()
            if not post_res.get("success"):
                logger.warning(f"[KalshiTrader] Reconciliation failed to fetch live positions: {post_res.get('error')}")
                return None

            post_positions = post_res.get("positions", [])
            pre_positions = pre_positions or []

            def _find_pos(pos_list, tk):
                for p in pos_list:
                    if isinstance(p, dict):
                        p_tk = str(p.get("ticker", "")).strip() or str(p.get("market_ticker", "")).strip()
                        if p_tk == str(tk).strip():
                            return p
                return {}

            pre_pos_entry = _find_pos(pre_positions, ticker)
            post_pos_entry = _find_pos(post_positions, ticker)

            pre_qty = self._extract_side_position(pre_pos_entry, side)
            post_qty = self._extract_side_position(post_pos_entry, side)

            side_upper = str(side or "").upper().strip()
            action_upper = str(action or "BUY").upper().strip()

            if action_upper == "BUY":
                delta = post_qty - pre_qty
                if delta > 0:
                    fill_count = round(delta, 2)
                    fill_price = float(price if price is not None else 0.50)
                    fill_cost = round(fill_price * fill_count, 4)
                    buf = float(slippage_buffer if slippage_buffer is not None else 0.04)
                    logger.info(
                        f"[KalshiTrader] Reconciled timeout for BUY order {client_order_id} on {ticker}: "
                        f"found position increase of {fill_count} {side_upper} (pre: {pre_qty}, post: {post_qty})"
                    )
                    return {
                        "success": True,
                        "mode": "LIVE",
                        "order_id": client_order_id,
                        "client_order_id": client_order_id,
                        "ticker": ticker,
                        "side": side_upper,
                        "action": "BUY",
                        "count": fill_count,
                        "requested_price": price,
                        "filled_price": fill_price,
                        "total_cost": fill_cost,
                        "slippage_buffer": buf,
                        "status": "FILLED",
                        "source": "reconciled_after_timeout",
                        "created_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                        "message": f"Order reconciled after network timeout: confirmed +{fill_count} {side_upper} on {ticker}"
                    }
            elif action_upper in ["CLOSE", "SELL"]:
                delta = pre_qty - post_qty
                if delta > 0:
                    filled_count = round(delta, 2)
                    exit_price = float(price if price is not None else 0.50)
                    remaining = max(0.0, round(requested_count - filled_count, 4))
                    logger.info(
                        f"[KalshiTrader] Reconciled timeout for CLOSE order {client_order_id} on {ticker}: "
                        f"found position decrease of {filled_count} {side_upper} (pre: {pre_qty}, post: {post_qty})"
                    )
                    return {
                        "success": True,
                        "mode": "LIVE",
                        "order_id": client_order_id,
                        "client_order_id": client_order_id,
                        "filled_count": filled_count,
                        "remaining_count": remaining,
                        "exit_price": round(exit_price, 4),
                        "fee_paid": 0.0,
                        "source": "reconciled_after_timeout",
                        "message": f"Position close reconciled after network timeout: confirmed -{filled_count} {side_upper} on {ticker}"
                    }
        except Exception as err:
            logger.error(f"[KalshiTrader] Error during timeout reconciliation for {ticker}: {err}", exc_info=True)

        return None

    def _lookup_order_fill(self, ticker: str, client_order_id: str) -> Optional[Dict[str, Any]]:
        """Best-effort: find our own order by client_order_id and return its filled count.
        Only ever used to CONFIRM a fill after a lost response - never to deny one - so any
        error or unexpected response shape simply returns None and the caller falls back to
        the position check / ambiguous handling."""
        if not client_order_id:
            return None
        try:
            path = "/trade-api/v2/portfolio/orders"
            headers = self._sign_headers("GET", path)
            resp = self.session.get(f"{BASE_URL}{path}", params={"ticker": ticker, "limit": 100},
                                    headers=headers, timeout=5.0)
            if resp.status_code != 200:
                return None
            for order in (resp.json() or {}).get("orders", []) or []:
                if str(order.get("client_order_id", "")) != str(client_order_id):
                    continue
                fill = None
                for key in ("fill_count", "fill_count_fp", "taker_fill_count"):
                    if order.get(key) not in (None, ""):
                        try:
                            fill = float(order.get(key))
                            break
                        except (TypeError, ValueError):
                            pass
                if fill is None:
                    try:
                        fill = float(order.get("initial_count")) - float(order.get("remaining_count"))
                    except (TypeError, ValueError):
                        fill = None
                if fill and fill > 0:
                    return {"count": round(fill, 2), "order_id": order.get("order_id", client_order_id)}
                return None
        except Exception as e:
            logger.debug(f"[KalshiTrader] Order lookup by client_order_id failed for {ticker}: {e}")
        return None

    def _resolve_uncertain_buy(
        self,
        ticker: str,
        client_order_id: str,
        side: str,
        pre_positions: Optional[list],
        requested_count: float,
        price: float,
        slippage_buffer: float,
        err: Any,
    ) -> Dict[str, Any]:
        """A BUY request left our process but we never got a trustworthy answer (timeout,
        dropped connection, unreadable response...). Kalshi may have filled it. Try to confirm
        a fill (by order id, then by position change - retried once, since positions can lag
        a moment behind the fill). If nothing can be confirmed, return `ambiguous: True`, which
        callers must treat as "possibly traded" - never as a clean rejection they can retry."""
        for attempt in range(2):
            found = self._lookup_order_fill(ticker, client_order_id)
            if found:
                fill_count = found["count"]
                logger.info(f"[KalshiTrader] Confirmed fill after lost response via order lookup: "
                            f"{fill_count} {side.upper()} on {ticker} (client_order_id={client_order_id})")
                return {
                    "success": True,
                    "mode": "LIVE",
                    "order_id": found.get("order_id", client_order_id),
                    "client_order_id": client_order_id,
                    "ticker": ticker,
                    "side": side.upper(),
                    "action": "BUY",
                    "count": fill_count,
                    "requested_price": price,
                    "filled_price": price,
                    "total_cost": round(price * fill_count, 4),
                    "slippage_buffer": slippage_buffer,
                    "status": "FILLED",
                    "source": "reconciled_by_order_lookup",
                    "created_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                }
            reconciled = self._reconcile_after_timeout(
                ticker=ticker,
                client_order_id=client_order_id,
                side=side,
                pre_positions=pre_positions,
                requested_count=float(requested_count),
                action="BUY",
                price=price,
                slippage_buffer=slippage_buffer,
            )
            if reconciled is not None:
                return reconciled
            if attempt == 0:
                if not getattr(self, "fail_fast", False):
                    time.sleep(1.5)
        logger.error(f"[KalshiTrader] BUY outcome UNKNOWN for {ticker} (client_order_id={client_order_id}): {err}")
        return {
            "success": False,
            "error": f"Order outcome could not be confirmed ({err}). "
                     f"MANUAL VERIFICATION REQUIRED — check Kalshi positions before retrying.",
            "ambiguous": True,
            "client_order_id": client_order_id,
            "ticker": ticker,
        }
    def place_order(self, *args, **kwargs) -> Dict[str, Any]:
        with self._order_submit_lock:
            return self._place_order_internal(*args, **kwargs)

    def place_sports_order(self, *args, **kwargs) -> Dict[str, Any]:
        with self._order_submit_lock:
            return self._place_sports_order_internal(*args, **kwargs)

    def _place_sports_order_internal(
        self,
        ticker: str,
        side: str,  # 'yes' or 'no'
        count: int = 1,
        limit_price_dollars: Optional[float] = None,
        dry_run: bool = True,
        order_type: str = "limit",
        slippage_buffer_dollars: Optional[float] = None,
        available_balance: Optional[float] = None,
        fail_fast: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Executes an order on an exact Kalshi sports market contract (e.g. KXNFLGAME-..., KXATPMATCH-..., KXMLB-...).
        In dry_run=True, simulates fill against live quote or provided price.
        In dry_run=False, verifies the exact market on Kalshi, checks balance on Exchange 0 (Main/Cash),
        signs and submits an IOC limit order to Kalshi's V2 trade API.
        """
        use_fail_fast = self.fail_fast if fail_fast is None else fail_fast
        try:
            if not isinstance(count, (int, float)) or count <= 0:
                return {"success": False, "error": f"Invalid order count: {count}. Must be a positive whole integer."}
            if isinstance(count, float) and not count.is_integer():
                return {"success": False, "error": f"Invalid fractional contract count: {count}. Kalshi event contracts require whole integers."}
            count_int = int(count)
        except Exception:
            return {"success": False, "error": f"Invalid order count: {count}."}

        clean_ticker = str(ticker or "").strip()
        if not clean_ticker:
            return {"success": False, "error": "Missing sports market ticker."}

        side_clean = str(side or "").lower().strip()
        if side_clean not in ["yes", "no"]:
            return {"success": False, "error": f"Invalid side: {side}. Must be 'yes' or 'no'."}

        client_order_id = str(uuid.uuid4())
        buf = 0.04
        if slippage_buffer_dollars is not None:
            try:
                buf = max(0.0, min(float(slippage_buffer_dollars), 0.15))
            except (ValueError, TypeError):
                buf = 0.04

        # 1. Check for dummy/paper synthetic tickers
        is_dummy = (
            clean_ticker.startswith("KALSHI-") or
            clean_ticker.endswith("-MKT") or
            clean_ticker.endswith("_SYNTH") or
            not clean_ticker.startswith("KX")
        )

        if dry_run:
            sim_price = float(limit_price_dollars) if (limit_price_dollars is not None and 0.01 <= float(limit_price_dollars) <= 0.99) else 0.50
            if not is_dummy:
                try:
                    q = self.get_market_quote(clean_ticker)
                    if q.get("success"):
                        m_obj = q.get("market", {})
                        if side_clean == "yes":
                            ask_val = m_obj.get("yes_ask_dollars") or (float(m_obj.get("yes_ask", 0)) / 100.0 if m_obj.get("yes_ask") else None) or m_obj.get("last_price_dollars")
                        else:
                            ask_val = m_obj.get("no_ask_dollars") or (float(m_obj.get("no_ask", 0)) / 100.0 if m_obj.get("no_ask") else None) or (1.0 - float(m_obj.get("last_price_dollars", 0.5)))
                        if ask_val is not None and 0.01 <= float(ask_val) <= 0.99:
                            sim_price = round(float(ask_val), 4)
                except Exception:
                    pass

            cost = round(sim_price * count_int, 4)
            return {
                "success": True,
                "mode": "PAPER",
                "order_id": f"sim_sports_{int(time.time())}_{uuid.uuid4().hex[:8]}",
                "client_order_id": client_order_id,
                "ticker": clean_ticker,
                "side": side_clean.upper(),
                "action": "BUY",
                "count": count_int,
                "requested_count": count_int,
                "requested_price": sim_price,
                "filled_price": sim_price,
                "total_cost": cost,
                "slippage_buffer": buf,
                "status": "FILLED (SIMULATED)",
                "created_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                "message": f"Simulated sports BUY of {count_int} {side_clean.upper()} on {clean_ticker} @ ${sim_price:.2f}"
            }

        # 2. LIVE order execution
        if is_dummy:
            return {
                "success": False,
                "error": f"Cannot execute live order on synthetic or non-Kalshi ticker '{clean_ticker}'."
            }

        if not self.is_authenticated():
            return {
                "success": False,
                "error": "Kalshi API credentials not configured or private key invalid."
            }

        quote_res = self.get_market_quote(clean_ticker)
        if not quote_res.get("success"):
            # Clean ticker might be an event ticker (e.g. KXATPMATCH-26OCT05BELMUL) rather than a market ticker.
            # Attempt event lookup to resolve market ticker.
            try:
                ev_path = f"/trade-api/v2/events/{quote(clean_ticker, safe='')}"
                headers = {"Accept": "application/json", "User-Agent": "ApexProps-Trader/1.0"}
                if self.is_authenticated():
                    try:
                        headers = self._sign_headers("GET", ev_path)
                    except Exception:
                        pass
                ev_resp = self.session.get(
                    f"{BASE_URL}{ev_path}",
                    params={"with_nested_markets": True},
                    headers=headers,
                    timeout=5.0
                )
                if ev_resp.status_code == 200:
                    ev_data = ev_resp.json().get("event", {})
                    ev_markets = ev_data.get("markets", [])
                    if ev_markets:
                        open_markets = [m for m in ev_markets if str(m.get("status") or "").lower() in ("active", "open")]
                        cand_markets = open_markets if open_markets else ev_markets
                        chosen_m = cand_markets[0]
                        resolved_ticker = chosen_m.get("ticker")
                        if resolved_ticker:
                            logger.info(f"[KalshiTrader] Resolved event ticker '{clean_ticker}' to market ticker '{resolved_ticker}'")
                            clean_ticker = resolved_ticker
                            quote_res = self.get_market_quote(clean_ticker)
            except Exception as ev_err:
                logger.warning(f"[KalshiTrader] Failed event fallback lookup for {clean_ticker}: {ev_err}")

        if not quote_res.get("success"):
            return {
                "success": False,
                "error": f"Market '{clean_ticker}' verification failed: {quote_res.get('error', 'Market not open')}"
            }

        market_info = quote_res.get("market", {})
        close_time_str = market_info.get("close_time")
        if close_time_str:
            try:
                ct = datetime.fromisoformat(close_time_str.replace("Z", "+00:00"))
                sec_left = (ct - datetime.now(timezone.utc)).total_seconds()
                if sec_left < 30:
                    return {
                        "success": False,
                        "error": f"Sports market '{clean_ticker}' expires in {int(sec_left)}s (< 30s remaining). Order rejected."
                    }
            except Exception as e:
                logger.debug(f"close_time parse error: {e}")

        if side_clean == "yes":
            m_ask = market_info.get("yes_ask_dollars")
            if m_ask is None and market_info.get("yes_ask") is not None:
                m_ask = float(market_info.get("yes_ask")) / 100.0
            if m_ask is None:
                m_ask = market_info.get("last_price_dollars")
        else:
            m_ask = market_info.get("no_ask_dollars")
            if m_ask is None and market_info.get("no_ask") is not None:
                m_ask = float(market_info.get("no_ask")) / 100.0
            if m_ask is None and market_info.get("last_price_dollars") is not None:
                m_ask = round(1.0 - float(market_info.get("last_price_dollars")), 4)

        try:
            market_ask_flt = float(m_ask) if m_ask is not None else 0.50
        except (ValueError, TypeError):
            market_ask_flt = 0.50

        if limit_price_dollars is not None and 0.01 <= float(limit_price_dollars) <= 0.99:
            raw_price = float(limit_price_dollars)
        else:
            raw_price = market_ask_flt

        outcome_price = max(0.01, min(raw_price + buf, 0.99))

        bal_res = self.get_balance(force_refresh=True)
        if not bal_res.get("success"):
            return {
                "success": False,
                "error": f"Unable to verify Kalshi live balance: {bal_res.get('error', 'Balance error')}"
            }

        target_ex = market_info.get("exchange_index")
        if target_ex is None:
            target_ex = 0
        else:
            try:
                target_ex = int(target_ex)
            except (ValueError, TypeError):
                target_ex = 0

        raw_bal = bal_res.get("raw", {})
        breakdown = raw_bal.get("balance_breakdown", [])

        total_live_bal = float(bal_res.get("balance_dollars", 0.0))
        ex0_bal = total_live_bal
        shard_bal = total_live_bal if target_ex == 0 else 0.0

        for b_item in breakdown:
            try:
                b_idx = int(b_item.get("exchange_index", 0))
                b_val = float(b_item.get("balance", 0.0))
                if b_idx == 0:
                    ex0_bal = b_val
                if b_idx == target_ex:
                    shard_bal = b_val
            except (ValueError, TypeError):
                pass

        est_cost = outcome_price * count_int

        # If order is on a non-zero exchange shard and balance on that shard is insufficient,
        # automatically transfer required funds from Exchange 0 (Main/Cash)
        if target_ex != 0 and shard_bal < est_cost:
            needed = round(math.ceil((est_cost - shard_bal) * 100) / 100.0, 2)
            if ex0_bal < needed:
                return {
                    "success": False,
                    "error": f"Insufficient funds on Exchange {target_ex} (${shard_bal:.2f}) and Exchange 0 (${ex0_bal:.2f}) to cover required ${est_cost:.2f}."
                }
            logger.info(f"[KalshiTrader] Auto-transferring ${needed:.2f} from Exchange 0 to Exchange {target_ex} for sports order...")
            transfer_res = self.transfer_between_exchanges(
                source_exchange=0,
                destination_exchange=target_ex,
                amount_dollars=needed
            )
            if not transfer_res.get("success"):
                return {
                    "success": False,
                    "error": f"Auto-transfer of ${needed:.2f} to Exchange {target_ex} failed: {transfer_res.get('error')}"
                }
            shard_bal = round(shard_bal + needed, 2)

        live_balance = shard_bal if target_ex != 0 else ex0_bal
        if live_balance < est_cost:
            return {
                "success": False,
                "error": f"Insufficient funds: Balance ${live_balance:.2f} is less than required ${est_cost:.2f}."
            }

        v2_side = "bid" if side_clean == "yes" else "ask"
        book_price = outcome_price if side_clean == "yes" else (1.0 - outcome_price)
        v2_payload = {
            "ticker": clean_ticker,
            "client_order_id": client_order_id,
            "side": v2_side,
            "count": f"{count_int}.00",
            "price": f"{book_price:.4f}",
            "time_in_force": "immediate_or_cancel",
            "self_trade_prevention_type": "taker_at_cross",
            "post_only": False,
            "cancel_order_on_pause": True,
            "reduce_only": False,
        }
        if target_ex is not None:
            v2_payload["exchange_index"] = target_ex

        pre_positions = []
        try:
            pre_res = self.get_positions()
            if pre_res.get("success"):
                pre_positions = pre_res.get("positions", [])
        except Exception as pre_err:
            logger.warning(f"[KalshiTrader] Failed to snapshot pre-order positions: {pre_err}")

        path = "/trade-api/v2/portfolio/events/orders"
        sent_cid = None
        sent_price = outcome_price
        max_order_attempts = 1 if use_fail_fast else 3
        order_backoff = 1.0

        try:
            for order_attempt in range(1, max_order_attempts + 1):
                headers = self._sign_headers("POST", path)
                sent_cid = client_order_id
                resp = self.order_session.post(f"{BASE_URL}{path}", json=v2_payload, headers=headers, timeout=5.0)
                if resp.status_code == 429:
                    if use_fail_fast:
                        logger.warning("[KalshiTrader] place_sports_order received HTTP 429 (fail_fast=True). Failing fast without sleep.")
                        return {
                            "success": False,
                            "error": f"Kalshi 429 rate limit exceeded: {resp.text}",
                            "status_code": 429,
                            "ambiguous": False
                        }
                    if order_attempt < max_order_attempts:
                        logger.warning(f"[KalshiTrader] place_sports_order received HTTP 429, backing off {order_backoff:.1f}s...")
                        time.sleep(order_backoff)
                        order_backoff *= 2.0
                        continue
                break

            if resp.status_code in [200, 201]:
                self._cached_balance_time = 0.0
                res_data = resp.json()
                fill_count = float(res_data.get("fill_count", "0") or "0")
                if fill_count == 0:
                    try:
                        fresh_q = self.get_market_quote(clean_ticker)
                        if fresh_q.get("success"):
                            fresh_m = fresh_q.get("market", {})
                            if side_clean == "yes":
                                fresh_ask = fresh_m.get("yes_ask_dollars") or (float(fresh_m.get("yes_ask", 0)) / 100.0 if fresh_m.get("yes_ask") else None)
                            else:
                                fresh_ask = fresh_m.get("no_ask_dollars") or (float(fresh_m.get("no_ask", 0)) / 100.0 if fresh_m.get("no_ask") else None)
                            if fresh_ask is not None:
                                f_ask = float(fresh_ask)
                                if 0.02 <= f_ask <= 0.95 and abs(f_ask - raw_price) <= 0.06:
                                    retry_price = max(0.01, min(f_ask + buf, 0.99))
                                    retry_bp = retry_price if side_clean == "yes" else (1.0 - retry_price)
                                    retry_cid = str(uuid.uuid4())
                                    new_payload = dict(v2_payload)
                                    new_payload["client_order_id"] = retry_cid
                                    new_payload["price"] = f"{retry_bp:.4f}"
                                    sent_cid = retry_cid
                                    sent_price = retry_price
                                    retry_resp = self.order_session.post(f"{BASE_URL}{path}", json=new_payload, headers=self._sign_headers("POST", path), timeout=5.0)
                                    if retry_resp.status_code in [200, 201]:
                                        retry_data = retry_resp.json()
                                        retry_fill = float(retry_data.get("fill_count", "0") or "0")
                                        if retry_fill > 0:
                                            avg_r_fill = float(retry_data.get("average_fill_price", str(retry_bp)) or str(retry_bp))
                                            avg_r_outcome = round(avg_r_fill if side_clean == "yes" else (1.0 - avg_r_fill), 4)
                                            return {
                                                "success": True,
                                                "mode": "LIVE",
                                                "order_id": retry_data.get("order_id", retry_cid),
                                                "client_order_id": retry_data.get("client_order_id", retry_cid),
                                                "ticker": clean_ticker,
                                                "side": side_clean.upper(),
                                                "action": "BUY",
                                                "count": retry_fill,
                                                "requested_count": count_int,
                                                "requested_price": f_ask,
                                                "filled_price": avg_r_outcome,
                                                "total_cost": round(avg_r_outcome * retry_fill, 4),
                                                "slippage_buffer": buf,
                                                "status": "FILLED",
                                                "created_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                                                "raw_response": retry_data
                                            }
                    except Exception as retry_err:
                        logger.warning(f"[KalshiTrader] Sports IOC retry error: {retry_err}")
                        if sent_cid != client_order_id:
                            return self._resolve_uncertain_buy(
                                ticker=clean_ticker, client_order_id=sent_cid, side=side_clean,
                                pre_positions=pre_positions, requested_count=float(count_int),
                                price=sent_price, slippage_buffer=buf, err=retry_err,
                            )
                    return {
                        "success": False,
                        "error": "Kalshi Order Unfilled: IOC limit order did not cross the book due to price movement or low liquidity.",
                        "raw_response": res_data
                    }

                avg_book_fill = float(res_data.get("average_fill_price", str(book_price)) or str(book_price))
                avg_outcome_fill = round(avg_book_fill if side_clean == "yes" else (1.0 - avg_book_fill), 4)
                return {
                    "success": True,
                    "mode": "LIVE",
                    "order_id": res_data.get("order_id", client_order_id),
                    "client_order_id": res_data.get("client_order_id", client_order_id),
                    "ticker": clean_ticker,
                    "side": side_clean.upper(),
                    "action": "BUY",
                    "count": fill_count,
                    "requested_count": count_int,
                    "requested_price": raw_price,
                    "filled_price": avg_outcome_fill,
                    "total_cost": round(avg_outcome_fill * fill_count, 4),
                    "slippage_buffer": buf,
                    "status": "FILLED",
                    "created_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                    "raw_response": res_data
                }
            else:
                err_text = resp.text
                user_msg = err_text
                try:
                    err_json = resp.json()
                    user_msg = err_json.get("error", {}).get("message") or err_json.get("message") or err_text
                except Exception:
                    pass
                return {
                    "success": False,
                    "order_id": "",
                    "ambiguous": False,
                    "error": f"Kalshi Order Rejected (HTTP {resp.status_code}): {user_msg}",
                    "payload_sent": v2_payload
                }
        except requests.exceptions.ConnectTimeout as e:
            return {
                "success": False,
                "order_id": "",
                "ambiguous": False,
                "error": f"Could not reach Kalshi (connect timeout); order not sent: {e}"
            }
        except Exception as e:
            if sent_cid is None:
                return {
                    "success": False,
                    "order_id": "",
                    "ambiguous": False,
                    "error": f"Order execution exception before sending: {str(e)}"
                }
            logger.warning(
                f"[KalshiTrader] Lost response for sports order {sent_cid} on {clean_ticker} ({type(e).__name__}: {e}). Checking for fill..."
            )
            return self._resolve_uncertain_buy(
                ticker=clean_ticker, client_order_id=sent_cid, side=side_clean,
                pre_positions=pre_positions, requested_count=float(count_int),
                price=sent_price, slippage_buffer=buf, err=e,
            )

    def _place_order_internal(
        self,
        ticker: str,
        side: str,  # 'yes' or 'no'
        count: int = 1,
        limit_price_dollars: Optional[float] = None,
        dry_run: bool = True,
        order_type: str = "limit",
        slippage_buffer_dollars: Optional[float] = None,
        available_balance: Optional[float] = None,
        fail_fast: Optional[bool] = None
    ) -> Dict[str, Any]:
        use_fail_fast = self.fail_fast if fail_fast is None else fail_fast
        """
        Executes a buy order on the specified contract side (YES = above target, NO = below target).
        In dry_run=True, simulates the trade against the same real-market constraints a live order
        would face: a verified, currently-open (non-synthetic) market, the same 30s expiry backstop,
        the same book-crossing slippage buffer plus a small latency tax, a simulated top-of-book depth
        (so a paper order can be partially filled or fully missed), and - if `available_balance` is
        given - a fail-closed affordability check.
        In dry_run=False, signs and sends the order to the Kalshi live API with strict safety bounds.

        `available_balance`: the caller's own balance-store reading (paper_balance.py for the
        single-user bot, a SaaS user's paper balance, etc.). Only used for dry_run; ignored for a
        live order, which checks Kalshi's real balance itself. Omit to skip the affordability check.
        """
        # H5: Validate contract count is a strictly positive whole integer
        try:
            if not isinstance(count, (int, float)) or count <= 0:
                return {"success": False, "error": f"Invalid order count: {count}. Must be a positive whole integer."}
            if isinstance(count, float) and not count.is_integer():
                return {"success": False, "error": f"Invalid fractional contract count: {count}. Kalshi event contracts require whole integers."}
            count_int = int(count)
        except Exception:
            return {"success": False, "error": f"Invalid order count: {count}."}

        side_clean = side.lower().strip()
        if side_clean not in ["yes", "no"]:
            return {"success": False, "error": f"Invalid side: {side}. Must be 'yes' or 'no'."}

        client_order_id = str(uuid.uuid4())

        # Slippage buffer: Default 0.04 or configurable dollar value clamped safely [0.00, 0.15]
        buf = 0.04
        if slippage_buffer_dollars is not None:
            try:
                buf = max(0.0, min(float(slippage_buffer_dollars), 0.15))
            except (ValueError, TypeError):
                buf = 0.04

        # 1. PAPER TRADING (SIMULATION) - models the same real-market constraints LIVE faces,
        # without requiring an authenticated Kalshi call (many paper-only accounts have no live
        # Kalshi credentials configured at all, so re-verifying via get_active_15m_market() here
        # would make paper trading depend on credentials it doesn't need and doesn't have).
        if dry_run:
            # Expiry backstop, derived from the ticker's own encoded close time (no network call) -
            # KXBTC15M-26SEP271015-15 closes at a time baked right into the ticker string. A ticker
            # that doesn't encode one (a test fixture, or a fabricated "_SYNTH" offline ticker)
            # simply skips this check rather than blocking, since we have nothing real to check it against.
            try:
                from backend.btc.market_results import market_close_epoch
                close_epoch = market_close_epoch(ticker)
            except Exception:
                close_epoch = None
            if close_epoch is not None:
                sec_remaining = close_epoch - time.time()
                if sec_remaining < 30:
                    return {
                        "success": False,
                        "error": f"Contract '{ticker}' expires in {int(sec_remaining)}s (< 30s remaining). Paper order rejected to mirror live behavior."
                    }

            # Fix A chokepoint: synthetic markets have fabricated prices and nothing real to settle
            # against, so no paper order may open on one (LIVE already refuses them).
            if "_SYNTH" in str(ticker).upper():
                return {"success": False, "error": f"'{ticker}' is a synthetic market with no real Kalshi contract; paper orders are disabled to mirror live."}

            # Same book-crossing slippage buffer a live order pays, plus a small fixed latency tax
            # standing in for the adverse drift that happens during a real order's network round
            # trip (paper has no such delay otherwise, which would make it strictly better-priced
            # than live for an identical signal). Rounded to whole cents.
            raw_price = float(limit_price_dollars) if limit_price_dollars is not None else 0.50
            simulated_price = round(max(0.01, min(raw_price + buf + PAPER_LATENCY_TAX_DOLLARS, 0.99)), 2)

            sim_depth = _simulated_book_depth(ticker, f"entry_{side_clean}")
            filled_count = min(count_int, sim_depth) if sim_depth > 0 else count_int
            
            if sim_depth == 0:
                return {
                    "success": False,
                    "error": f"No {side_clean.upper()} liquidity on {ticker} at or below ${min(0.99, raw_price + buf):.2f} (simulated IOC missed, same as live)."
                }
                
            fill_source = "estimated_top_of_book"

            # Fix D: walk Kalshi's real order book up to the same limit a live order would send
            # (ask + slippage buffer). Thin books now partially fill or miss, like a live IOC.
            book_fill = paper_buy_from_book(ticker, side_clean, count_int, min(0.99, raw_price + buf))
            if book_fill is not None:
                book_filled, book_vwap = book_fill
                if book_filled <= 0:
                    return {
                        "success": False,
                        "error": f"No {side_clean.upper()} liquidity on {ticker} at or below ${min(0.99, raw_price + buf):.2f} (simulated IOC missed, same as live).",
                    }
                filled_count = book_filled
                simulated_price = round(max(0.01, min(book_vwap + PAPER_LATENCY_TAX_DOLLARS, raw_price + buf, 0.99)), 4)
                fill_source = "kalshi_order_book"

            cost = round(simulated_price * filled_count, 4)

            # Fail-closed affordability check, mirroring LIVE's own real-balance check (H4 above).
            # Opt-in: only enforced when the caller passes its own balance-store reading.
            if available_balance is not None:
                try:
                    avail = float(available_balance)
                except (TypeError, ValueError):
                    avail = None
                if avail is not None and cost > avail + 1e-9:
                    return {
                        "success": False,
                        "error": f"Insufficient paper balance: ${avail:.2f} available, ${cost:.2f} required."
                    }

            partial_note = ""
            return {
                "success": True,
                "mode": "PAPER",
                "order_id": f"sim_{client_order_id[:8]}",
                "ambiguous": False,
                "client_order_id": client_order_id,
                "ticker": ticker,
                "side": side_clean.upper(),
                "action": "BUY",
                "count": filled_count,
                "requested_count": count_int,
                "requested_price": raw_price,
                "filled_price": simulated_price,
                "total_cost": cost,
                "slippage_buffer": buf,
                "latency_tax": PAPER_LATENCY_TAX_DOLLARS,
                "fill_source": fill_source,
                "status": "FILLED (SIMULATED)" if filled_count == count_int else "PARTIALLY FILLED (SIMULATED)",
                "created_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                "message": f"Simulated BUY of {filled_count} {side_clean.upper()} on {ticker} @ ${simulated_price:.2f}"
            }

        # Extract series_ticker from the passed ticker (e.g., "KXETH15M-..." -> "KXETH15M")
        series_t = "KXBTC15M"
        if ticker and ticker.startswith("KX"):
            series_t = ticker.split("-")[0]

        # Non-15M contracts (such as sports markets) route to sports order handler
        if not series_t.endswith("15M"):
            return self._place_sports_order_internal(
                ticker=ticker,
                side=side,
                count=count,
                limit_price_dollars=limit_price_dollars,
                dry_run=dry_run,
                slippage_buffer_dollars=slippage_buffer_dollars,
                available_balance=available_balance
            )

        # Fast-Path: Use active market (from cache or fast fetch) without redundant GET roundtrips
        # Requires at least 30s before expiration to prevent entering dying contracts
        verified_market = self.get_active_15m_market(series_ticker=series_t, allow_synthetic=False, force_refresh=False, min_seconds_left=30)
        if not verified_market or verified_market.get("is_synthetic"):
            # Fallback to force refresh if cache empty
            verified_market = self.get_active_15m_market(series_ticker=series_t, allow_synthetic=False, force_refresh=True, min_seconds_left=30)
            if not verified_market or verified_market.get("is_synthetic"):
                return {
                    "success": False,
                    "error": f"No verified open Kalshi {series_t} market is available (>30s remaining required). Live order was not submitted."
                }
        
        verified_ticker = verified_market.get("ticker") or verified_market.get("event_ticker", "")
        if not verified_ticker:
            return {"success": False, "error": "Verified market missing ticker information."}

        # Safeguard: Reject order if contract expires in less than 30 seconds
        close_time_str = verified_market.get("close_time")
        if close_time_str:
            try:
                ct = datetime.fromisoformat(close_time_str.replace("Z", "+00:00"))
                sec_remaining = (ct - datetime.now(timezone.utc)).total_seconds()
                if sec_remaining < 30:
                    logger.warning(
                        f"[KalshiTrader] Refusing to place order: contract '{verified_ticker}' expires in {sec_remaining:.1f}s (< 30s remaining)."
                    )
                    return {
                        "success": False,
                        "error": f"Contract '{verified_ticker}' expires in {int(sec_remaining)}s (< 30s remaining). Live order rejected to prevent instant settlement."
                    }
            except Exception as e:
                logger.debug(f"close_time_str parse error: {e}")
            
        if ticker and ticker.strip() and ticker.strip() != verified_ticker:
            logger.warning(
                f"[KalshiTrader] place_order() called with ticker='{ticker}' but verified active market is '{verified_ticker}'. Using verified ticker."
            )
        ticker = verified_ticker
        
        # Clamp price with slippage buffer to guarantee Immediate-Or-Cancel (IOC) book cross
        raw_price = float(limit_price_dollars if limit_price_dollars else 0.65)
        outcome_price = max(0.01, min(raw_price + buf, 0.99))

        # H4: Fail-closed balance check on live trading
        bal_res = self.get_balance(force_refresh=True)
        if not bal_res.get("success"):
            return {
                "success": False,
                "error": f"Live order aborted: Unable to verify Kalshi account balance ({bal_res.get('error', 'Balance check failed')})."
            }
        live_balance = float(bal_res.get("balance_dollars", 0.0))
        target_ex = verified_market.get("exchange_index")
        if target_ex is not None:
            for b_item in bal_res.get("raw", {}).get("balance_breakdown", []):
                if b_item.get("exchange_index") == target_ex:
                    live_balance = min(live_balance, float(b_item.get("balance", live_balance)))
                    break
        est_cost = outcome_price * count_int

        if live_balance < est_cost:
            return {
                "success": False,
                "error": f"Insufficient funds: Balance ${live_balance:.2f} on exchange {target_ex} is less than required ${est_cost:.2f}."
            }

        # V2 endpoint: POST /portfolio/events/orders
        # The V2 event book is always quoted from the YES side. "ask" is
        # economically a buy-NO, so a NO price must be converted to its
        # complementary YES price before submission.
        # count: fixed-point count string e.g. "1.00"
        v2_side = "bid" if side_clean == "yes" else "ask"
        book_price = outcome_price if side_clean == "yes" else (1.0 - outcome_price)
        v2_payload = {
            "ticker": ticker,
            "client_order_id": client_order_id,
            "side": v2_side,
            "count": f"{count_int}.00",
            "price": f"{book_price:.4f}",
            "time_in_force": "immediate_or_cancel",
            "self_trade_prevention_type": "taker_at_cross",
            "post_only": False,
            "cancel_order_on_pause": True,
            "reduce_only": False,
        }
        if "exchange_index" in verified_market and verified_market["exchange_index"] is not None:
            v2_payload["exchange_index"] = verified_market["exchange_index"]

        pre_positions = []
        try:
            pre_res = self.get_positions()
            if pre_res.get("success"):
                pre_positions = pre_res.get("positions", [])
        except Exception as pre_err:
            logger.warning(f"[KalshiTrader] Failed to snapshot pre-order positions: {pre_err}")

        path = "/trade-api/v2/portfolio/events/orders"
        # M-AMBIG: once a request has left this process, any failure to read a clean answer
        # means Kalshi MAY have filled it. Track which order was last sent so every such
        # failure is resolved as "confirmed fill" or "ambiguous", never as a clean rejection.
        sent_cid = None
        sent_price = outcome_price
        max_order_attempts = 1 if use_fail_fast else 3
        order_backoff = 1.0
        try:
            for order_attempt in range(1, max_order_attempts + 1):
                headers = self._sign_headers("POST", path)
                # H6: Use order_session (max_retries=0) for mutating orders
                sent_cid = client_order_id
                resp = self.order_session.post(f"{BASE_URL}{path}", json=v2_payload, headers=headers, timeout=5.0)

                if resp.status_code == 429:
                    if use_fail_fast:
                        logger.warning(
                            f"[KalshiTrader] place_order received HTTP 429 (fail_fast=True). Failing fast without sleep."
                        )
                        return {
                            "success": False,
                            "error": f"Kalshi 429 rate limit exceeded: {resp.text}",
                            "status_code": 429,
                            "ambiguous": False
                        }
                    if order_attempt < max_order_attempts:
                        logger.warning(
                            f"[KalshiTrader] place_order received HTTP 429, backing off for {order_backoff:.1f}s "
                            f"(attempt {order_attempt}/{max_order_attempts})..."
                        )
                        time.sleep(order_backoff)
                        order_backoff *= 2.0
                        continue
                break

            if resp.status_code in [200, 201]:
                self._cached_balance_time = 0.0
                self._cached_market_times = {}
                res_data = resp.json()
                fill_count = float(res_data.get("fill_count", "0") or "0")
                if fill_count == 0:
                    # ── FAST RETRY FOR IOC ORDERS ──
                    # If IOC order unfilled due to sub-second price movement, re-query active market and retry once
                    try:
                        fresh_market = self.get_active_15m_market(series_ticker=series_t, allow_synthetic=False, force_refresh=True, min_seconds_left=20)
                        if fresh_market:
                            fresh_ask = float(fresh_market.get(f"{side_clean}_ask") or 0.0)
                            if 0.02 <= fresh_ask <= 0.90 and abs(fresh_ask - raw_price) <= 0.06:
                                retry_count = count_int
                                new_outcome_price = max(0.01, min(fresh_ask + buf, 0.99))
                                new_cost = new_outcome_price * retry_count
                                if live_balance < new_cost:
                                    retry_count = int(live_balance / max(0.01, new_outcome_price))
                                
                                if retry_count >= 1:
                                    logger.info(f"[KalshiTrader] IOC unfilled at ${outcome_price:.2f}. Retrying once with fresh ask ${fresh_ask:.2f} (limit: ${new_outcome_price:.2f}, contracts: {retry_count}) for {ticker}...")
                                    new_book_price = new_outcome_price if side_clean == "yes" else (1.0 - new_outcome_price)
                                    retry_cid = str(uuid.uuid4())
                                    new_payload = dict(v2_payload)
                                    new_payload["client_order_id"] = retry_cid
                                    new_payload["count"] = f"{retry_count}.00"
                                    new_payload["price"] = f"{new_book_price:.4f}"
                                    
                                    retry_headers = self._sign_headers("POST", path)
                                    # From here on the retry is "sent": an error resolves it as ambiguous.
                                    sent_cid = retry_cid
                                    sent_price = new_outcome_price
                                    retry_resp = self.order_session.post(f"{BASE_URL}{path}", json=new_payload, headers=retry_headers, timeout=5.0)
                                    if retry_resp.status_code in [200, 201]:
                                        retry_data = retry_resp.json()
                                        retry_fill = float(retry_data.get("fill_count", "0") or "0")
                                        if retry_fill > 0:
                                            avg_retry_fill = float(retry_data.get("average_fill_price", str(new_book_price)) or str(new_book_price))
                                            avg_retry_outcome = round(
                                                avg_retry_fill if side_clean == "yes" else (1.0 - avg_retry_fill),
                                                4,
                                            )
                                            logger.info(f"[KalshiTrader] IOC retry SUCCEEDED: filled {retry_fill} {side_clean.upper()} @ ${avg_retry_outcome:.2f}")
                                            return {
                                                "success": True,
                                                "mode": "LIVE",
                                                "order_id": retry_data.get("order_id", retry_cid),
                                                "ambiguous": False,
                                                "client_order_id": retry_data.get("client_order_id", retry_cid),
                                                "ticker": ticker,
                                                "side": side_clean.upper(),
                                                "action": "BUY",
                                                "count": retry_fill,
                                                "requested_price": fresh_ask,
                                                "filled_price": avg_retry_outcome,
                                                "total_cost": round(avg_retry_outcome * retry_fill, 4),
                                                "slippage_buffer": buf,
                                                "status": "FILLED",
                                                "created_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                                                "raw_response": retry_data
                                            }
                    except Exception as retry_err:
                        logger.warning(f"[KalshiTrader] IOC retry error: {retry_err}")
                        if sent_cid != client_order_id:
                            # The retry order itself was sent and we lost its answer - it may
                            # have filled. (The first order is known unfilled: fill_count == 0.)
                            return self._resolve_uncertain_buy(
                                ticker=ticker, client_order_id=sent_cid, side=side_clean,
                                pre_positions=pre_positions, requested_count=float(count_int),
                                price=sent_price, slippage_buffer=buf, err=retry_err,
                            )

                    return {
                        "success": False,
                        "error": "Kalshi Order Unfilled: IOC limit order did not cross the book due to price movement or low liquidity.",
                        "raw_response": res_data
                    }

                avg_book_fill = float(res_data.get("average_fill_price", str(book_price)) or str(book_price))
                avg_outcome_fill = round(
                    avg_book_fill if side_clean == "yes" else (1.0 - avg_book_fill),
                    4,
                )
                return {
                    "success": True,
                    "mode": "LIVE",
                    "order_id": res_data.get("order_id", client_order_id),
                    "ambiguous": False,
                    "client_order_id": res_data.get("client_order_id", client_order_id),
                    "ticker": ticker,
                    "side": side_clean.upper(),
                    "action": "BUY",
                    "count": fill_count,
                    "requested_price": raw_price,
                    "filled_price": avg_outcome_fill,
                    "total_cost": round(avg_outcome_fill * fill_count, 4),
                    "slippage_buffer": buf,
                    "status": "FILLED",
                    "created_at": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                    "raw_response": res_data
                }
            else:
                err_text = resp.text
                if resp.status_code == 409 and "trading_is_paused" in err_text:
                    user_msg = "Kalshi Exchange Maintenance: Trading is paused for weekly maintenance until 5:00 AM EDT. Orders will resume at 5:00 AM EDT."
                elif "market_not_open" in err_text or "not open" in err_text.lower():
                    user_msg = "Kalshi Market Not Open: Waiting for 15M contract open window."
                else:
                    user_msg = err_text
                return {
                    "success": False,
                    "order_id": "",
                    "ambiguous": False,
                    "error": f"Kalshi Order Rejected (HTTP {resp.status_code}): {user_msg}",
                    "payload_sent": v2_payload
                }
        except requests.exceptions.ConnectTimeout as e:
            # The connection was never established, so the order never reached Kalshi.
            return {
                "success": False,
                "order_id": "",
                "ambiguous": False,
                "error": f"Could not reach Kalshi (connect timeout); order not sent: {e}"
            }
        except Exception as e:
            if sent_cid is None:
                return {
                    "success": False,
                    "order_id": "",
                    "ambiguous": False,
                    "error": f"Order execution exception before sending: {str(e)}"
                }
            # Timeout, dropped connection, unreadable/garbled response... after the request
            # was sent. It may have filled - confirm it or report it as ambiguous.
            logger.warning(
                f"[KalshiTrader] Lost the response for order {sent_cid} on {ticker} ({type(e).__name__}: {e}). "
                f"Checking Kalshi for a fill..."
            )
            return self._resolve_uncertain_buy(
                ticker=ticker, client_order_id=sent_cid, side=side_clean,
                pre_positions=pre_positions, requested_count=float(count_int),
                price=sent_price, slippage_buffer=buf, err=e,
            )

def filled_count(order_res: Dict[str, Any], fallback):
    """Contracts actually filled according to a place_order() result. An IOC order (or a
    simulated paper order) can fill only part of what was requested, so records, P&L and
    risk must use this rather than the requested count. Whole numbers come back as ints."""
    try:
        filled = float((order_res or {}).get("count", fallback))
    except (TypeError, ValueError):
        return fallback
    if filled <= 0:
        return fallback
    return int(filled) if filled.is_integer() else round(filled, 2)


kalshi_trader = KalshiTrader()


def get_authenticated_trader_for_user(user_or_id, fail_fast: bool = False) -> Optional[KalshiTrader]:
    """
    Returns an authenticated KalshiTrader instance using the user's RSA keys stored in users.db,
    or None if credentials are missing or invalid.
    """
    try:
        from backend.database.models import get_user_by_id
        from backend.auth.security import decrypt_kalshi_key
        user = get_user_by_id(user_or_id) if isinstance(user_or_id, int) else user_or_id
        if not user:
            return None
        key_id = user.get("kalshi_key_id")
        enc_priv = user.get("kalshi_priv_key_encrypted")
        if not key_id or not enc_priv:
            return None
        priv_pem = decrypt_kalshi_key(enc_priv)
        if not priv_pem:
            return None
        kt = KalshiTrader(key_id=key_id, private_key_pem=priv_pem, fail_fast=fail_fast)
        if kt.is_authenticated():
            return kt
        return None
    except Exception as e:
        logger.error(f"[KalshiTrader] Error resolving authenticated trader for user: {e}")
        return None
