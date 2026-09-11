"""
Kalshi Crypto Event Contracts Client
Pulls live 15-minute Bitcoin price targets and market-implied odds from Kalshi's CFTC-regulated KXBTC15M series.
"""
import time
import requests

KALSHI_API_URL = "https://external-api.kalshi.com/trade-api/v2/markets"

_kalshi_cache = None
_kalshi_cache_time = 0.0
CACHE_TTL_SEC = 8.0  # 8-second cache to maintain high responsiveness without rate limiting


def get_kalshi_15m_market():
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
    global _kalshi_cache, _kalshi_cache_time
    now = time.time()
    if _kalshi_cache and (now - _kalshi_cache_time) < CACHE_TTL_SEC:
        return _kalshi_cache

    try:
        markets = []
        for status_param in ["open", None]:
            params = {"series_ticker": "KXBTC15M"}
            if status_param:
                params["status"] = status_param
            try:
                resp = requests.get(
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
            except Exception:
                pass

        if markets:
            import datetime
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            valid_m = []
            for m in markets:
                ct_str = m.get("close_time")
                if ct_str:
                    try:
                        ct = datetime.datetime.fromisoformat(ct_str.replace("Z", "+00:00"))
                        if ct > now_utc - datetime.timedelta(minutes=5):
                            valid_m.append((ct, m))
                    except Exception:
                        pass

            if valid_m:
                valid_m.sort(key=lambda x: x[0])
                active_m = valid_m[0][1]
            else:
                return None
            floor_strike = active_m.get("floor_strike")
            if floor_strike is not None:
                target_price = float(floor_strike)
            else:
                from backend.btc.data_fetcher import get_live_15m_target_data, get_btc_ticker
                target_data = get_live_15m_target_data()
                target_price = float(target_data.get("target_price") or get_btc_ticker().get("price", 78000.0))
            # Calculate Yes/No probability
            yes_bid = float(active_m.get("yes_bid_dollars") or 0.0)
            yes_ask = float(active_m.get("yes_ask_dollars") or 0.0)
            last_p = float(active_m.get("last_price_dollars") or 0.5)

            if yes_bid > 0 and yes_ask > 0:
                yes_prob = round(((yes_bid + yes_ask) / 2.0) * 100, 1)
            elif last_p > 0:
                yes_prob = round(last_p * 100, 1)
            else:
                yes_prob = 50.0

            no_prob = round(100.0 - yes_prob, 1)

            result = {
                "target_price": target_price,
                "yes_prob": yes_prob,
                "no_prob": no_prob,
                "ticker": active_m.get("ticker", ""),
                "close_time": active_m.get("close_time", ""),
                "status": active_m.get("status", "active"),
                "volume_24h": float(active_m.get("volume_24h_fp") or 0.0),
                "source": "Kalshi KXBTC15M"
            }
            _kalshi_cache = result
            _kalshi_cache_time = time.time()
            return result
    except Exception as e:
        print(f"[Kalshi Client] Error fetching KXBTC15M: {e}")

    return _kalshi_cache
