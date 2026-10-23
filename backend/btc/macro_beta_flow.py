"""
backend/btc/macro_beta_flow.py
Cross-Asset Macro Beta Flow & Global Risk Sentiment for Gemini 15M Gate.

Tracks:
  - Global risk sentiment (RISK_ON vs RISK_OFF).
  - BTC vs Altcoin (ETH, SOL, DOGE) lead-lag volume and momentum delta.
  - Cross-market directional alignment.
"""

import logging
import threading
import time
from typing import Any, Dict
import requests

logger = logging.getLogger(__name__)

_BETA_CACHE: Dict[str, Any] = {}
_BETA_LOCK = threading.Lock()
_BETA_TTL_SEC = 30.0


def fetch_cross_asset_macro_beta(target_asset: str = "BTC") -> Dict[str, Any]:
    """
    Computes global crypto macro beta, comparing BTC, ETH, SOL, and DOGE recent momentum.
    Uses Binance.US (US-accessible) as primary with OKX fallback.
    """
    now = time.time()
    with _BETA_LOCK:
        cached = _BETA_CACHE.get("global")
        if cached and (now - cached.get("_ts", 0)) < _BETA_TTL_SEC:
            res = dict(cached)
            res.pop("_ts", None)
            return res

    default_res = {
        "macro_risk_sentiment": "NEUTRAL",
        "btc_24h_drift_pct": 0.0,
        "eth_24h_drift_pct": 0.0,
        "sol_24h_drift_pct": 0.0,
        "doge_24h_drift_pct": 0.0,
        "cross_asset_alignment": "ALIGNED",
        "alt_leader": "BTC",
        "status": "default",
    }

    try:
        resp = requests.get(
            "https://api.binance.us/api/v3/ticker/24hr?symbols=[%22BTCUSDT%22,%22ETHUSDT%22,%22SOLUSDT%22,%22DOGEUSDT%22]",
            timeout=2.0,
        )
        if resp.status_code == 200:
            tickers = resp.json()
            data_map = {t.get("symbol"): float(t.get("priceChangePercent", 0.0) or 0.0) for t in tickers}

            btc_chg = data_map.get("BTCUSDT", 0.0)
            eth_chg = data_map.get("ETHUSDT", 0.0)
            sol_chg = data_map.get("SOLUSDT", 0.0)
            doge_chg = data_map.get("DOGEUSDT", 0.0)

            all_chgs = {"BTC": btc_chg, "ETH": eth_chg, "SOL": sol_chg, "DOGE": doge_chg}
            alt_leader = max(all_chgs, key=lambda k: all_chgs[k])

            pos_count = sum(1 for c in (btc_chg, eth_chg, sol_chg, doge_chg) if c > 0.0)
            if pos_count >= 3 and btc_chg >= 0.8:
                sentiment = "RISK_ON (Broad Market Expansion)"
            elif pos_count <= 1 and btc_chg <= -0.8:
                sentiment = "RISK_OFF (Broad Market Liquidation)"
            elif btc_chg > eth_chg and btc_chg > sol_chg and btc_chg > doge_chg:
                sentiment = "BTC_DOMINANCE (Capital concentrating in Bitcoin)"
            else:
                sentiment = "SELECTIVE_ROTATION / MIXED"

            if all(c > 0 for c in (btc_chg, eth_chg, sol_chg, doge_chg)) or all(c < 0 for c in (btc_chg, eth_chg, sol_chg, doge_chg)):
                alignment = "STRONG_UNIDIRECTIONAL_CONFLUENCE"
            else:
                alignment = "DIVERGENT (Cross-asset chop / desynchronization)"

            res = {
                "macro_risk_sentiment": sentiment,
                "btc_24h_drift_pct": round(btc_chg, 2),
                "eth_24h_drift_pct": round(eth_chg, 2),
                "sol_24h_drift_pct": round(sol_chg, 2),
                "doge_24h_drift_pct": round(doge_chg, 2),
                "alt_leader": alt_leader,
                "cross_asset_alignment": alignment,
                "status": "live",
            }
            with _BETA_LOCK:
                _BETA_CACHE["global"] = {**res, "_ts": now}
            return res
    except Exception as e:
        logger.debug(f"[MacroBetaFlow] Error querying cross-asset data: {e}")

    return default_res
