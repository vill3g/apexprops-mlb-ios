"""
ShadowTrader Native NFL Simulator: Key Numbers & Margin Distribution Engine.
Models NFL discrete margin clusters (3, 7, 10, 14, 6) for moneyline, spread, and totals.
"""

import math
from typing import Dict, Any, Optional

# Empirical margin probabilities in the NFL
NFL_KEY_NUMBERS = {
    3: 0.152,  # 15.2% of NFL games finish with a 3-point margin
    7: 0.093,  # 9.3% finish with a 7-point margin
    6: 0.059,  # 5.9% finish with a 6-point margin
    10: 0.057, # 5.7% finish with a 10-point margin
    4: 0.051,  # 5.1% finish with a 4-point margin
    14: 0.048  # 4.8% finish with a 14-point margin
}


def nfl_spread_to_win_prob(spread_pts: float, is_favorite: bool = True) -> float:
    """
    Converts point spread to win probability using the empirical cumulative margin function.
    Spread is passed as absolute value or negative for favorite (e.g. -3.5 or 3.5).
    """
    s = abs(float(spread_pts))
    # Approximation of normal margin with key number discretization
    # Margin mean = spread, std = 13.86
    z = s / 13.86
    # Error function normal cdf
    base_cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

    # Key number cluster boosts
    if 2.5 <= s <= 3.5:
        base_cdf += 0.015
    elif 6.5 <= s <= 7.5:
        base_cdf += 0.012

    prob = base_cdf if is_favorite else (1.0 - base_cdf)
    return round(max(0.05, min(0.95, prob)) * 100.0, 1)


def simulate_nfl_matchup(
    home_team: str,
    away_team: str,
    spread: float = -2.5,
    total: float = 44.5,
    home_qb_rating: float = 95.0,
    away_qb_rating: float = 90.0
) -> Dict[str, Any]:
    """Simulates an NFL game for moneyline, spread, and game totals."""
    # Negative spread means home team is favorite
    is_home_favorite = (spread <= 0)
    home_win_prob = nfl_spread_to_win_prob(abs(spread), is_favorite=is_home_favorite)
    away_win_prob = round(100.0 - home_win_prob, 1)

    # Spread cover probability (standard market line has ~50% fair probability)
    qb_diff = (home_qb_rating - away_qb_rating) / 10.0
    home_cover_prob = round(max(30.0, min(70.0, 50.0 + (qb_diff * 1.5))), 1)
    away_cover_prob = round(100.0 - home_cover_prob, 1)

    # Total over/under & H2H adjustment
    from backend.sports_engine.h2h_matrix import HeadToHeadEngine
    h2h_res = HeadToHeadEngine.evaluate_h2h_impact(
        sport="NFL",
        team_a=home_team,
        team_b=away_team,
        target_team=home_team,
        market_type="TOTAL",
        market_line=total
    )
    h2h_total_shift = h2h_res.get("total_points_delta", 0.0)

    proj_total = round(total + (qb_diff * 0.4) + h2h_total_shift, 1)
    over_prob = round(max(35.0, min(65.0, 50.0 + ((proj_total - total) * 3.5))), 1)
    under_prob = round(100.0 - over_prob, 1)

    return {
        "home_team": home_team,
        "away_team": away_team,
        "spread_line": spread,
        "total_line": total,
        "home_win_prob": home_win_prob,
        "away_win_prob": away_win_prob,
        "home_cover_spread_prob": home_cover_prob,
        "away_cover_spread_prob": away_cover_prob,
        "over_prob": over_prob,
        "under_prob": under_prob,
        "projected_total": proj_total,
        "h2h_stats": h2h_res,
        "factor_impacts": {
            "qb_differential_impact": round(qb_diff * 2.0, 1),
            "h2h_total_shift": h2h_total_shift,
            "h2h_summary": h2h_res.get("h2h_summary", ""),
            "key_number_3_significance": "HIGH (15.2% frequency)",
            "key_number_7_significance": "MEDIUM (9.3% frequency)",
            "home_field_points": 1.8
        }
    }
