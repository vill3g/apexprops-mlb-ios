"""
backend/btc/kelly_scaler.py
Conviction-Calibrated Dynamic Kelly Sizing Engine for Gemini 15M Gate.

Dynamically sizes position contracts based on:
  - Gemini Conviction Grade & Calibrated Confidence (72% to 95%).
  - Stale Quote Arbitrage Edge (boosts sizing when market makers lag spot by >= 0.14%).
  - Dual-Model Debate Unanimity (boosts sizing when gemini-3.8-flash and gemini-3.7-flash agree).
  - Volatility / Deadzone penalties (reduces size when near strike deadzone or macro event horizon).
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def calculate_dynamic_kelly_size(
    base_contracts: int,
    confidence: float,
    is_snipe_opportunity: bool = False,
    is_unanimous_debate: bool = False,
    is_deadzone: bool = False,
    is_macro_risk: bool = False,
) -> Dict[str, Any]:
    """
    Computes dynamic contract sizing and multiplier.
    Returns:
      - scaled_contracts: int
      - multiplier: float
      - grade: str ("GRADE_A_PLUS", "GRADE_A", "GRADE_B", "GRADE_C")
      - sizing_rationale: str
    """
    base = max(1, int(base_contracts or 1))
    conf = float(confidence or 50.0)

    # Base multiplier from confidence
    if conf >= 82.0 or is_snipe_opportunity:
        grade = "GRADE_A_PLUS (Maximum Institutional Edge)"
        multiplier = 2.0 if is_snipe_opportunity else 1.6
    elif conf >= 76.0:
        grade = "GRADE_A (High Conviction Confluence)"
        multiplier = 1.3
    elif conf >= 72.0:
        grade = "GRADE_B (Standard Quality Setup)"
        multiplier = 1.0
    else:
        grade = "GRADE_C (Marginal Edge / High Caution)"
        multiplier = 0.6

    # Apply Debate Bonus
    if is_unanimous_debate and multiplier >= 1.0:
        multiplier = round(multiplier * 1.15, 2)

    # Penalties
    if is_deadzone:
        multiplier = round(multiplier * 0.70, 2)
    if is_macro_risk:
        multiplier = round(multiplier * 0.50, 2)

    multiplier = max(0.5, min(2.5, multiplier))
    scaled = max(1, int(round(base * multiplier)))

    return {
        "base_contracts": base,
        "scaled_contracts": scaled,
        "multiplier": multiplier,
        "conviction_grade": grade,
        "sizing_rationale": f"Confidence {conf:.0f}% with multiplier {multiplier:.2f}x (Grade: {grade})",
    }
