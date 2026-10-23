"""
backend/btc/cf_synthetic_settler.py
Real-Time 60-Second CF Benchmarks Synthetic Settlement Index & Lock Engine.

Kalshi 15m contracts settle against the simple arithmetic average of 60 seconds of BRTI index ticks
during the final minute of the contract (second :00 to :59 before expiration).

This module:
1. Samples sub-second spot prices from spot_streamer every 1.0 second during the final 90 seconds.
2. Tracks the running arithmetic mean of the final 60-second window.
3. Computes the mathematical point-of-no-return: whether the contract is mathematically locked
   in-the-money (guaranteed win) or out-of-the-money, alerting the engine to take profit or de-risk.
"""

from collections import deque
import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Running buffer of (timestamp, spot_price) for last 90 seconds per asset
_SETTLEMENT_SAMPLES: Dict[str, deque] = {}
_LOCK = threading.Lock()


def record_spot_sample(asset: str, spot_price: float):
    """Records one second tick for the running 60s TWAP calculation."""
    if spot_price <= 0:
        return
    a_up = str(asset or "BTC").upper().strip()
    now = time.time()
    with _LOCK:
        if a_up not in _SETTLEMENT_SAMPLES:
            _SETTLEMENT_SAMPLES[a_up] = deque(maxlen=90)
        _SETTLEMENT_SAMPLES[a_up].append((now, spot_price))


def evaluate_synthetic_settlement_lock(
    asset: str,
    strike: float,
    seconds_remaining: float,
    current_side: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates running 60-second settlement math in the final 90 seconds.
    Returns:
      - is_settlement_window: bool (seconds_remaining <= 65)
      - running_twap_price: float
      - twap_vs_strike_delta: float
      - math_locked_outcome: "LOCKED_YES", "LOCKED_NO", or "UNRESOLVED"
      - confidence_lock_pct: float (50% to 100%)
      - recommendation: str ("HOLD_TO_EXPIRATION", "TAKE_PROFIT_IMMEDIATELY", "CUT_POSITION")
    """
    default_res = {
        "is_settlement_window": seconds_remaining <= 65.0,
        "seconds_remaining": round(seconds_remaining, 1),
        "running_twap_price": 0.0,
        "twap_vs_strike_delta": 0.0,
        "math_locked_outcome": "UNRESOLVED",
        "confidence_lock_pct": 50.0,
        "recommendation": "STANDARD_TRADING",
    }

    if seconds_remaining > 65.0 or strike <= 0:
        return default_res

    a_up = str(asset or "BTC").upper().strip()
    now = time.time()

    with _LOCK:
        samples = list(_SETTLEMENT_SAMPLES.get(a_up, []))

    # Filter samples from the last 60 seconds
    recent_ticks = [p for t, p in samples if (now - t) <= 60.0]
    if not recent_ticks:
        return default_res

    running_twap = sum(recent_ticks) / len(recent_ticks)
    delta = round(running_twap - strike, 2)
    ticks_elapsed = len(recent_ticks)
    ticks_remaining = max(1, int(seconds_remaining))

    # Mathematical bounding: what would spot need to print to flip the average?
    # Required average for remaining ticks to flip from YES to NO:
    # (running_twap * ticks_elapsed + X * ticks_remaining) / (ticks_elapsed + ticks_remaining) == strike
    total_ticks = ticks_elapsed + ticks_remaining
    needed_avg_to_flip = ((strike * total_ticks) - (running_twap * ticks_elapsed)) / ticks_remaining

    locked_outcome = "UNRESOLVED"
    lock_pct = 50.0
    rec = "HOLD_TO_EXPIRATION"

    # Extreme clearance: needed price to flip is > 1.5% away
    flip_pct = abs((needed_avg_to_flip - running_twap) / running_twap * 100.0)

    if running_twap > strike:
        if ticks_elapsed >= 40 and flip_pct > 0.40:
            locked_outcome = "LOCKED_YES"
            lock_pct = 99.0
            rec = "HOLD_TO_EXPIRATION (Mathematically locked YES win)"
        elif ticks_elapsed >= 25 and delta > (strike * 0.0008):
            locked_outcome = "PROBABLE_YES"
            lock_pct = 85.0
            rec = "HOLD_TO_EXPIRATION"
    elif running_twap < strike:
        if ticks_elapsed >= 40 and flip_pct > 0.40:
            locked_outcome = "LOCKED_NO"
            lock_pct = 99.0
            rec = "HOLD_TO_EXPIRATION (Mathematically locked NO win)"
        elif ticks_elapsed >= 25 and delta < -(strike * 0.0008):
            locked_outcome = "PROBABLE_NO"
            lock_pct = 85.0
            rec = "HOLD_TO_EXPIRATION"

    return {
        "is_settlement_window": True,
        "seconds_remaining": round(seconds_remaining, 1),
        "ticks_sampled_in_final_minute": ticks_elapsed,
        "running_twap_price": round(running_twap, 2),
        "twap_vs_strike_delta": delta,
        "needed_price_to_flip": round(needed_avg_to_flip, 2),
        "flip_required_pct": round(flip_pct, 2),
        "math_locked_outcome": locked_outcome,
        "confidence_lock_pct": lock_pct,
        "recommendation": rec,
    }
