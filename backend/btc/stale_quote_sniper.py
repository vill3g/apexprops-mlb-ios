"""
backend/btc/stale_quote_sniper.py
Institutional Stale Quote Arbitrage & Sniping Engine.

Exploits latency disparity between real-time CF Benchmarks constituent spot prices (Kraken/Coinbase)
and resting Kalshi contract orderbook quotes.

Trigger Rule:
  If the spot price moves >= 0.15% away from the Kalshi strike in the first 120 seconds of a 15m candle,
  but the Kalshi contract orderbook is still offering contracts between 46c and 54c (stale 50/50 odds),
  generate an authoritative high-conviction SNIPE signal for immediate IOC sweep.
"""

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Minimum spot dislocation percentage required to declare a stale quote arbitrage opportunity
MIN_DISLOCATION_PCT = 0.14  # 0.14% - 0.15% (e.g. ~$120 on BTC, ~$3.50 on ETH)
# Window in which Kalshi orderbooks are most sluggish
MAX_SNIPE_WINDOW_SEC = 150.0  # first 2.5 minutes


def evaluate_stale_quote_snipe(
    asset: str,
    ticker: str,
    strike: float,
    current_spot: float,
    sec_elapsed: float,
    yes_ask: float,
    yes_bid: float,
    no_ask: float,
    no_bid: float,
) -> Dict[str, Any]:
    """
    Evaluates whether Kalshi's orderbook is offering stale quotes that lag the real spot move.
    Returns:
      - is_snipe_opportunity: bool
      - recommended_side: "YES" or "NO"
      - spot_dislocation_pct: float
      - edge_bps: float
      - snipe_conviction: int (80 to 95)
      - reasoning: str
    """
    default_res = {
        "is_snipe_opportunity": False,
        "recommended_side": None,
        "spot_dislocation_pct": 0.0,
        "edge_cents": 0.0,
        "snipe_conviction": 0,
        "reasoning": "No stale quote disparity detected.",
    }

    if strike <= 0 or current_spot <= 0 or sec_elapsed > MAX_SNIPE_WINDOW_SEC:
        return default_res

    a_up = str(asset or "BTC").upper().strip()

    # Asset-specific dislocation sensitivity threshold:
    # Forex volatility is much lower than Crypto, so 0.035% (~3.5 pips) is a significant move.
    # High-beta crypto like DOGE/SOL requires 0.18%, while BTC/ETH use 0.12%.
    if a_up in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD"):
        min_dislocation = 0.035
    elif a_up == "DOGE":
        min_dislocation = 0.22
    elif a_up == "SOL":
        min_dislocation = 0.16
    else:
        min_dislocation = MIN_DISLOCATION_PCT

    # Calculate percentage spot dislocation from the official strike
    dislocation_pct = round(((current_spot - strike) / strike) * 100.0, 3)
    abs_dislocation = abs(dislocation_pct)

    # Convert prices to dollars if needed
    if yes_ask > 1.0: yes_ask /= 100.0
    if yes_bid > 1.0: yes_bid /= 100.0
    if no_ask > 1.0: no_ask /= 100.0
    if no_bid > 1.0: no_bid /= 100.0

    # CASE 1: Spot surged ABOVE strike (>= threshold), but Kalshi YES ask is still cheap (<= 55c)
    # Fair value for an ITM contract with cushion is 68c - 80c.
    if dislocation_pct >= min_dislocation and 0.45 <= yes_ask <= 0.55:
        edge_cents = round(0.72 - yes_ask, 2)  # Fair value vs current ask
        conviction = min(92, int(75 + (abs_dislocation / min_dislocation) * 8))
        return {
            "is_snipe_opportunity": True,
            "recommended_side": "YES",
            "spot_dislocation_pct": dislocation_pct,
            "spot_distance_dollars": round(current_spot - strike, 4),
            "current_contract_ask": yes_ask,
            "estimated_fair_value": 0.72,
            "edge_cents": edge_cents,
            "snipe_conviction": conviction,
            "reasoning": (
                f"⚡ STALE QUOTE ARB (YES): Spot moved +{dislocation_pct:.2f}% (${current_spot - strike:+.4f}) "
                f"above strike, but Kalshi YES ask is lagging at {yes_ask*100:.0f}¢ (Fair: ~72¢). Snipe underpriced contracts."
            ),
        }

    # CASE 2: Spot dumped BELOW strike (<= -threshold), but Kalshi NO ask is still cheap (<= 55c)
    # Fair value for an ITM contract with cushion is 68c - 80c.
    if dislocation_pct <= -min_dislocation and 0.45 <= no_ask <= 0.55:
        edge_cents = round(0.72 - no_ask, 2)
        conviction = min(92, int(75 + (abs_dislocation / min_dislocation) * 8))
        return {
            "is_snipe_opportunity": True,
            "recommended_side": "NO",
            "spot_dislocation_pct": dislocation_pct,
            "spot_distance_dollars": round(current_spot - strike, 4),
            "current_contract_ask": no_ask,
            "estimated_fair_value": 0.72,
            "edge_cents": edge_cents,
            "snipe_conviction": conviction,
            "reasoning": (
                f"⚡ STALE QUOTE ARB (NO): Spot dropped {dislocation_pct:.2f}% (${current_spot - strike:+.4f}) "
                f"below strike, but Kalshi NO ask is lagging at {no_ask*100:.0f}¢ (Fair: ~72¢). Snipe underpriced contracts."
            ),
        }

    return default_res
