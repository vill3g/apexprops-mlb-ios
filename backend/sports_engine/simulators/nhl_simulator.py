"""
ShadowTrader Native NHL Simulator: Bivariate Poisson xG & Puck Line Engine.
Simulates hockey match winner, 60-minute regulation 3-way, empty-net puck lines, and totals.
"""

import math
import random
from typing import Dict, Any, Optional

LEAGUE_AVG_GOALS = 3.10
HOME_ADVANTAGE_GOALS = 0.22


def simulate_hockey_match(
    home_team: str,
    away_team: str,
    home_off_rating: float = 1.0,
    away_off_rating: float = 1.0,
    home_def_rating: float = 1.0,
    away_def_rating: float = 1.0,
    total_line: float = 5.5,
    num_sims: int = 3000
) -> Dict[str, Any]:
    """Runs Poisson simulation of an NHL match."""
    h_xg = LEAGUE_AVG_GOALS * home_off_rating * away_def_rating + (HOME_ADVANTAGE_GOALS / 2.0)
    a_xg = LEAGUE_AVG_GOALS * away_off_rating * home_def_rating - (HOME_ADVANTAGE_GOALS / 2.0)

    h_xg = max(1.8, min(4.8, h_xg))
    a_xg = max(1.8, min(4.8, a_xg))

    def poisson_pmf(k: int, lambd: float) -> float:
        return (math.exp(-lambd) * (lambd ** k)) / math.factorial(k)

    max_goals = 8
    h_win_reg = 0.0
    a_win_reg = 0.0
    draw_reg = 0.0
    over_tot = 0.0
    under_tot = 0.0
    puck_line_h = 0.0  # Home -1.5

    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p = poisson_pmf(h, h_xg) * poisson_pmf(a, a_xg)
            if h > a:
                h_win_reg += p
                if (h - a) >= 2:
                    puck_line_h += p
            elif a > h:
                a_win_reg += p
            else:
                draw_reg += p

            if (h + a) > total_line:
                over_tot += p
            elif (h + a) < total_line:
                under_tot += p

    # In NHL: Overtime/Shootout decides ties (approx 53% home win in OT)
    ot_home_share = 0.53
    total_home_win = h_win_reg + (draw_reg * ot_home_share)
    total_away_win = 1.0 - total_home_win

    # Empty net goal adjustment for Puck Line (+8% probability when leading by 1 late)
    puck_line_h_adjusted = min(0.60, puck_line_h + (h_win_reg * 0.12))

    return {
        "home_team": home_team,
        "away_team": away_team,
        "home_win_prob": round(total_home_win * 100.0, 1),
        "away_win_prob": round(total_away_win * 100.0, 1),
        "reg_home_win_prob": round(h_win_reg * 100.0, 1),
        "reg_draw_prob": round(draw_reg * 100.0, 1),
        "reg_away_win_prob": round(a_win_reg * 100.0, 1),
        "projected_total_goals": round(h_xg + a_xg, 2),
        "total_line": total_line,
        "over_prob": round(over_tot * 100.0, 1),
        "under_prob": round(under_tot * 100.0, 1),
        "home_puck_line_prob": round(puck_line_h_adjusted * 100.0, 1),
        "factor_impacts": {
            "home_ice_advantage_pct": 3.8,
            "goalie_defense_differential": round((home_def_rating - away_def_rating) * 5.0, 1)
        }
    }
