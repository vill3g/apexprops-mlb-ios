import logging

logger = logging.getLogger(__name__)
"""
Kalshi Crypto Event Contracts Client
Pulls live 15-minute Bitcoin price targets and market-implied odds from Kalshi's CFTC-regulated KXBTC15M series.
"""
import threading
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

KALSHI_API_URL = "https://external-api.kalshi.com/trade-api/v2/markets"

_session = requests.Session()
_adapter = HTTPAdapter(pool_connections=20, pool_maxsize=50, max_retries=Retry(total=2, backoff_factor=0.2))
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)

_kalshi_cache = {}
_kalshi_cache_times = {}
_kalshi_cache_lock = threading.Lock()  # FIX #8: protects module-level cache globals from concurrent writes
CACHE_TTL_SEC = 1.0  # 1.0-second cache to deliver real-time 1-second odds updates without hitting Kalshi 429 rate limits

import datetime
import email.utils

_KALSHI_CLOCK_OFFSET_SEC = 0.0
_KALSHI_CLOCK_LAST_SYNC = 0.0
_KALSHI_CLOCK_HAS_SUBSEC = False
_KALSHI_CLOCK_LOCK = threading.Lock()
_KALSHI_CLOCK_SYNCING = False


def _update_offset_from_kalshi_header(resp, req_mid_ts: float) -> None:
    """Updates clock offset from Kalshi HTTP Date header when sub-second sync hasn't run yet."""
    global _KALSHI_CLOCK_OFFSET_SEC, _KALSHI_CLOCK_LAST_SYNC
    try:
        date_hdr = resp.headers.get("Date") if resp is not None else None
        if not date_hdr:
            return
        srv_dt = email.utils.parsedate_to_datetime(date_hdr)
        if srv_dt is None:
            return
        # HTTP Date header has 1-second resolution (truncated); +0.5s centers the expected sub-second value
        est_offset = (srv_dt.timestamp() + 0.5) - req_mid_ts
        with _KALSHI_CLOCK_LOCK:
            if not _KALSHI_CLOCK_HAS_SUBSEC or (time.time() - _KALSHI_CLOCK_LAST_SYNC > 120.0):
                _KALSHI_CLOCK_OFFSET_SEC = est_offset
                _KALSHI_CLOCK_LAST_SYNC = time.time()
    except Exception:
        pass


def sync_exchange_clock_offset(force: bool = False) -> float:
    """
    Synchronizes local system clock against sub-second Exchange / Kalshi UTC time.
    Compensates for Windows OS clock drift (e.g. +22.05s lag) so 15m contract countdowns
    and rollover boundaries match Kalshi's official clock to within <100ms.
    """
    global _KALSHI_CLOCK_OFFSET_SEC, _KALSHI_CLOCK_LAST_SYNC, _KALSHI_CLOCK_HAS_SUBSEC, _KALSHI_CLOCK_SYNCING
    now_local = time.time()
    with _KALSHI_CLOCK_LOCK:
        if not force and _KALSHI_CLOCK_HAS_SUBSEC and _KALSHI_CLOCK_LAST_SYNC > 0 and (now_local - _KALSHI_CLOCK_LAST_SYNC < 60.0):
            return _KALSHI_CLOCK_OFFSET_SEC
        if _KALSHI_CLOCK_SYNCING:
            return _KALSHI_CLOCK_OFFSET_SEC
        _KALSHI_CLOCK_SYNCING = True

    def _do_sync():
        global _KALSHI_CLOCK_OFFSET_SEC, _KALSHI_CLOCK_LAST_SYNC, _KALSHI_CLOCK_HAS_SUBSEC, _KALSHI_CLOCK_SYNCING
        try:
            # 1. Primary sub-second reference: Coinbase Exchange /time endpoint (returns exact millisecond epoch)
            t0 = time.time()
            r = _session.get("https://api.exchange.coinbase.com/time", timeout=1.5)
            t1 = time.time()
            if r.status_code == 200:
                cb_epoch = float(r.json().get("epoch", 0.0))
                if cb_epoch > 1700000000.0:
                    mid = (t0 + t1) / 2.0
                    with _KALSHI_CLOCK_LOCK:
                        _KALSHI_CLOCK_OFFSET_SEC = cb_epoch - mid
                        _KALSHI_CLOCK_LAST_SYNC = t1
                        _KALSHI_CLOCK_HAS_SUBSEC = True
                    return
        except Exception:
            pass
        try:
            # 2. Fallback reference: Kalshi exchange status Date header
            t0 = time.time()
            r = _session.get("https://external-api.kalshi.com/trade-api/v2/exchange/status", timeout=1.5)
            t1 = time.time()
            _update_offset_from_kalshi_header(r, (t0 + t1) / 2.0)
        except Exception:
            pass
        finally:
            with _KALSHI_CLOCK_LOCK:
                _KALSHI_CLOCK_SYNCING = False

    if not _KALSHI_CLOCK_HAS_SUBSEC or _KALSHI_CLOCK_LAST_SYNC == 0.0 or force:
        _do_sync()
    else:
        threading.Thread(target=_do_sync, daemon=True, name="KalshiClockSync").start()

    with _KALSHI_CLOCK_LOCK:
        return _KALSHI_CLOCK_OFFSET_SEC


def get_kalshi_epoch() -> float:
    """Returns current UTC epoch timestamp calibrated to Kalshi/Exchange server time."""
    return time.time() + sync_exchange_clock_offset(force=False)


def get_kalshi_utc_now() -> datetime.datetime:
    """Returns timezone-aware UTC datetime calibrated to Kalshi/Exchange server time."""
    return datetime.datetime.fromtimestamp(get_kalshi_epoch(), tz=datetime.timezone.utc)


from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
import requests.exceptions

@retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(4), retry=retry_if_exception_type((requests.exceptions.RequestException, ValueError)))
def _safe_get(*args, **kwargs):
    t0 = time.time()
    resp = _session.get(*args, **kwargs)
    t1 = time.time()
    _update_offset_from_kalshi_header(resp, (t0 + t1) / 2.0)
    if resp.status_code in [429, 502, 503, 504]:
        logger.warning(f"Kalshi API returned {resp.status_code}, retrying...")
        raise requests.exceptions.RequestException(f"Retryable status {resp.status_code}")
    return resp

def get_kalshi_15m_market(series_ticker: str = "KXBTC15M", allow_synthetic: bool = True, **kwargs):
    """
    Fetch active open KXBTC15M market from Kalshi.
    Returns:
        dict with:
            target_price: float (floor_strike)
            yes_prob: float (percentage 0-100)
            no_prob: float (percentage 0-100)
            ticker: str
            close_time: str
            status: str
            source: str
    """

    now = time.time()
    cal_epoch = get_kalshi_epoch()
    force_refresh = bool(kwargs.get("force_refresh", False))
    # Check cache under lock so concurrent threads don't all fire HTTP requests on expiry.
    with _kalshi_cache_lock:
        if not force_refresh and series_ticker in _kalshi_cache and (now - _kalshi_cache_times.get(series_ticker, 0)) < CACHE_TTL_SEC:
            cached_m = _kalshi_cache.get(series_ticker)
            cached_close_ms = cached_m.get("close_epoch_ms") if isinstance(cached_m, dict) else None
            # Only serve cached market if it hasn't already closed on Kalshi
            if not cached_close_ms or (cached_close_ms / 1000.0) > cal_epoch:
                return cached_m
        # Optimistic stamp: claim this slot so other threads see it as "fresh" and wait
        _kalshi_cache_times[series_ticker] = now

    try:
        markets = []
        try:
            resp = _safe_get(
                KALSHI_API_URL,
                params={"series_ticker": series_ticker, "status": "open"},
                headers={"Accept": "application/json", "User-Agent": "ApexProps-Kalshi-Client/1.0"},
                timeout=2.5
            )
            if resp.status_code == 200:
                markets = resp.json().get("markets", [])
        except Exception as e:
            logger.debug(f"Failed to fetch open markets via REST for {series_ticker}: {e}")

        if not markets:
            try:
                from backend.engine.kalshi_market_cache import get_market_cache_instance, USE_MARKET_CACHE
                if USE_MARKET_CACHE:
                    mc = get_market_cache_instance()
                    cached_series = mc.get_markets_for_series(series_ticker)
                    if cached_series:
                        markets = cached_series
            except Exception:
                pass

        active_m = None
        active_ct = None
        if markets:
            now_utc = get_kalshi_utc_now()
            valid_m = []
            for m in markets:
                ct_str = m.get("close_time")
                if ct_str:
                    try:
                        ct = datetime.datetime.fromisoformat(ct_str.replace("Z", "+00:00"))
                        if ct > now_utc and ct <= now_utc + datetime.timedelta(minutes=30):
                            valid_m.append((ct, m))
                    except Exception as e:
                        logger.debug(f"close_time parse error: {e}")

            if valid_m:
                valid_m.sort(key=lambda x: x[0])
                active_ct, active_m = valid_m[0]

        if not active_m:
            if allow_synthetic:
                cur_p = 0.50
                try:
                    from backend.engine.multi_asset_fetcher import get_asset_ticker
                    raw_asset = series_ticker.replace("KX", "").replace("15M", "")
                    cur_p = float(get_asset_ticker(raw_asset).get("price", 0.50) or 0.50)
                except Exception:
                    cur_p = 0.50
                synth = {
                    "target_price": cur_p,
                    "strike_price": cur_p,
                    "yes_prob": 50.0,
                    "no_prob": 50.0,
                    "yes_bid": 0.50,
                    "yes_ask": 0.50,
                    "no_bid": 0.50,
                    "no_ask": 0.50,
                    "spread": 0.0,
                    "yes_bid_size": 0,
                    "yes_ask_size": 0,
                    "orderbook_imbalance": 0.0,
                    "market_bias": "NEUTRAL",
                    "ticker": f"{series_ticker}_SYNTH",
                    "close_time": "",
                    "status": "synthetic",
                    "volume_24h": 0.0,
                    "open_interest": 0.0,
                    "source": "Kalshi Synthetic"
                }
                return synth
            return None

        floor_strike = active_m.get("floor_strike")
        if floor_strike is not None and float(floor_strike or 0) > 0:
            target_price = float(floor_strike)
        else:
            from backend.btc.data_fetcher import get_live_15m_target_data
            asset = series_ticker.replace("KX", "").replace("15M", "")
            target_data = {}
            try:
                target_data = get_live_15m_target_data(asset)
            except Exception:
                pass
            asset_p = 0.0
            try:
                from backend.engine.multi_asset_fetcher import get_asset_ticker
                asset_p = float(get_asset_ticker(asset).get("price", 0.0) or 0.0)
            except Exception:
                pass
            target_price = float(target_data.get("target_price") or asset_p or 0.50)

        def _parse_dollar_field(m_obj, dollar_key, raw_key, default=0.0):
            vd = m_obj.get(dollar_key)
            if vd is not None and str(vd).strip() != "":
                try:
                    return float(vd)
                except (ValueError, TypeError):
                    pass
            vr = m_obj.get(raw_key)
            if vr is not None and str(vr).strip() != "":
                try:
                    f = float(vr)
                    return f / 100.0 if f > 1.0 else f
                except (ValueError, TypeError):
                    pass
            return default

        # Extract detailed top-of-book order metrics safely (handles both Kalshi REST and MarketCache)
        yes_bid = _parse_dollar_field(active_m, "yes_bid_dollars", "yes_bid", 0.0)
        yes_ask = _parse_dollar_field(active_m, "yes_ask_dollars", "yes_ask", 0.0)
        no_bid = _parse_dollar_field(active_m, "no_bid_dollars", "no_bid", 0.0)
        no_ask = _parse_dollar_field(active_m, "no_ask_dollars", "no_ask", 0.0)
        last_p = _parse_dollar_field(active_m, "last_price_dollars", "last_price", 0.50)

        if yes_bid > 0 and (no_ask <= 0.0 or no_ask >= 1.0):
            no_ask = round(1.0 - yes_bid, 4)
        if yes_ask > 0 and (no_bid <= 0.0 or no_bid >= 1.0):
            no_bid = round(1.0 - yes_ask, 4)

        yes_bid_size = int(float(active_m.get("yes_bid_size") or active_m.get("yes_bid_count") or active_m.get("yes_bid_size_fp") or 0))
        yes_ask_size = int(float(active_m.get("yes_ask_size") or active_m.get("yes_ask_count") or active_m.get("yes_ask_size_fp") or 0))

        if yes_bid > 0 and yes_ask > 0:
            yes_prob = round(((yes_bid + yes_ask) / 2.0) * 100, 1)
        elif last_p > 0:
            yes_prob = round(last_p * 100, 1)
        else:
            yes_prob = 50.0

        no_prob = round(100.0 - yes_prob, 1)

        # Order book metrics
        spread = round(max(0.0, yes_ask - yes_bid), 3) if (yes_bid > 0 and yes_ask > 0) else 0.04
        total_size = yes_bid_size + yes_ask_size
        orderbook_imbalance = round(((yes_bid_size - yes_ask_size) / float(total_size)) * 100, 1) if total_size > 0 else 0.0

        if yes_prob >= 55.0:
            market_bias = "BULLISH"
        elif yes_prob <= 45.0:
            market_bias = "BEARISH"
        else:
            market_bias = "NEUTRAL"

        result = {
            "target_price": target_price,
            "strike_price": target_price,
            "yes_prob": yes_prob,
            "no_prob": no_prob,
            "yes_bid": round(yes_bid, 2),
            "yes_ask": round(yes_ask, 2),
            "no_bid": round(no_bid, 2),
            "no_ask": round(no_ask, 2),
            "spread": spread,
            "yes_bid_size": yes_bid_size,
            "yes_ask_size": yes_ask_size,
            "orderbook_imbalance": orderbook_imbalance,
            "market_bias": market_bias,
            "ticker": active_m.get("ticker", ""),
            "close_time": active_m.get("close_time", ""),
            "close_epoch_ms": int(active_ct.timestamp() * 1000) if active_ct else None,
            "server_now_ms": int(get_kalshi_epoch() * 1000),
            "status": active_m.get("status", "active"),
            "volume_24h": float(active_m.get("volume_24h_fp") or active_m.get("volume_24h") or 0.0),
            "open_interest": float(active_m.get("open_interest_fp") or active_m.get("open_interest") or 0.0),
            "source": f"Kalshi {series_ticker}"
        }
        with _kalshi_cache_lock:
            _kalshi_cache[series_ticker] = result
            _kalshi_cache_times[series_ticker] = time.time()
        return result
    except Exception as e:
        logger.error(f"[Kalshi Client] Error fetching {series_ticker}: {e}")

    with _kalshi_cache_lock:
        return _kalshi_cache.get(series_ticker) or {}


def get_kalshi_market_by_ticker(ticker: str):
    """Fetch a specific Kalshi market by its exact ticker."""
    now = time.time()
    with _kalshi_cache_lock:
        if ticker in _kalshi_cache and (now - _kalshi_cache_times.get(ticker, 0)) < CACHE_TTL_SEC:
            return _kalshi_cache.get(ticker)
        _kalshi_cache_times[ticker] = now

    try:
        resp = _safe_get(
            KALSHI_API_URL + f"/{ticker}",
            headers={"Accept": "application/json", "User-Agent": "ApexProps-Kalshi-Client/1.0"},
            timeout=4.0
        )
        if resp.status_code == 200:
            market = resp.json()
            if "market" in market:
                market = market["market"]
            
            y_bid = float(market.get("yes_bid_dollars") or market.get("yes_bid") or 0.0)
            if y_bid > 1.0: y_bid /= 100.0
            n_bid = float(market.get("no_bid_dollars") or market.get("no_bid") or 0.0)
            if n_bid > 1.0: n_bid /= 100.0
            
            y_ask = float(market.get("yes_ask_dollars") or market.get("yes_ask") or 0.0)
            if y_ask > 1.0: y_ask /= 100.0
            n_ask = float(market.get("no_ask_dollars") or market.get("no_ask") or 0.0)
            if n_ask > 1.0: n_ask /= 100.0

            result = {
                "ticker": market.get("ticker", ""),
                "status": market.get("status", "active"),
                "yes_bid": y_bid,
                "no_bid": n_bid,
                "yes_ask": y_ask,
                "no_ask": n_ask,
                "close_time": market.get("close_time", "")
            }
            with _kalshi_cache_lock:
                _kalshi_cache[ticker] = result
                _kalshi_cache_times[ticker] = time.time()
            return result
    except Exception as e:
        logger.debug(f"[Kalshi Client] Error fetching market {ticker}: {e}")

    with _kalshi_cache_lock:
        return _kalshi_cache.get(ticker) or None



# ── Live trade feed (public, no login) ─────────────────────────────────────
_trades_cache = {}
_trades_lock = threading.Lock()
TRADES_CACHE_TTL_SEC = 1.5   # every dashboard polls this; one Kalshi call per 1.5 s per market


def get_recent_trades(ticker: str, limit: int = 50) -> list:
    """Most recent public trades on one Kalshi market, newest first, as
    [{"id", "side": "yes"|"no", "count", "price", "dollars", "ts"}].
    `dollars` is what the buyer paid (contracts x their side's price)."""
    if not ticker:
        return []
    now = time.time()
    with _trades_lock:
        hit = _trades_cache.get(ticker)
        if hit and now - hit[0] < TRADES_CACHE_TTL_SEC:
            return hit[1]
    trades = []
    try:
        resp = _safe_get(
            KALSHI_API_URL + "/trades",
            params={"ticker": ticker, "limit": max(1, min(int(limit), 200))},
            timeout=4,
        )
        if resp.status_code == 200:
            for t in resp.json().get("trades", []) or []:
                side = str(t.get("taker_outcome_side") or t.get("taker_side") or "").lower()
                if side not in ("yes", "no"):
                    continue
                try:
                    count = float(t.get("count_fp") or t.get("count") or 0)
                    price = float(t.get(f"{side}_price_dollars") or 0) or float(t.get(f"{side}_price") or 0) / 100.0
                except (TypeError, ValueError):
                    continue
                if count <= 0 or price <= 0:
                    continue
                created = str(t.get("created_time") or "")
                try:
                    from datetime import datetime
                    ts = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
                except ValueError:
                    ts = now
                trades.append({
                    "id": str(t.get("trade_id") or f"{created}-{count}-{price}"),
                    "side": side,
                    "count": round(count, 2),
                    "price": round(price, 4),
                    "dollars": round(count * price, 2),
                    "ts": ts,
                })
        else:
            logger.debug(f"[KalshiTrades] HTTP {resp.status_code} for {ticker}")
    except (requests.exceptions.RequestException, ValueError) as e:
        logger.debug(f"[KalshiTrades] fetch failed for {ticker}: {e}")
        with _trades_lock:
            hit = _trades_cache.get(ticker)
        return hit[1] if hit else []
    with _trades_lock:
        _trades_cache[ticker] = (now, trades)
        if len(_trades_cache) > 20:   # keep only recent markets
            for k in sorted(_trades_cache, key=lambda k: _trades_cache[k][0])[:-10]:
                _trades_cache.pop(k, None)
    return trades


