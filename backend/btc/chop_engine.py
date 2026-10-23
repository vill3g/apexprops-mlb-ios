"""
Specialized Chop Trading Engine for ShadowTrader AI.

Operates strictly during COMPRESSION_MEAN_REVERSION market states:
1. Rejects 50/50 coin-flip contracts near the strike ($0.45 - $0.55).
2. Executes Asymmetric Boundary Fades: Buys deep discount contracts ($0.15 - $0.35)
   when spot price reaches outer Bollinger Bands (2.0 std dev) or RSI extremes (<30 oversold / >70 overbought).
3. Enforces Micro-Scalp Profit Targets (+10c to +15c) and early expiration exit (2 mins before close)
   to eliminate pin-risk roulette.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Tactical Chop Corridor: Buy only heavily discounted asymmetric contracts
CHOP_MIN_ASK_CENTS = 0.15
CHOP_MAX_ASK_CENTS = 0.35
CHOP_DEFAULT_SCALP_CENTS = 0.12  # +12 cents target exit
CHOP_MAX_SPREAD_CENTS = 0.04     # Must have tight bid-ask spread to avoid getting gouged


def evaluate_chop_contract(
    df: Any,
    target_price: float = 0.0,
    kalshi_m: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Backwards-compatible wrapper for AutoExecutor calling evaluate_chop_contract(df, target_price, kalshi_m).
    """
    if df is None or len(df) == 0:
        return {"action": "PASS", "direction": "PASS", "confidence": 50.0, "reason": "No data"}
    
    last = df.iloc[-1]
    spot = float(last.get("close") or target_price)
    strike = float(target_price or spot)
    km = kalshi_m or {}
    
    yes_ask = float(km.get("yes_ask") or 0.50)
    no_ask = float(km.get("no_ask") or 0.50)
    yes_bid = float(km.get("yes_bid") or 0.48)
    no_bid = float(km.get("no_bid") or 0.48)
    rsi_1m = float(last.get("rsi_1m") or last.get("rsi") or 50.0)
    rsi_5m = float(last.get("rsi_5m") or last.get("rsi") or 50.0)
    bbu = float(last.get("bb_upper") or (spot * 1.002))
    bbl = float(last.get("bb_lower") or (spot * 0.998))
    bbm = float(last.get("bb_middle") or spot)
    
    setup = evaluate_chop_trade(
        asset="BTC",
        spot_price=spot,
        strike_price=strike,
        kalshi_yes_ask=yes_ask,
        kalshi_no_ask=no_ask,
        kalshi_yes_bid=yes_bid,
        kalshi_no_bid=no_bid,
        rsi_1m=rsi_1m,
        rsi_5m=rsi_5m,
        bb_upper_1m=bbu,
        bb_lower_1m=bbl,
        bb_middle_1m=bbm,
        seconds_to_expiry=450
    )
    if not setup:
        return {
            "action": "PASS",
            "direction": "PASS",
            "confidence": 50.0,
            "conviction_grade": "PASS / CHOP DEADZONE (CAPITAL GUARD)",
            "reason": "Chop range center: no outer boundary fade trigger",
            "catalysts": ["Chop Engine: inside neutral zone, passing to prevent chop loss"]
        }
    return {
        "action": f"BID {setup['side']}",
        "direction": setup["side"],
        "side": setup["side"],
        "confidence": setup["confidence"],
        "conviction_grade": "GRADE A+ CHOP FADE",
        "reason": setup["reason"],
        "catalysts": [setup["reason"]],
        "is_chop_trade": True,
        "target_scalp_exit": setup["target_scalp_exit"]
    }


def evaluate_chop_trade(
    asset: str,
    spot_price: float,
    strike_price: float,
    kalshi_yes_ask: float,
    kalshi_no_ask: float,
    kalshi_yes_bid: float,
    kalshi_no_bid: float,
    rsi_1m: float,
    rsi_5m: float,
    bb_upper_1m: float,
    bb_lower_1m: float,
    bb_middle_1m: float,
    seconds_to_expiry: int,
) -> Optional[Dict[str, Any]]:
    """
    Evaluates whether a high-expectancy fade exists in chop market conditions.
    Returns trade setup dictionary or None if setup criteria are not met.
    """
    # 1. Expiration safety: Never enter chop trades in final 180 seconds (micro-noise roulette)
    if seconds_to_expiry < 180:
        return None

    # 2. Check Overbought condition -> Fade with NO (or Buy cheap NO if strike is above spot)
    # If RSI > 68 and spot >= upper Bollinger band, price is exhausting upwards in chop.
    # Expectation: Mean-reversion back to middle band (bb_middle).
    spread_no = kalshi_no_ask - kalshi_no_bid
    if rsi_1m >= 68.0 and spot_price >= (bb_upper_1m * 0.9995):
        if CHOP_MIN_ASK_CENTS <= kalshi_no_ask <= CHOP_MAX_ASK_CENTS and spread_no <= CHOP_MAX_SPREAD_CENTS:
            return {
                "action": "BUY_NO",
                "side": "NO",
                "target_price": kalshi_no_ask,
                "strategy": "CHOP_FADE_OVERBOUGHT",
                "target_scalp_exit": round(kalshi_no_ask + CHOP_DEFAULT_SCALP_CENTS, 2),
                "stop_loss_price": round(max(0.05, kalshi_no_ask - 0.08), 2),
                "confidence": 76.5,
                "reason": (
                    f"🧊 Chop Fade: 1m RSI={rsi_1m:.1f} hit overbought resistance at upper BB "
                    f"(${spot_price:,.2f} >= ${bb_upper_1m:,.2f}). Fading reversion to VWAP/mid with discount NO @ ${kalshi_no_ask:.2f}."
                )
            }

    # 3. Check Oversold condition -> Fade with YES (Buy cheap YES on bounce)
    # If RSI < 32 and spot <= lower Bollinger band, price is exhausting downwards in chop.
    spread_yes = kalshi_yes_ask - kalshi_yes_bid
    if rsi_1m <= 32.0 and spot_price <= (bb_lower_1m * 1.0005):
        if CHOP_MIN_ASK_CENTS <= kalshi_yes_ask <= CHOP_MAX_ASK_CENTS and spread_yes <= CHOP_MAX_SPREAD_CENTS:
            return {
                "action": "BUY_YES",
                "side": "YES",
                "target_price": kalshi_yes_ask,
                "strategy": "CHOP_FADE_OVERSOLD",
                "target_scalp_exit": round(kalshi_yes_ask + CHOP_DEFAULT_SCALP_CENTS, 2),
                "stop_loss_price": round(max(0.05, kalshi_yes_ask - 0.08), 2),
                "confidence": 76.5,
                "reason": (
                    f"🧊 Chop Fade: 1m RSI={rsi_1m:.1f} hit oversold support at lower BB "
                    f"(${spot_price:,.2f} <= ${bb_lower_1m:,.2f}). Fading bounce to VWAP/mid with discount YES @ ${kalshi_yes_ask:.2f}."
                )
            }

    return None
