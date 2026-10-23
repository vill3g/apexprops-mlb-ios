"""
ShadowTrader Native Sports Math: Probability Calibration & Dixon-Coles Bivariate Simulation.
"""

import math
import random
import time
from typing import Dict, Tuple, List, Optional, Any
from backend.sports_engine.math.devig import american_to_implied, american_to_decimal


def two_way_devig(over_odds: float, under_odds: float) -> Tuple[float, float, float]:
    """Power-method vig removal for 2-way markets."""
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
    fair_1 = p1 ** k
    fair_2 = p2 ** k
    norm = fair_1 + fair_2
    if norm > 0:
        return round((fair_1 / norm) * 100.0, 1), round((fair_2 / norm) * 100.0, 1), margin
    return 50.0, 50.0, margin


def three_way_devig(home_odds: float, draw_odds: float, away_odds: float) -> Tuple[float, float, float, float]:
    """Power-method vig removal for 3-way markets (Soccer 1X2 Moneyline)."""
    p_h = american_to_implied(home_odds)
    p_d = american_to_implied(draw_odds)
    p_a = american_to_implied(away_odds)
    margin = round(((p_h + p_d + p_a) - 1.0) * 100.0, 2)

    low, high = 1.0, 5.0
    for _ in range(35):
        mid = (low + high) / 2.0
        val = (p_h ** mid) + (p_d ** mid) + (p_a ** mid)
        if val > 1.0:
            low = mid
        else:
            high = mid

    k = (low + high) / 2.0
    f_h = p_h ** k
    f_d = p_d ** k
    f_a = p_a ** k
    norm = f_h + f_d + f_a

    if norm > 0:
        return (
            round((f_h / norm) * 100.0, 1),
            round((f_d / norm) * 100.0, 1),
            round((f_a / norm) * 100.0, 1),
            margin
        )
    return 33.3, 33.4, 33.3, margin


def calibrate_probability(
    raw_model_prob: float,
    market_fair_prob: float = 50.0,
    confidence_weight: float = 0.65,
    min_prob: float = 0.1,
    max_prob: float = 99.9,
    is_unit_fraction: Optional[bool] = None
) -> float:
    """Bayesian probability shrinkage towards sharp market consensus prior."""
    if is_unit_fraction is True:
        p_model = float(raw_model_prob) * 100.0
        p_market = float(market_fair_prob) if float(market_fair_prob) > 1.0 else float(market_fair_prob) * 100.0
    else:
        p_model = float(raw_model_prob)
        p_market = float(market_fair_prob)

    if 52.3 <= p_market <= 52.5:
        p_market = 50.0

    alpha = max(0.20, min(0.85, confidence_weight))
    calibrated = (alpha * p_model) + ((1.0 - alpha) * p_market)
    return round(max(min_prob, min(max_prob, calibrated)), 1)


def to_percentage(p: Any, decimals: int = 1) -> float:
    """Standardizes probability unit scale to percentage [0.0, 100.0]."""
    if p is None:
        return 0.0
    try:
        val = float(p)
    except (ValueError, TypeError):
        return 0.0

    if 0.0 < val <= 1.0:
        val = val * 100.0

    return round(max(0.0, min(100.0, val)), decimals)


def dixon_coles_soccer_simulation(
    home_xg: float,
    away_xg: float,
    rho: float = -0.11
) -> Dict[str, Any]:
    """Dixon-Coles Bivariate Poisson simulation for soccer match winner, draw, and totals."""
    def poisson_pmf(k: int, lambd: float) -> float:
        if lambd <= 0:
            return 1.0 if k == 0 else 0.0
        return (math.exp(-lambd) * (lambd ** k)) / math.factorial(k)

    max_goals = 8
    prob_matrix = [[0.0 for _ in range(max_goals + 1)] for _ in range(max_goals + 1)]
    total_prob = 0.0

    for x in range(max_goals + 1):
        for y in range(max_goals + 1):
            base_p = poisson_pmf(x, max(0.1, home_xg)) * poisson_pmf(y, max(0.1, away_xg))
            if x == 0 and y == 0:
                tau = max(0.2, 1.0 - (home_xg * away_xg * rho))
            elif x == 0 and y == 1:
                tau = max(0.2, 1.0 + (home_xg * rho))
            elif x == 1 and y == 0:
                tau = max(0.2, 1.0 + (away_xg * rho))
            elif x == 1 and y == 1:
                tau = max(0.2, 1.0 - rho)
            else:
                tau = 1.0

            p = base_p * tau
            prob_matrix[x][y] = p
            total_prob += p

    if total_prob > 0:
        for x in range(max_goals + 1):
            for y in range(max_goals + 1):
                prob_matrix[x][y] /= total_prob

    home_wins = 0.0
    draws = 0.0
    away_wins = 0.0
    over_25 = 0.0
    under_25 = 0.0
    btts_yes = 0.0
    exp_goals = 0.0

    for x in range(max_goals + 1):
        for y in range(max_goals + 1):
            p = prob_matrix[x][y]
            if x > y:
                home_wins += p
            elif x == y:
                draws += p
            else:
                away_wins += p

            if (x + y) > 2.5:
                over_25 += p
            else:
                under_25 += p

            if x > 0 and y > 0:
                btts_yes += p

            exp_goals += (x + y) * p

    return {
        "home_win_prob": round(home_wins * 100.0, 1),
        "draw_prob": round(draws * 100.0, 1),
        "away_win_prob": round(away_wins * 100.0, 1),
        "over_25_prob": round(over_25 * 100.0, 1),
        "under_25_prob": round(under_25 * 100.0, 1),
        "btts_prob": round(btts_yes * 100.0, 1),
        "avg_total_goals": round(exp_goals, 2)
    }
