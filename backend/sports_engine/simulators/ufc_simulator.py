"""
ShadowTrader Native UFC Simulator: Empirical Striking & Grappling Engine.
Simulates UFC bout winner, inside-distance finish rates, and round totals.
"""

from typing import Dict, Any, Optional

DIVISION_FINISH_RATES = {
    "FLYWEIGHT": 0.44,
    "BANTAMWEIGHT": 0.48,
    "FEATHERWEIGHT": 0.52,
    "LIGHTWEIGHT": 0.58,
    "WELTERWEIGHT": 0.55,
    "MIDDLEWEIGHT": 0.62,
    "LIGHT HEAVYWEIGHT": 0.68,
    "HEAVYWEIGHT": 0.76,
    "WOMEN_STRAWWEIGHT": 0.32,
    "WOMEN_FLYWEIGHT": 0.36,
    "WOMEN_BANTAMWEIGHT": 0.42,
    "DEFAULT": 0.54
}


def simulate_ufc_fight(
    fighter_a: str,
    fighter_b: str,
    division: str = "WELTERWEIGHT",
    fighter_a_slpm: float = 4.2,  # Significant strikes landed per min
    fighter_b_slpm: float = 3.8,
    fighter_a_td_avg: float = 1.8, # Takedowns per 15 min
    fighter_b_td_avg: float = 1.2,
    scheduled_rounds: int = 3
) -> Dict[str, Any]:
    """Simulates a UFC bout for winner, inside the distance finish, and round totals."""
    div_key = str(division or "WELTERWEIGHT").upper().replace(" ", "_")
    finish_prior = DIVISION_FINISH_RATES.get(div_key, DIVISION_FINISH_RATES["DEFAULT"])
    if scheduled_rounds == 5:
        finish_prior = min(0.85, finish_prior * 1.25)

    # Differential scores
    strike_diff = (fighter_a_slpm - fighter_b_slpm) * 3.5
    td_diff = (fighter_a_td_avg - fighter_b_td_avg) * 2.8
    total_advantage = strike_diff + td_diff

    # Model win probability (base 50% shifted by striking/grappling edge)
    prob_a = max(20.0, min(80.0, 50.0 + total_advantage))
    prob_b = 100.0 - prob_a

    # Inside the distance probability
    inside_dist_prob = round(finish_prior * 100.0, 1)
    decision_prob = round(100.0 - inside_dist_prob, 1)

    return {
        "fighter_a": fighter_a,
        "fighter_b": fighter_b,
        "division": div_key,
        "scheduled_rounds": scheduled_rounds,
        "fighter_a_win_prob": round(prob_a, 1),
        "fighter_b_win_prob": round(prob_b, 1),
        "inside_distance_prob": inside_dist_prob,
        "goes_to_decision_prob": decision_prob,
        "round_total_line": 1.5 if scheduled_rounds == 3 else 2.5,
        "factor_impacts": {
            "division_finish_baseline": round(finish_prior * 100.0, 1),
            "striking_differential_impact": round(strike_diff, 1),
            "grappling_differential_impact": round(td_diff, 1)
        }
    }
