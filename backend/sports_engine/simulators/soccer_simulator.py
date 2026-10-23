"""
ShadowTrader Native Soccer Simulator: Dixon-Coles 3-Way & Totals Engine.
Covers Premier League, Champions League, MLS, La Liga, and international soccer.
"""

from typing import Dict, Any, Optional
from backend.sports_engine.math.calibrator import dixon_coles_soccer_simulation


def simulate_soccer_match(
    home_team: str,
    away_team: str,
    home_attack_strength: float = 1.35,
    away_attack_strength: float = 1.15,
    home_defense_weakness: float = 1.05,
    away_defense_weakness: float = 1.15,
    league: str = "EPL"
) -> Dict[str, Any]:
    """Runs Dixon-Coles simulation for 3-way match winner, draw, and over/under 2.5 goals."""
    # Compute expected goals (xG)
    h_xg = max(0.4, min(4.2, home_attack_strength * away_defense_weakness))
    a_xg = max(0.3, min(3.8, away_attack_strength * home_defense_weakness * 0.88))  # Home advantage factor

    sim_res = dixon_coles_soccer_simulation(h_xg, a_xg, rho=-0.11)

    return {
        "home_team": home_team,
        "away_team": away_team,
        "league": league,
        "projected_home_xg": round(h_xg, 2),
        "projected_away_xg": round(a_xg, 2),
        "home_win_prob": sim_res["home_win_prob"],
        "draw_prob": sim_res["draw_prob"],
        "away_win_prob": sim_res["away_win_prob"],
        "over_25_prob": sim_res["over_25_prob"],
        "under_25_prob": sim_res["under_25_prob"],
        "btts_prob": sim_res["btts_prob"],
        "avg_total_goals": sim_res["avg_total_goals"],
        "factor_impacts": {
            "home_pitch_advantage_pct": 4.2,
            "attack_differential_xg": round(h_xg - a_xg, 2)
        }
    }
