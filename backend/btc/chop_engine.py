"""
backend/btc/chop_engine.py
Chop-regime contract evaluator.

Routed to from AutoExecutor when effective_style == "CHOP" (AUTO mode
detects low volatility + tight Bollinger Band width and routes here
instead of the SNIPER/momentum path).

This wraps the existing, tested evaluate_next_15m_contract() confluence
engine rather than duplicating its logic, and applies two chop-specific
adjustments on top:

  1. A wider "distance from 50%" floor before allowing a directional bet.
     Range-bound markets make momentum/breakout signals less reliable,
     so we require more conviction than usual before trading.
  2. Tags conviction_grade so it contains the substring "CHOP" — this is
     required downstream: AutoExecutor's conviction gate for CHOP style is
         meets_conviction = ("CHOP" in grade) and (actual_conf >= min_conf)
     Any forecast returned from here that doesn't contain "CHOP" in its
     conviction_grade will always be rejected by that gate, silently.

NOTE: This is a conservative placeholder, not a recovered original
implementation — no prior version of this file was present in the
distributed repo/zip. If your team has a documented chop-mode strategy
(mean-reversion at range extremes, fade-the-pin, etc.) beyond "reuse the
main engine with a higher confidence floor," implement that here instead.
Backtest this against `backend/btc/backtest.py` before allowing CHOP style
to run in LIVE mode.
"""

import logging
from typing import Optional, Dict, Any

import pandas as pd

from backend.btc.analyzer import evaluate_next_15m_contract

logger = logging.getLogger(__name__)

# Extra distance-from-50% required in chop conditions, on top of whatever
# evaluate_next_15m_contract() already applied via its own volatility-regime
# edge shrinkage (see analyzer.py "Chop regime: shrink edge").
CHOP_EXTRA_CONFIDENCE_FLOOR = 6.0  # percentage points


def evaluate_chop_contract(
    df_ind: pd.DataFrame,
    target_price: float = None,
    kalshi_m: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Evaluate a 15m contract under a low-volatility / range-bound regime.

    Returns the same schema as evaluate_next_15m_contract() so it's a
    drop-in replacement in AutoExecutor's dispatch (probability_percent,
    primary_edge, recommendation, conviction_grade, conviction_badge,
    direction, pre_gate_direction, pre_gate_prob, raw_ml_prob, ml_prob,
    catalysts, ...).
    """
    forecast = evaluate_next_15m_contract(
        df_ind,
        target_price=target_price,
        patterns=[],  # chart patterns (triangles/flags) are momentum signals; skip in chop
        kalshi_m=kalshi_m,
        trading_style="SNIPER",
    )

    prob = float(forecast.get("probability_percent", 50.0))
    grade = str(forecast.get("conviction_grade", "") or "")
    badge = str(forecast.get("conviction_badge", "") or "")
    rec = str(forecast.get("recommendation", "") or "")

    distance_from_coinflip = abs(prob - 50.0)

    if distance_from_coinflip < CHOP_EXTRA_CONFIDENCE_FLOOR:
        # Not confident enough for a directional bet in a choppy market — pass.
        forecast["conviction_grade"] = "PASS / NO BID (CHOP)"
        forecast["conviction_badge"] = "⚪ PASS (CHOP)"
        forecast["recommendation"] = "PASS / NO BID (CHOP)"
        forecast["direction"] = "PASS"
        logger.debug(
            f"[ChopEngine] Distance from 50%% ({distance_from_coinflip:.1f}) below "
            f"chop floor ({CHOP_EXTRA_CONFIDENCE_FLOOR}); passing."
        )
        return forecast

    # Confident enough: tag the grade so it survives AutoExecutor's
    # `"CHOP" in grade` conviction gate, without discarding the underlying
    # grade tier (A+/A/B/ML MODEL) that other parts of the codebase inspect.
    if "CHOP" not in grade:
        forecast["conviction_grade"] = f"{grade} (CHOP)".strip()
    if "CHOP" not in badge:
        forecast["conviction_badge"] = f"{badge} (CHOP)".strip()
    if "CHOP" not in rec:
        forecast["recommendation"] = f"{rec} (CHOP)".strip()

    return forecast
