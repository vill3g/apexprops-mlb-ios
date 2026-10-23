"""
Maker Engine for Kalshi 15M Binary Markets.
Provides passive limit order pricing inside the bid-ask spread to eliminate
taker fees and capture the bid-ask spread, with automatic fallback to taker
execution when speed/momentum demands immediate fill.
"""

import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def get_execution_urgency(
    forecast: Optional[Dict[str, Any]] = None,
    sec_left: float = 900.0,
    regime: str = "SNIPER"
) -> str:
    """
    Determines execution urgency: "MAKER" (passive limit inside spread) or
    "TAKER" (immediate cross to guarantee entry).

    TAKER is chosen only when:
    1. sec_left < 120 (less than 2 minutes left in 15M contract).
    2. High-velocity momentum surge (MOMENTUM_SURFER / STRONG_MOMENTUM).
    3. Extreme conviction (win prob >= 82% or unanimous 3-model agreement).

    In all other cases, MAKER is chosen to save up to $0.0175/contract in fees
    and capture 2-6 cents of bid-ask spread.
    """
    if sec_left < 120.0:
        return "TAKER"

    regime_upper = str(regime or "").upper()
    if regime_upper in ("STRONG_MOMENTUM", "MOMENTUM_SURFER"):
        return "TAKER"

    if forecast and isinstance(forecast, dict):
        prob = float(forecast.get("probability_percent") or forecast.get("prob") or 50.0)
        if prob >= 82.0:
            return "TAKER"
        if bool(forecast.get("is_unanimous")) and float(forecast.get("agreement_ratio") or 1.0) >= 0.95:
            return "TAKER"

    return "MAKER"


def compute_maker_limit_price(
    active_m: Dict[str, Any],
    side: str,
    urgency: str = "MAKER",
    target_limit_price: Optional[float] = None
) -> Tuple[float, bool]:
    """
    Calculates the optimal order price and whether to post as MAKER (post-only)
    or TAKER (immediate IOC cross).

    Args:
        active_m: The Kalshi active 15M market dictionary (containing yes_bid, yes_ask, etc.)
        side: "yes" or "no"
        urgency: "MAKER" or "TAKER"
        target_limit_price: Optional limit price suggested by RL / ML agent

    Returns:
        (price: float, is_maker: bool)
        - price is clamped in [0.01, 0.99] rounded to 2 decimals.
        - is_maker is True if posting a passive limit order inside the book.
    """
    side_clean = str(side or "yes").lower().strip()

    # Extract bids and asks from market
    raw_yes_bid = active_m.get("yes_bid")
    raw_yes_ask = active_m.get("yes_ask")

    yes_bid = float(raw_yes_bid) if raw_yes_bid is not None else 0.0
    yes_ask = float(raw_yes_ask) if raw_yes_ask is not None else 0.0

    # Derive complementary NO quotes if direct no quotes are missing
    raw_no_bid = active_m.get("no_bid")
    raw_no_ask = active_m.get("no_ask")

    if raw_no_bid is not None:
        no_bid = float(raw_no_bid)
    else:
        no_bid = round(max(0.0, 1.0 - yes_ask), 2) if yes_ask > 0 else 0.0

    if raw_no_ask is not None:
        no_ask = float(raw_no_ask)
    else:
        no_ask = round(max(0.0, 1.0 - yes_bid), 2) if yes_bid > 0 else 0.0

    if side_clean == "yes":
        cur_bid = yes_bid
        cur_ask = yes_ask
    else:
        cur_bid = no_bid
        cur_ask = no_ask

    # Fallback if quotes are missing or malformed
    if cur_ask <= 0.0:
        base_px = round(float(target_limit_price or 0.50), 2)
        return min(0.99, max(0.01, base_px)), False

    # TAKER execution: Pay current ask (crossing the book)
    if urgency == "TAKER":
        taker_px = round(cur_ask, 2)
        return min(0.99, max(0.01, taker_px)), False

    # MAKER execution: Place passive limit order inside spread
    # Valid book check
    if cur_bid <= 0.0 or cur_bid >= cur_ask:
        # If no active bid or inverted book, bid 2 cents below ask
        maker_px = round(max(0.01, cur_ask - 0.02), 2)
        return min(0.99, max(0.01, maker_px)), True

    spread = round(cur_ask - cur_bid, 2)

    if spread >= 0.02:
        # Outbid the best bid by 1 cent (capturing priority inside spread or midpoint)
        maker_px = round(cur_bid + 0.01, 2)
    else:
        # 1-cent spread (tightest possible book, e.g. 0.49 bid / 0.50 ask):
        # Join top of bid queue as maker
        maker_px = round(cur_bid, 2)

    # If the model suggested a target limit price lower than our maker price, respect it
    if target_limit_price is not None:
        try:
            cand = float(target_limit_price)
            if 0.01 <= cand < cur_ask:
                maker_px = min(maker_px, round(cand, 2))
        except (ValueError, TypeError):
            pass

    maker_px = min(0.99, max(0.01, round(maker_px, 2)))
    return maker_px, True
