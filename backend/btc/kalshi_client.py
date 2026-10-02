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
_adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=Retry(total=2, backoff_factor=0.2))
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)

_kalshi_cache = {}
_kalshi_cache_times = {}
_kalshi_cache_lock = threading.Lock()  # FIX #8: protects module-level cache globals from concurrent writes
CACHE_TTL_SEC = 0.95  # 0.95-second cache to deliver real-time odds without hitting rate limits (prevents 1000ms polling aliasing)


from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
import requests.exceptions

@retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(4), retry=retry_if_exception_type((requests.exceptions.RequestException, ValueError)))
def _safe_get(*args, **kwargs):
    resp = _session.get(*args, **kwargs)
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
    # FIX #8: Check cache under lock so concurrent threads don't all fire HTTP requests on expiry.
    with _kalshi_cache_lock:
        if series_ticker in _kalshi_cache and (now - _kalshi_cache_times.get(series_ticker, 0)) < CACHE_TTL_SEC:
            return _kalshi_cache.get(series_ticker)
        # Optimistic stamp: claim this slot so other threads see it as "fresh" and wait
        _kalshi_cache_times[series_ticker] = now

    try:
        markets = []
        for status_param in ["open", None]:
            params = {"series_ticker": series_ticker}
            if status_param:
                params["status"] = status_param
            try:
                resp = _safe_get(
                    KALSHI_API_URL,
                    params=params,
                    headers={"Accept": "application/json", "User-Agent": "ApexProps-Kalshi-Client/1.0"},
                    timeout=4.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    m_list = data.get("markets", [])
                    if m_list:
                        markets = m_list
                        break
            except Exception as e:
                logger.debug(f"Ignored exception: {e}")

        active_m = None
        if markets:
            import datetime
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            valid_m = []
            for m in markets:
                ct_str = m.get("close_time")
                if ct_str:
                    try:
                        ct = datetime.datetime.fromisoformat(ct_str.replace("Z", "+00:00"))
                        if ct > now_utc - datetime.timedelta(seconds=15) and ct < now_utc + datetime.timedelta(minutes=30):
                            valid_m.append((ct, m))
                    except Exception as e:
                        logger.debug(f"close_time parse error: {e}")

            if valid_m:
                valid_m.sort(key=lambda x: x[0])
                active_m = valid_m[0][1]

        if not active_m:
            if allow_synthetic:
                from backend.engine.multi_asset_fetcher import get_asset_ticker
                cur_p = float(get_asset_ticker(series_ticker.replace("KX", "").replace("15M", "")).get("price", 0.0))
                synth = {
                    "target_price": cur_p,
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
        if floor_strike is not None:
            target_price = float(floor_strike)
        else:
            from backend.btc.data_fetcher import get_live_15m_target_data
            from backend.engine.multi_asset_fetcher import get_asset_ticker
            asset = series_ticker.replace("KX", "").replace("15M", "")
            target_data = get_live_15m_target_data(asset)
            target_price = float(target_data.get("target_price") or get_asset_ticker(asset).get("price", 0.0))
        # Extract detailed top-of-book order metrics
        yes_bid = float(active_m.get("yes_bid_dollars") or (float(active_m.get("yes_bid") or 0) / 100.0))
        yes_ask = float(active_m.get("yes_ask_dollars") or (float(active_m.get("yes_ask") or 0) / 100.0))
        no_bid = float(active_m.get("no_bid_dollars") or (float(active_m.get("no_bid") or 0) / 100.0))
        no_ask = float(active_m.get("no_ask_dollars") or (float(active_m.get("no_ask") or 0) / 100.0))
        last_p = float(active_m.get("last_price_dollars") or (float(active_m.get("last_price") or 50) / 100.0))
        yes_bid_size = int(active_m.get("yes_bid_size") or active_m.get("yes_bid_count") or 0)
        yes_ask_size = int(active_m.get("yes_ask_size") or active_m.get("yes_ask_count") or 0)

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
        logger.error(f"[Kalshi Client] Error fetching KXBTC15M: {e}")

    with _kalshi_cache_lock:
        return _kalshi_cache.get(series_ticker) or {}



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


