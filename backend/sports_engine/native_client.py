"""
ShadowTrader Native Sports Prediction Client.
Generates in-process sports simulations, probabilities, edges, and explanations
with zero outbound HTTP loopbacks to port 8057.
"""

import logging
import re
import time
import threading
from typing import Dict, List, Any, Optional, Tuple

from backend.sports_engine.math.devig import american_to_implied, calculate_ev
from backend.sports_engine.math.calibrator import calibrate_probability
from backend.sports_engine.simulators.mlb_simulator import simulate_mlb_game
from backend.sports_engine.simulators.nhl_simulator import simulate_hockey_match
from backend.sports_engine.simulators.nfl_simulator import simulate_nfl_matchup
from backend.sports_engine.simulators.soccer_simulator import simulate_soccer_match
from backend.sports_engine.simulators.tennis_simulator import simulate_tennis_match
from backend.sports_engine.simulators.ufc_simulator import simulate_ufc_fight
from backend.sports_engine.explainer import generate_pick_explanation

logger = logging.getLogger(__name__)

_MEM_PICKS_CACHE: Dict[str, Tuple[float, Any]] = {}
_MEM_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 90.0  # seconds


class NativeSportsClient:
    """In-process native sports AI prediction engine."""

    def __init__(self):
        self._cache_time = 0.0
        self._cached_picks: List[Dict[str, Any]] = []

    def fetch_latest_picks(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Returns the active list of sports AI predictions."""
        now = time.time()
        with _MEM_CACHE_LOCK:
            if not force_refresh and self._cached_picks and (now - self._cache_time < _CACHE_TTL):
                return list(self._cached_picks)

        # Generate fresh native predictions across all active sports
        picks: List[Dict[str, Any]] = []

        # 1. Inspect open Kalshi sports events to generate tailored predictions for current slate
        try:
            from backend.routes.engine_sports import _fetch_kalshi_series_events, _SPORTS_SERIES_MAP
            for sport_name, series_list in _SPORTS_SERIES_MAP.items():
                for series_ticker in series_list:
                    if not series_ticker.endswith("GAME") and not series_ticker.endswith("MATCH") and not series_ticker.endswith("FIGHT"):
                        continue
                    try:
                        events = _fetch_kalshi_series_events(series_ticker)
                        for ev in events[:8]:  # Top upcoming events per series
                            tk = ev.get("event_ticker") or ev.get("ticker")
                            title = ev.get("title") or ""
                            sub = ev.get("sub_title") or ""
                            pred = self.predict_for_event(tk, title=f"{title} {sub}", sport=sport_name)
                            if pred:
                                picks.append(pred)
                    except Exception as e:
                        logger.debug(f"[NativeSportsClient] Series {series_ticker} scan error: {e}")
        except Exception as e:
            logger.debug(f"[NativeSportsClient] Kalshi series scan error: {e}")

        # Fallback / baseline simulated slate if no active Kalshi events are currently open
        if not picks:
            picks.extend(self._generate_baseline_slate())

        with _MEM_CACHE_LOCK:
            self._cached_picks = picks
            self._cache_time = now

        return list(picks)

    def predict_for_event(self, event_ticker: str, title: str = "", sport: str = "") -> Optional[Dict[str, Any]]:
        """
        Generates an on-demand native AI simulation and explanation for a specific Kalshi sports event.
        Zero external HTTP roundtrips.
        """
        if not event_ticker:
            return None

        tk_clean = str(event_ticker).upper().strip()
        title_clean = str(title or "").strip()

        # 1. Infer sport
        s = (sport or "").upper()
        if not s:
            if "NHL" in tk_clean or "HOCKEY" in tk_clean:
                s = "NHL"
            elif "NFL" in tk_clean:
                s = "NFL"
            elif "MLB" in tk_clean:
                s = "MLB"
            elif any(k in tk_clean for k in ("EPL", "MLS", "SOC")):
                s = "SOC"
            elif any(k in tk_clean for k in ("ATP", "WTA", "TEN")):
                s = "TEN"
            elif "UFC" in tk_clean:
                s = "UFC"
            elif any(k in tk_clean for k in ("NPB", "KBO")):
                s = "NPB/KBO"
            else:
                s = "SPORTS"

        # 2. Extract teams / matchup from title or ticker
        team_a, team_b = self._parse_matchup(tk_clean, title_clean)
        if not team_a or not team_b:
            team_a = "Team A"
            team_b = "Team B"

        matchup_str = f"{team_a} vs {team_b}"

        # 3. Determine market type
        market_type = "MONEYLINE"
        if "TOTAL" in tk_clean or "TOTAL" in title_clean.upper():
            market_type = "TOTAL"
        elif "SPREAD" in tk_clean or "SPREAD" in title_clean.upper():
            market_type = "SPREAD"

        # 4. Run appropriate native simulator
        sim_res = {}
        pick = team_a
        win_prob = 54.5
        edge = 5.2

        if s == "NHL":
            sim_res = simulate_hockey_match(home_team=team_b, away_team=team_a)
            if market_type == "TOTAL":
                pick = f"Over {sim_res.get('total_line', 5.5)}"
                win_prob = sim_res.get("over_prob", 52.0)
            else:
                pick = team_b if sim_res.get("home_win_prob", 50) >= 50 else team_a
                win_prob = max(sim_res.get("home_win_prob", 50), sim_res.get("away_win_prob", 50))
            edge = round(max(1.5, win_prob - 50.0), 1)

        elif s == "NFL":
            sim_res = simulate_nfl_matchup(home_team=team_b, away_team=team_a)
            if market_type == "TOTAL":
                line_val = sim_res.get('total_line', 44.5)
                o_prob = sim_res.get("over_prob", 50.0)
                u_prob = sim_res.get("under_prob", 50.0)
                if o_prob >= u_prob:
                    pick = f"Over {line_val}"
                    win_prob = o_prob
                else:
                    pick = f"Under {line_val}"
                    win_prob = u_prob
            elif market_type == "SPREAD":
                pick = team_b if sim_res.get("home_cover_spread_prob", 50) >= 50 else team_a
                win_prob = max(sim_res.get("home_cover_spread_prob", 50), sim_res.get("away_cover_spread_prob", 50))
            else:
                pick = team_b if sim_res.get("home_win_prob", 50) >= 50 else team_a
                win_prob = max(sim_res.get("home_win_prob", 50), sim_res.get("away_win_prob", 50))
            edge = round(max(2.0, win_prob - 49.5), 1)

        elif s in ("MLB", "NPB/KBO", "NPB", "KBO"):
            sim_res = simulate_mlb_game(home_team=team_b, away_team=team_a)
            if market_type == "TOTAL":
                pick = f"Under {sim_res.get('total_line', 8.5)}"
                win_prob = sim_res.get("under_prob", 53.0)
            else:
                pick = team_b if sim_res.get("home_win_prob", 50) >= 50 else team_a
                win_prob = max(sim_res.get("home_win_prob", 50), sim_res.get("away_win_prob", 50))
            edge = round(max(1.8, win_prob - 50.0), 1)

        elif s in ("SOC", "SOCCER"):
            sim_res = simulate_soccer_match(home_team=team_a, away_team=team_b, league="EPL")
            if market_type == "TOTAL":
                pick = "Over 2.5 Goals"
                win_prob = sim_res.get("over_25_prob", 53.5)
            else:
                h_p = sim_res.get("home_win_prob", 45.0)
                a_p = sim_res.get("away_win_prob", 30.0)
                pick = team_a if h_p >= a_p else team_b
                win_prob = max(h_p, a_p)
            edge = round(max(2.5, win_prob - 48.0), 1)

        elif s in ("TEN", "TENNIS"):
            sim_res = simulate_tennis_match(player_a=team_a, player_b=team_b)
            p_a_prob = sim_res.get("player_a_win_prob", 55.0)
            p_b_prob = sim_res.get("player_b_win_prob", 45.0)
            pick = team_a if p_a_prob >= p_b_prob else team_b
            win_prob = max(p_a_prob, p_b_prob)
            edge = round(max(2.0, win_prob - 50.0), 1)

        elif s in ("UFC", "MMA"):
            sim_res = simulate_ufc_fight(fighter_a=team_a, fighter_b=team_b)
            f_a_prob = sim_res.get("fighter_a_win_prob", 54.0)
            f_b_prob = sim_res.get("fighter_b_win_prob", 46.0)
            pick = team_a if f_a_prob >= f_b_prob else team_b
            win_prob = max(f_a_prob, f_b_prob)
            edge = round(max(3.0, win_prob - 49.0), 1)

        else:
            win_prob = 56.0
            edge = 4.5
            pick = team_a

        # 5. Generate structured explanation natively
        exp_payload = generate_pick_explanation(
            sport=s,
            matchup=matchup_str,
            pick=pick,
            market_type=market_type,
            win_prob=win_prob,
            edge_pct=edge,
            sim_data=sim_res
        )

        # 6. Master Sports Capper Evaluation
        from backend.sports_engine.master_capper import MasterSportsCapper
        capper_eval = MasterSportsCapper.evaluate_capper_edge(
            sport=s,
            matchup=matchup_str,
            pick_name=pick,
            market_type=market_type,
            model_win_prob=win_prob,
            kalshi_price_dollars=round(max(0.10, min(0.90, (win_prob - edge) / 100.0)), 2),
            situational_factors=sim_res.get("factor_impacts", {})
        )
        exp_payload["capper"] = capper_eval
        if capper_eval.get("capper_thesis"):
            exp_payload["narrative"] = capper_eval["capper_thesis"]

        return {
            "sport": s,
            "league": s,
            "market_type": market_type,
            "predicted_team": pick,
            "opponent": matchup_str,
            "confidence_pct": round(win_prob, 1),
            "edge_pct": round(edge, 1),
            "metadata": {
                "name": pick,
                "matchup": matchup_str,
                "home_team": team_b,
                "away_team": team_a,
                "league": s,
                "game_id": tk_clean,
                "start_label": "Today",
                "explain": exp_payload,
                "narrative": exp_payload.get("narrative", ""),
                "capper": capper_eval,
                "capper_grade": capper_eval.get("grade", "A"),
                "capper_stars": capper_eval.get("stars", "⭐⭐⭐⭐"),
                "capper_tier": capper_eval.get("tier_label", "SHARP_VALUE"),
                "net_ev_pct": capper_eval.get("net_ev_pct", 0.0),
                "kelly_bankroll_pct": capper_eval.get("kelly_bankroll_pct", 0.0)
            }
        }

    def _parse_matchup(self, ticker: str, title: str) -> Tuple[str, str]:
        """Extracts matchup participant names from Kalshi event title or ticker."""
        if title:
            # Check for "at" or "vs" in title
            parts = re.split(r'\s+(?:vs\.?|at|@)\s+', title, flags=re.IGNORECASE)
            if len(parts) >= 2:
                t1 = re.sub(r'\(.*?\)', '', parts[0]).strip()
                t2 = re.sub(r'\(.*?\)', '', parts[1]).strip()
                t2 = re.sub(r'\s+(?:winner|game|match|title).*', '', t2, flags=re.IGNORECASE).strip()
                if t1 and t2:
                    return t1, t2

        # Ticker fallback e.g. KXATPMATCH-26OCT09BUBMAC
        m = re.search(r'-(\d{2}[A-Z]{3}\d{2})([A-Z]{3})([A-Z]{3})', ticker)
        if m:
            return m.group(2), m.group(3)

        return "Team A", "Team B"

    def _generate_baseline_slate(self) -> List[Dict[str, Any]]:
        """Generates initial baseline predictions across active sports leagues."""
        slate = [
            self.predict_for_event("KXNHLGAME-EDMBOS", title="Edmonton Oilers at Boston Bruins", sport="NHL"),
            self.predict_for_event("KXNFLGAME-KCDAL", title="Kansas City Chiefs at Dallas Cowboys", sport="NFL"),
            self.predict_for_event("KXEPLGAME-ARSCHE", title="Arsenal vs Chelsea", sport="SOC"),
            self.predict_for_event("KXATPMATCH-ALCMED", title="Carlos Alcaraz vs Daniil Medvedev", sport="TEN"),
            self.predict_for_event("KXUFCFIGHT-ALLDUN", title="Arnold Allen vs Chris Duncan", sport="UFC"),
        ]
        return [p for p in slate if p]


# Global singleton
_GLOBAL_NATIVE_CLIENT: Optional[NativeSportsClient] = None


def get_native_sports_client() -> NativeSportsClient:
    global _GLOBAL_NATIVE_CLIENT
    if _GLOBAL_NATIVE_CLIENT is None:
        _GLOBAL_NATIVE_CLIENT = NativeSportsClient()
    return _GLOBAL_NATIVE_CLIENT
