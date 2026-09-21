import requests
import logging

logger = logging.getLogger(__name__)

def fetch_coinbase_orderbook_imbalance(asset: str = "BTC") -> float:
    """
    Fetches the Level 2 Orderbook from Coinbase for the given asset (e.g., 'BTC').
    Returns an imbalance score between -1.0 and 1.0.
    Positive -> More buy pressure (Bids > Asks)
    Negative -> More sell pressure (Asks > Bids)
    """
    if asset.upper() != "BTC":
        return 0.0 # Only implementing BTC for now

    url = "https://api.exchange.coinbase.com/products/BTC-USD/book?level=2"
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
        logger.warning(f"[Orderbook] Failed to fetch Coinbase L2 orderbook: {e}")
        return 0.0
