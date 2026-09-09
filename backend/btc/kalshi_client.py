"""
Kalshi Crypto Event Contracts Client
Pulls live 15-minute Bitcoin price targets and market-implied odds from Kalshi's CFTC-regulated KXBTC15M series.
"""
import time
import requests

KALSHI_API_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"

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
        resp = requests.get(
            KALSHI_API_URL,
            params={"series_ticker": "KXBTC15M", "status": "open"},
            headers={"Accept": "application/json", "User-Agent": "ApexProps-Kalshi-Client/1.0"},
            timeout=4.0
        )
        if resp.status_code == 200:
            data = resp.json()
            markets = data.get("markets", [])
            if markets:
                # Find the earliest expiring open market (active 15m interval)
                active_m = sorted(markets, key=lambda m: m.get("close_time", ""))[0]
                floor_strike = active_m.get("floor_strike")
                if floor_strike is not None:
                    target_price = float(floor_strike)
                    
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
