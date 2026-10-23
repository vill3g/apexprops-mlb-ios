"""
3-Phase 15-Minute Time-Decay Engine for Kalshi Binary Markets.

Optimizes trade selection, regime routing, and risk management across
the three distinct microstructural phases of every 15-minute candle:

1. Phase 1: OPENING_BREAKOUT (15m to 10m remaining, sec_left >= 600)
   - Dominant driver: Initial range expansion and directional momentum.
   - Recommended regimes: MOMENTUM_SURFER, SNIPER.
   - Discipline: Avoid premature counter-trend mean-reversion fading.

2. Phase 2: MID_CONSOLIDATION (10m to 4m remaining, 240 <= sec_left < 600)
   - Dominant driver: VWAP pullbacks, Bollinger Band %b mean-reversion, order book stabilization.
   - Recommended regimes: AMBUSH, SNIPER with passive maker limit bidding inside the spread.
   - Discipline: Prime maker window for fee elimination and spread harvesting.

3. Phase 3: EXPIRY_PIN (4m to 0.5m remaining, 30 <= sec_left < 240)
   - Dominant driver: Extreme non-linear time decay (Theta -> infinity).
   - Delta-to-Strike Lock-in vs Pin Risk:
     * Delta Locked (|spot - strike| >= delta_buffer): Spot has moved safely away from strike;
       probability of winning outcome is mathematically > 85-95%. High-conviction entry.
     * Pin Risk (|spot - strike| < delta_buffer): Spot is hovering right at the strike price.
       A $5 tick flips the binary payoff between $1 and $0. Entry is strictly vetoed to preserve capital.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Minimum spot buffer from strike in Phase 3 to qualify as "Delta Locked" rather than "Pin Risk"
DEFAULT_DELTA_BUFFERS = {
    "BTC": 30.0,    # $30 spot cushion for BTC
    "ETH": 2.50,    # $2.50 spot cushion for ETH
    "SOL": 0.35,    # $0.35 spot cushion for SOL
    "DOGE": 0.0015, # $0.0015 spot cushion for DOGE
    "GOLD": 1.50,   # $1.50 spot cushion for Gold
    "DEFAULT": 20.0
}


def classify_15m_time_phase(
    sec_left: float,
    spot_price: float = 0.0,
    strike_price: float = 0.0,
    atr: float = 100.0,
    asset: str = "BTC"
) -> Dict[str, Any]:
    """
    Evaluates the current 15-minute candle phase and delta-to-strike dynamics.

    Returns:
        Dict containing:
        - phase: "OPENING_BREAKOUT", "MID_CONSOLIDATION", or "EXPIRY_PIN"
        - phase_num: 1, 2, or 3
        - sec_left: float
        - delta_to_strike: float (|spot - strike|)
        - is_delta_locked: bool (True if deep enough in-the-money during Phase 3)
        - is_pin_risk: bool (True if dangerously close to strike in Phase 3)
        - recommended_focus: str
        - desc: str
    """
    sec = max(0.0, float(sec_left))
    delta = abs(float(spot_price) - float(strike_price)) if (spot_price > 0 and strike_price > 0) else 0.0

    buffer_threshold = DEFAULT_DELTA_BUFFERS.get(str(asset or "BTC").upper(), DEFAULT_DELTA_BUFFERS["DEFAULT"])
    if atr > 0:
        buffer_threshold = max(buffer_threshold, 0.35 * atr)

    # 1. Phase 1: OPENING_BREAKOUT (15m to 10m left)
    if sec >= 600.0:
        return {
            "phase": "OPENING_BREAKOUT",
            "phase_num": 1,
            "sec_left": round(sec, 1),
            "delta_to_strike": round(delta, 2),
            "is_delta_locked": False,
            "is_pin_risk": False,
            "recommended_focus": "MOMENTUM_BREAKOUT",
            "desc": f"Phase 1 Opening Breakout ({sec/60.0:.1f}m left): Range establishment & trend velocity priority."
        }

    # 2. Phase 2: MID_CONSOLIDATION (10m to 4m left)
    if sec >= 240.0:
        return {
            "phase": "MID_CONSOLIDATION",
            "phase_num": 2,
            "sec_left": round(sec, 1),
            "delta_to_strike": round(delta, 2),
            "is_delta_locked": False,
            "is_pin_risk": False,
            "recommended_focus": "MEAN_REVERSION_MAKER",
            "desc": f"Phase 2 Mid Consolidation ({sec/60.0:.1f}m left): VWAP/Bands absorption with passive maker pricing."
        }

    # 3. Phase 3: EXPIRY_PIN (4m to 0.5m left)
    is_delta_locked = False
    is_pin_risk = False

    if spot_price > 0 and strike_price > 0:
        if delta >= buffer_threshold:
            is_delta_locked = True
            rec_focus = "DELTA_LOCK_IN"
            desc = f"Phase 3 Expiry Lock-In ({sec/60.0:.1f}m left): Spot cushion ${delta:.2f} >= ${buffer_threshold:.2f}. High probability expiration setup."
        else:
            is_pin_risk = True
            rec_focus = "PIN_RISK_VETO"
            desc = f"Phase 3 Strike Pin Risk ({sec/60.0:.1f}m left): Spot ${spot_price:,.2f} is within ${delta:.2f} of strike ${strike_price:,.2f}. Coin-flip risk veto active."
    else:
        rec_focus = "EXPIRY_GENERAL"
        desc = f"Phase 3 Expiry ({sec/60.0:.1f}m left): Rapid theta decay window."

    return {
        "phase": "EXPIRY_PIN",
        "phase_num": 3,
        "sec_left": round(sec, 1),
        "delta_to_strike": round(delta, 2),
        "is_delta_locked": is_delta_locked,
        "is_pin_risk": is_pin_risk,
        "recommended_focus": rec_focus,
        "desc": desc
    }
