"""
ShadowTrader Native Sports Math: Institutional Devigging & Sizing.
"""

import math
from typing import Dict, Tuple, Optional, List, Any


def american_to_decimal(american_odds: Any) -> float:
    """Converts American odds (-110, +150, '+150') to European decimal odds."""
    try:
        val = float(str(american_odds).replace("+", "").strip())
    except (ValueError, TypeError):
        return 1.0
    if val > 0:
        return 1.0 + (val / 100.0)
    elif val < 0:
        return 1.0 + (100.0 / abs(val))
    return 1.0


def decimal_to_american(decimal_odds: float) -> str:
    """Converts decimal odds (e.g. 2.50) to formatted American odds (+150)."""
    if decimal_odds <= 1.0:
        return "+100"
    b = decimal_odds - 1.0
    if b >= 1.0:
        val = int(round(b * 100))
        return f"+{val}"
    else:
        val = int(round(100.0 / b))
        return f"-{val}"


def american_to_implied(american_odds: Any) -> float:
    """Calculates naive implied probability from raw American odds."""
    try:
        val = float(str(american_odds).replace("+", "").strip())
    except (ValueError, TypeError):
        return 0.5
    if val > 0:
        return 100.0 / (val + 100.0)
    elif val < 0:
        abs_val = abs(val)
        return abs_val / (abs_val + 100.0)
    return 0.5


def _normalize_win_prob(model_win_prob: float, is_unit_fraction: Optional[bool] = None) -> float:
    prob = float(model_win_prob)
    if is_unit_fraction is True:
        p = prob / 100.0 if prob > 1.0 else prob
    elif is_unit_fraction is False:
        p = prob / 100.0
    else:
        p = prob / 100.0 if prob > 1.0 else prob
    return max(0.0, min(1.0, p))


def calculate_ev(model_win_prob: float, decimal_odds: float, is_unit_fraction: Optional[bool] = None) -> float:
    """Calculates Expected Value percentage: EV% = (p * dec - 1.0) * 100."""
    p = _normalize_win_prob(model_win_prob, is_unit_fraction)
    return round((p * float(decimal_odds) - 1.0) * 100.0, 2)


def multiplicative_devig(over_odds: float, under_odds: float) -> Tuple[float, float, float]:
    """Returns (fair_prob_over, fair_prob_under, bookmaker_margin)."""
    raw_over = american_to_implied(over_odds)
    raw_under = american_to_implied(under_odds)
    total_implied = raw_over + raw_under
    margin = round((total_implied - 1.0) * 100, 2)
    fair_over = raw_over / total_implied if total_implied > 0 else 0.5
    fair_under = raw_under / total_implied if total_implied > 0 else 0.5
    return fair_over, fair_under, margin


def power_devig(over_odds: float, under_odds: float) -> Tuple[float, float, float]:
    """Power method devigging: Solves for k such that implied_over^k + implied_under^k = 1.0."""
    p1 = american_to_implied(over_odds)
    p2 = american_to_implied(under_odds)
    margin = round(((p1 + p2) - 1.0) * 100, 2)

    low, high = 1.0, 5.0
    for _ in range(35):
        mid = (low + high) / 2.0
        val = (p1 ** mid) + (p2 ** mid)
        if val > 1.0:
            low = mid
        else:
            high = mid

    k = (low + high) / 2.0
    fair_over = p1 ** k
    fair_under = p2 ** k
    norm = fair_over + fair_under
    if norm > 0:
        return fair_over / norm, fair_under / norm, margin
    return 0.5, 0.5, margin


def shin_devig(over_odds: float, under_odds: float) -> Tuple[float, float, float, float]:
    """Shin's Model devigging accounting for informed trader fraction z."""
    beta1 = american_to_implied(over_odds)
    beta2 = american_to_implied(under_odds)
    sum_beta = beta1 + beta2
    margin = round((sum_beta - 1.0) * 100, 2)

    if sum_beta <= 1.0:
        return beta1 / sum_beta, beta2 / sum_beta, 0.0, margin

    low_z, high_z = 0.0, 0.40
    best_z = 0.0

    for _ in range(40):
        mid_z = (low_z + high_z) / 2.0

        def calc_p(beta, z):
            inner = (z ** 2) + 4.0 * (1.0 - z) * (beta ** 2) / sum_beta
            return (math.sqrt(max(0.0, inner)) - z) / (2.0 * (1.0 - z))

        p1 = calc_p(beta1, mid_z)
        p2 = calc_p(beta2, mid_z)
        p_sum = p1 + p2

        if p_sum > 1.0:
            low_z = mid_z
        else:
            high_z = mid_z
        best_z = mid_z

    fair_over = calc_p(beta1, best_z)
    fair_under = calc_p(beta2, best_z)
    tot = fair_over + fair_under
    if tot > 0:
        fair_over /= tot
        fair_under /= tot

    return fair_over, fair_under, round(best_z, 4), margin


def calculate_kelly_criterion(
    model_win_prob: float,
    american_odds: Any,
    kelly_fraction: float = 0.25,
    max_bankroll_pct: float = 5.0,
    is_unit_fraction: Optional[bool] = None
) -> Dict[str, Any]:
    """Calculates fractional Kelly Criterion sizing."""
    p = _normalize_win_prob(model_win_prob, is_unit_fraction)
    dec_odds = american_to_decimal(american_odds)
    b = dec_odds - 1.0

    if b <= 0.0 or p <= 0.0:
        ev_edge_pct = round((p * dec_odds - 1.0) * 100, 2) if b > 0.0 else 0.0
        return {
            "recommended_units": 0.0,
            "bankroll_pct": 0.0,
            "is_plus_ev": False,
            "full_kelly_pct": 0.0,
            "ev_edge_pct": ev_edge_pct
        }

    q = 1.0 - p
    full_kelly = (b * p - q) / b

    if full_kelly <= 0.0:
        return {
            "recommended_units": 0.0,
            "bankroll_pct": 0.0,
            "is_plus_ev": False,
            "full_kelly_pct": 0.0,
            "ev_edge_pct": round((p * dec_odds - 1.0) * 100, 2)
        }

    fractional_kelly = full_kelly * kelly_fraction
    capped_pct = min(max_bankroll_pct, fractional_kelly * 100.0)
    recommended_units = round(capped_pct, 2)

    return {
        "recommended_units": recommended_units,
        "bankroll_pct": round(capped_pct, 2),
        "is_plus_ev": True,
        "full_kelly_pct": round(full_kelly * 100.0, 2),
        "ev_edge_pct": round((p * dec_odds - 1.0) * 100, 2)
    }
