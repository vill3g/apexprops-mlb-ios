"""
ShadowTrader Master Sports Capper Engine.
Institutional-grade quantitative handicapping, CLV tracking, situational factor adjustments,
net EV fee factoring, and fractional Kelly staking for Kalshi binary sports markets.
"""

import math
import logging
from typing import Dict, Any, List, Optional, Tuple

from backend.sports_engine.math.devig import (
    american_to_decimal,
    american_to_implied,
    calculate_kelly_criterion
)
from backend.sports_engine.math.calibrator import calibrate_probability

from backend.sports_engine.situational import SituationalEngine

logger = logging.getLogger(__name__)


# Kalshi binary options transaction fee formula: 7% of p * (1 - p)
def calculate_kalshi_taker_fee(price_dollars: float) -> float:
    """Computes Kalshi taker fee per contract in dollars: 0.07 * P * (1 - P)."""
    p = max(0.01, min(0.99, float(price_dollars)))
    return round(0.07 * p * (1.0 - p), 4)


class MasterSportsCapper:
    """
    Syndicate-grade sports handicapper engine.
    Combines:
    1. Closing Line Value (CLV) & Sharp Consensus Edge
    2. Situational Factor Attribution (Fatigue, Rest, Matchup Leverage)
    3. Net Expected Value after Kalshi Binary Option Fees
    4. Fractional Kelly Bankroll Optimization
    5. Capper Conviction Grading & Actionable Thesis
    """

    @staticmethod
    def evaluate_capper_edge(
        sport: str,
        matchup: str,
        pick_name: str,
        market_type: str,
        model_win_prob: float,
        kalshi_price_dollars: float,
        situational_factors: Optional[Dict[str, Any]] = None,
        bankroll: float = 1000.0,
        max_bankroll_pct: float = 5.0
    ) -> Dict[str, Any]:
        """
        Comprehensive master handicapper evaluation for a prospective sports trade.
        """
        p_price = max(0.01, min(0.99, float(kalshi_price_dollars)))
        kalshi_implied_pct = round(p_price * 100.0, 1)

        # 1. Base model probability & situational adjustments
        base_win_pct = max(1.0, min(99.0, float(model_win_prob)))
        sit = situational_factors or {}

        # Evaluate through SituationalEngine
        sit_eval = SituationalEngine.evaluate_situational_catalysts(
            sport=sport,
            matchup=matchup,
            team_selected=pick_name,
            market_type=market_type,
            rest_days_team=sit.get("rest_days_team", sit.get("rest_advantage_days", 1)),
            rest_days_opp=sit.get("rest_days_opp", 1),
            is_travel_game=sit.get("is_travel_game", False),
            starter_delta_pct=sit.get("starter_differential_pct", 0.0),
            spread_pts=sit.get("spread_pts"),
            opponent_name=sit.get("opponent_name"),
            market_line=sit.get("market_line") or sit.get("total_line")
        )

        sit_delta = sit_eval.get("net_situational_delta_pct", 0.0)
        capper_notes: List[str] = list(sit_eval.get("catalysts", []))

        # Net calibrated handicapper probability
        adjusted_win_pct = max(5.0, min(95.0, base_win_pct + sit_delta))
        p_model = adjusted_win_pct / 100.0

        # 2. Raw and Net Expected Value (Accounting for Kalshi fees)
        fee_per_contract = calculate_kalshi_taker_fee(p_price)
        # Gross profit if win: (1.0 - p_price)
        # Gross loss if lose: p_price
        gross_ev_dollars = (p_model * (1.0 - p_price)) - ((1.0 - p_model) * p_price)
        net_ev_dollars = gross_ev_dollars - fee_per_contract
        net_ev_pct = round((net_ev_dollars / p_price) * 100.0, 2) if p_price > 0 else 0.0

        # Market Edge (Win Prob vs Implied Price)
        raw_edge_pct = round(adjusted_win_pct - kalshi_implied_pct, 1)

        # 3. Fractional Kelly Criterion Staking (Quarter-Kelly)
        # Decimal odds = 1 / p_price
        dec_odds = 1.0 / p_price
        kelly_res = calculate_kelly_criterion(
            model_win_prob=adjusted_win_pct,
            american_odds=f"+{int((dec_odds - 1.0)*100)}" if dec_odds >= 2.0 else f"-{int(100.0/(dec_odds - 1.0))}",
            kelly_fraction=0.25,
            max_bankroll_pct=max_bankroll_pct,
            is_unit_fraction=False
        )

        recommended_bankroll_pct = kelly_res.get("bankroll_pct", 0.0) if net_ev_dollars > 0 else 0.0
        recommended_wager_dollars = round((recommended_bankroll_pct / 100.0) * bankroll, 2)
        if net_ev_dollars <= 0.0:
            recommended_wager_dollars = 0.0

        # 4. Master Capper Conviction Grading
        if net_ev_pct >= 8.0 and adjusted_win_pct >= 58.0 and raw_edge_pct >= 5.0:
            grade = "A+"
            stars = "⭐⭐⭐⭐⭐"
            tier_label = "INSTITUTIONAL_LOCK"
            conviction_desc = "High-conviction syndicate edge with significant net expected value above market consensus."
        elif net_ev_pct >= 4.0 and adjusted_win_pct >= 54.0 and raw_edge_pct >= 3.0:
            grade = "A"
            stars = "⭐⭐⭐⭐"
            tier_label = "SHARP_VALUE"
            conviction_desc = "Solid quantitative alpha with favorable risk-adjusted payout profile."
        elif net_ev_pct >= 1.5 and raw_edge_pct >= 1.5:
            grade = "B+"
            stars = "⭐⭐⭐"
            tier_label = "EDGE_PLAY"
            conviction_desc = "Moderate edge meeting minimum EV thresholds. Managed position sizing recommended."
        elif net_ev_dollars > 0:
            grade = "B"
            stars = "⭐⭐"
            tier_label = "LEAN"
            conviction_desc = "Marginal edge after exchange fees; low-confidence play."
        else:
            grade = "F"
            stars = "❌"
            tier_label = "NEGATIVE_EV_PASS"
            conviction_desc = "Negative mathematical expectation after exchange fees. Capital Guard vetoes trade."

        # 5. Formulate Master Capper Thesis
        sport_label = (sport or "SPORTS").upper()
        thesis = (
            f"[{grade} {stars} | {tier_label}] {pick_name} in {matchup} ({market_type}). "
            f"Model projects {adjusted_win_pct:.1f}% win probability vs Kalshi's ${p_price:.2f} ({kalshi_implied_pct:.1f}% implied), "
            f"delivering +{raw_edge_pct:.1f}% raw edge and +{net_ev_pct:.1f}% Net EV after fees. "
            f"Recommended allocation: {recommended_bankroll_pct:.1f}% of bankroll (${recommended_wager_dollars:.2f})."
        )
        if capper_notes:
            thesis += f" Key situational factors: {'; '.join(capper_notes)}."

        return {
            "sport": sport_label,
            "matchup": matchup,
            "pick": pick_name,
            "market_type": market_type,
            "kalshi_price": round(p_price, 2),
            "kalshi_implied_pct": kalshi_implied_pct,
            "model_win_pct": adjusted_win_pct,
            "raw_edge_pct": raw_edge_pct,
            "fee_per_contract": fee_per_contract,
            "net_ev_dollars": round(net_ev_dollars, 4),
            "net_ev_pct": net_ev_pct,
            "is_plus_ev": bool(net_ev_dollars > 0),
            "grade": grade,
            "stars": stars,
            "tier_label": tier_label,
            "conviction_desc": conviction_desc,
            "kelly_bankroll_pct": recommended_bankroll_pct,
            "recommended_wager": recommended_wager_dollars,
            "capper_thesis": thesis,
            "capper_notes": capper_notes
        }
