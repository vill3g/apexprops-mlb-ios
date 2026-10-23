import logging

import requests

logger = logging.getLogger(__name__)

def fetch_coinbase_orderbook_imbalance(asset: str = "BTC") -> float:
    """
    Fetches the Level 2 Orderbook from Coinbase for the given asset (e.g., 'BTC', 'ETH', 'SOL', 'DOGE').
    Returns an imbalance score between -1.0 and 1.0.
    Positive -> More buy pressure (Bids > Asks)
    Negative -> More sell pressure (Asks > Bids)
    """
    a_up = str(asset or "BTC").upper().strip()
    if a_up not in ("BTC", "ETH", "SOL", "DOGE"):
        return 0.0

    url = f"https://api.exchange.coinbase.com/products/{a_up}-USD/book?level=2"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        bids = data.get("bids", [])
        asks = data.get("asks", [])

        # Sum total volume from top 50 bids/asks
        total_bid_vol = sum(float(bid[1]) for bid in bids[:50])
        total_ask_vol = sum(float(ask[1]) for ask in asks[:50])

        total_vol = total_bid_vol + total_ask_vol
        if total_vol == 0:
            return 0.0

        # Calculate imbalance: (bids - asks) / total
        imbalance = (total_bid_vol - total_ask_vol) / total_vol
        return imbalance

    except Exception as e:
        logger.warning(f"[Orderbook] Failed to fetch Coinbase L2 orderbook for {a_up}: {e}")
        return 0.0
