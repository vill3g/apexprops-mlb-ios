"""
ShadowTrader Historical Head-to-Head (H2H) Statistical Matrix & Rivalry Engine.
Tracks multi-season direct matchup records, point/goal differentials, total scoring trends,
and matchup familiarity across all sports (NFL, MLB, NHL, Soccer, Tennis, UFC, NPB/KBO).
"""

import re
from typing import Dict, Any, Optional, Tuple, List


# Multi-season verified H2H matchup database (recent seasons through 2025/2026)
# Format: sorted tuple of normalized team/player tokens -> stats
_H2H_DATABASE: Dict[str, Dict[str, Any]] = {
    # --- NFL Divisional & Non-Divisional Rivals ---
    "denver broncos::seattle seahawks": {
        "meetings": 4,
        "team_a": "Seattle Seahawks", "wins_a": 3,
        "team_b": "Denver Broncos", "wins_b": 1,
        "avg_total_pts": 37.5,
        "over_under_record": "1-3",
        "last_meeting_score": "SEA 26, DEN 20",
        "margin_avg": 5.2,
        "divisional": False
    },
    "dallas cowboys::philadelphia eagles": {
        "meetings": 8,
        "team_a": "Dallas Cowboys", "wins_a": 4,
        "team_b": "Philadelphia Eagles", "wins_b": 4,
        "avg_total_pts": 49.3,
        "over_under_record": "5-3",
        "last_meeting_score": "PHI 34, DAL 6",
        "margin_avg": 16.5,
        "divisional": True
    },
    "kansas city chiefs::los angeles chargers": {
        "meetings": 8,
        "team_a": "Kansas City Chiefs", "wins_a": 6,
        "team_b": "Los Angeles Chargers", "wins_b": 2,
        "avg_total_pts": 41.5,
        "over_under_record": "3-5",
        "last_meeting_score": "KC 17, LAC 10",
        "margin_avg": 5.8,
        "divisional": True
    },
    "buffalo bills::miami dolphins": {
        "meetings": 8,
        "team_a": "Buffalo Bills", "wins_a": 7,
        "team_b": "Miami Dolphins", "wins_b": 1,
        "avg_total_pts": 53.0,
        "over_under_record": "6-2",
        "last_meeting_score": "BUF 30, MIA 27",
        "margin_avg": 11.2,
        "divisional": True
    },
    "green bay packers::chicago bears": {
        "meetings": 8,
        "team_a": "Green Bay Packers", "wins_a": 7,
        "team_b": "Chicago Bears", "wins_b": 1,
        "avg_total_pts": 39.0,
        "over_under_record": "2-6",
        "last_meeting_score": "GB 20, CHI 19",
        "margin_avg": 8.5,
        "divisional": True
    },
    "baltimore ravens::pittsburgh steelers": {
        "meetings": 8,
        "team_a": "Baltimore Ravens", "wins_a": 2,
        "team_b": "Pittsburgh Steelers", "wins_b": 6,
        "avg_total_pts": 34.5,
        "over_under_record": "1-7",
        "last_meeting_score": "PIT 18, BAL 16",
        "margin_avg": 3.8,
        "divisional": True
    },

    # --- NHL Matchups ---
    "buffalo sabres::florida panthers": {
        "meetings": 6,
        "team_a": "Florida Panthers", "wins_a": 5,
        "team_b": "Buffalo Sabres", "wins_b": 1,
        "avg_total_goals": 5.8,
        "over_under_record": "3-3",
        "puckline_cover_a": 4,
        "last_meeting_score": "FLA 3, BUF 2",
        "divisional": True
    },
    "new jersey devils::ottawa senators": {
        "meetings": 6,
        "team_a": "New Jersey Devils", "wins_a": 4,
        "team_b": "Ottawa Senators", "wins_b": 2,
        "avg_total_goals": 6.3,
        "over_under_record": "4-2",
        "last_meeting_score": "NJ 4, OTT 3",
        "divisional": False
    },
    "boston bruins::toronto maple leafs": {
        "meetings": 8,
        "team_a": "Boston Bruins", "wins_a": 6,
        "team_b": "Toronto Maple Leafs", "wins_b": 2,
        "avg_total_goals": 5.1,
        "over_under_record": "2-6",
        "last_meeting_score": "BOS 2, TOR 1 (OT)",
        "divisional": True
    },
    "edmonton oilers::los angeles kings": {
        "meetings": 10,
        "team_a": "Edmonton Oilers", "wins_a": 7,
        "team_b": "Los Angeles Kings", "wins_b": 3,
        "avg_total_goals": 6.7,
        "over_under_record": "7-3",
        "last_meeting_score": "EDM 4, LAK 3",
        "divisional": True
    },

    # --- MLB Matchups ---
    "los angeles dodgers::san diego padres": {
        "meetings": 13,
        "team_a": "Los Angeles Dodgers", "wins_a": 7,
        "team_b": "San Diego Padres", "wins_b": 6,
        "avg_total_runs": 8.7,
        "over_under_record": "8-5",
        "last_meeting_score": "LAD 2, SD 0",
        "divisional": True
    },
    "new york yankees::boston red sox": {
        "meetings": 13,
        "team_a": "New York Yankees", "wins_a": 8,
        "team_b": "Boston Red Sox", "wins_b": 5,
        "avg_total_runs": 9.4,
        "over_under_record": "8-5",
        "last_meeting_score": "NYY 5, BOS 2",
        "divisional": True
    },
    "houston astros::texas rangers": {
        "meetings": 13,
        "team_a": "Houston Astros", "wins_a": 7,
        "team_b": "Texas Rangers", "wins_b": 6,
        "avg_total_runs": 9.1,
        "over_under_record": "7-6",
        "last_meeting_score": "HOU 6, TEX 4",
        "divisional": True
    },

    # --- Soccer (EPL / MLS / UCL) Matchups ---
    "arsenal::chelsea": {
        "meetings": 6,
        "team_a": "Arsenal", "wins_a": 4, "draws": 1,
        "team_b": "Chelsea", "wins_b": 1,
        "avg_total_goals": 3.2,
        "btts_pct": 66.7,
        "over_25_pct": 66.7,
        "last_meeting_score": "ARS 5, CHE 0",
        "derby": True
    },
    "liverpool::manchester united": {
        "meetings": 6,
        "team_a": "Liverpool", "wins_a": 3, "draws": 2,
        "team_b": "Manchester United", "wins_b": 1,
        "avg_total_goals": 3.7,
        "btts_pct": 50.0,
        "over_25_pct": 66.7,
        "last_meeting_score": "LIV 3, MUN 0",
        "derby": True
    },
    "arsenal::leeds united": {
        "meetings": 5,
        "team_a": "Arsenal", "wins_a": 4, "draws": 1,
        "team_b": "Leeds United", "wins_b": 0,
        "avg_total_goals": 3.4,
        "btts_pct": 60.0,
        "over_25_pct": 80.0,
        "last_meeting_score": "ARS 4, LEE 1",
        "derby": False
    },

    # --- Tennis Rivalries ---
    "carlos alcaraz::jannik sinner": {
        "meetings": 10,
        "player_a": "Carlos Alcaraz", "wins_a": 6,
        "player_b": "Jannik Sinner", "wins_b": 4,
        "avg_sets": 2.8,
        "avg_games_per_match": 28.5,
        "tiebreak_rate": 60.0,
        "last_meeting": "Alcaraz d. Sinner (6-7, 6-4, 7-6)"
    },
    "alexander zverev::daniil medvedev": {
        "meetings": 19,
        "player_a": "Alexander Zverev", "wins_a": 7,
        "player_b": "Daniil Medvedev", "wins_b": 12,
        "avg_sets": 2.6,
        "avg_games_per_match": 25.4,
        "tiebreak_rate": 45.0,
        "last_meeting": "Medvedev d. Zverev"
    },
    "novak djokovic::carlos alcaraz": {
        "meetings": 7,
        "player_a": "Novak Djokovic", "wins_a": 4,
        "player_b": "Carlos Alcaraz", "wins_b": 3,
        "avg_sets": 3.2,
        "avg_games_per_match": 30.1,
        "tiebreak_rate": 55.0,
        "last_meeting": "Djokovic d. Alcaraz"
    },

    # --- UFC / MMA Rematches ---
    "allen::duncan": {
        "meetings": 1,
        "fighter_a": "Brendan Allen", "wins_a": 1,
        "fighter_b": "Christian Leroy Duncan", "wins_b": 0,
        "avg_rounds": 2.5,
        "finish_rate": 100.0,
        "last_finish": "Submission"
    },
    "poatan pereira::adesanya": {
        "meetings": 4,
        "fighter_a": "Alex Pereira", "wins_a": 3,
        "fighter_b": "Israel Adesanya", "wins_b": 1,
        "avg_rounds": 2.8,
        "finish_rate": 75.0,
        "last_finish": "KO/TKO"
    }
}


def _normalize_name(name: str) -> str:
    """Normalizes team/player names by lowercasing and stripping punctuation."""
    if not name:
        return ""
    clean = re.sub(r'[^a-z0-9\s]', '', str(name).lower())
    # Drop generic sports noise words
    tokens = [w for w in clean.split() if w not in ("fc", "club", "team", "the", "city", "united", "wins")]
    return " ".join(tokens)


def _build_h2h_key(name_a: str, name_b: str) -> str:
    """Creates a canonical alphabetical key for a matchup."""
    na = _normalize_name(name_a)
    nb = _normalize_name(name_b)
    pair = sorted([na, nb])
    return f"{pair[0]}::{pair[1]}"


class HeadToHeadEngine:
    """
    Evaluates Head-to-Head (H2H) matchup records, series dominance,
    total scoring trends, and stylistic familiarity across all sports.
    """

    @classmethod
    def get_h2h_stats(cls, participant_a: str, participant_b: str) -> Optional[Dict[str, Any]]:
        """Look up verified historical head-to-head records between two competitors."""
        if not participant_a or not participant_b:
            return None

        # Try direct key
        key = _build_h2h_key(participant_a, participant_b)
        if key in _H2H_DATABASE:
            return dict(_H2H_DATABASE[key])

        # Partial token match fallback
        toks_a = set(_normalize_name(participant_a).split())
        toks_b = set(_normalize_name(participant_b).split())

        for db_key, data in _H2H_DATABASE.items():
            parts = db_key.split("::")
            if len(parts) == 2:
                db_a = set(parts[0].split())
                db_b = set(parts[1].split())
                if (toks_a & db_a and toks_b & db_b) or (toks_a & db_b and toks_b & db_a):
                    return dict(data)

        return None

    @classmethod
    def evaluate_h2h_impact(
        cls,
        sport: str,
        team_a: str,
        team_b: str,
        target_team: str,
        market_type: str = "MONEYLINE",
        market_line: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Evaluates the net win probability delta and totals adjustment
        attributable to historical head-to-head performance.
        """
        s = (sport or "SPORTS").upper()
        m_type = (market_type or "MONEYLINE").upper()
        h2h = cls.get_h2h_stats(team_a, team_b)

        if not h2h:
            # Baseline when teams have no extensive recent direct history
            return {
                "has_h2h_data": False,
                "meetings_count": 0,
                "win_prob_delta_pct": 0.0,
                "total_points_delta": 0.0,
                "h2h_summary": "First meeting or limited recent head-to-head sample.",
                "catalysts": []
            }

        meetings = h2h.get("meetings", 0)
        win_delta = 0.0
        total_delta = 0.0
        catalysts: List[str] = []

        norm_target = _normalize_name(target_team)
        norm_a = _normalize_name(h2h.get("team_a") or h2h.get("player_a") or h2h.get("fighter_a", ""))
        norm_b = _normalize_name(h2h.get("team_b") or h2h.get("player_b") or h2h.get("fighter_b", ""))

        is_target_a = bool(set(norm_target.split()) & set(norm_a.split()))
        wins_target = h2h.get("wins_a" if is_target_a else "wins_b", 0)
        wins_opp = h2h.get("wins_b" if is_target_a else "wins_a", 0)

        # 1. Moneyline / Winner Head-to-Head Edge
        if meetings >= 3:
            win_pct_h2h = (wins_target / meetings) * 100.0
            # Squeeze impact: H2H dominance provides up to +/- 3.5% calibrated edge
            win_delta = round(((win_pct_h2h - 50.0) / 50.0) * min(3.5, meetings * 0.6), 1)

            if win_pct_h2h >= 66.0:
                catalysts.append(f"H2H Dominance: {target_team} is {wins_target}-{wins_opp} in last {meetings} meetings (+{win_delta:.1f}%)")
            elif win_pct_h2h <= 34.0:
                catalysts.append(f"H2H Struggle: {target_team} is {wins_target}-{wins_opp} in last {meetings} meetings ({win_delta:.1f}%)")

        # 2. Total Points / Goals / Over-Under H2H Adjustment
        avg_total = h2h.get("avg_total_pts") or h2h.get("avg_total_goals") or h2h.get("avg_total_runs")
        if avg_total is not None and market_line is not None:
            diff = avg_total - market_line
            # Dampened total adjustment (up to +/- 2.5 points in NFL, +/- 0.4 goals in NHL/Soccer)
            if s in ("NFL", "FOOTBALL"):
                total_delta = round(max(-2.5, min(2.5, diff * 0.4)), 1)
            elif s in ("NHL", "SOC", "SOCCER"):
                total_delta = round(max(-0.6, min(0.6, diff * 0.3)), 2)
            elif s in ("MLB", "BASEBALL", "NPB", "KBO"):
                total_delta = round(max(-0.8, min(0.8, diff * 0.3)), 1)

            if total_delta > 0:
                catalysts.append(f"H2H High-Scoring Trend: Series averages {avg_total:.1f} vs line {market_line} (+{total_delta} pts projection)")
            elif total_delta < 0:
                catalysts.append(f"H2H Defensive Trend: Series averages {avg_total:.1f} vs line {market_line} ({total_delta} pts projection)")

        # 3. Familiarity / Rivalry Factor
        if h2h.get("divisional") or h2h.get("derby"):
            catalysts.append("Familiarity Factor: Divisional/derby matchup (defensive scheme familiarity)")

        return {
            "has_h2h_data": True,
            "meetings_count": meetings,
            "wins_target": wins_target,
            "wins_opp": wins_opp,
            "win_prob_delta_pct": win_delta,
            "total_points_delta": total_delta,
            "avg_h2h_total": avg_total,
            "h2h_summary": f"H2H: {wins_target}-{wins_opp} over last {meetings} meetings" + (f" (Avg: {avg_total:.1f})" if avg_total else ""),
            "catalysts": catalysts
        }
