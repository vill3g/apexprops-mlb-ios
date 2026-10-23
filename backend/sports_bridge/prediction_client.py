import httpx
import logging
import re
import time
import threading
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

_PICKS_CACHE: Dict[str, tuple] = {}
_PICKS_CACHE_LOCK = threading.Lock()
_PICKS_CACHE_TTL: float = 120.0

_EXPLAIN_CACHE: Dict[str, tuple] = {}
_EXPLAIN_CACHE_LOCK = threading.Lock()

_NARRATIVE_CACHE: Dict[str, tuple] = {}
_NARRATIVE_CACHE_LOCK = threading.Lock()
_NARRATIVE_FETCHING = set()

_SIMULATION_CACHE: Dict[str, dict] = {}
_SIM_CACHE_LOCK = threading.Lock()

def _clean_float(val, default=0.0) -> float:
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().rstrip('%').lstrip('+').strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return default

_CLIENT_REFRESH_IN_PROGRESS = False
_CLIENT_REFRESH_LOCK = threading.Lock()
_LAST_NPB_SUPPLEMENT_TS = 0.0
_LAST_TEN_SUPPLEMENT_TS = 0.0

class SportsPredictionClient:
    def __init__(self, endpoint_url: str = "http://127.0.0.1:8057/api/bot-bridge/predictions", base_url: str = "http://127.0.0.1:8057", use_kalshi_bridge: bool = False):
        self.use_kalshi_bridge = use_kalshi_bridge
        self.endpoint_url = endpoint_url
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=4.0)

    def fetch_latest_picks(self, force_refresh: bool = False) -> List[Dict]:
        global _PICKS_CACHE, _CLIENT_REFRESH_IN_PROGRESS
        now = time.time()
        cache_key = f"{self.base_url}|{self.endpoint_url}"
        with _PICKS_CACHE_LOCK:
            if cache_key in _PICKS_CACHE:
                cache_time, cached_picks = _PICKS_CACHE[cache_key]
                if not force_refresh and (now - cache_time < _PICKS_CACHE_TTL):
                    return list(cached_picks)
                if cached_picks:
                    self._trigger_bg_fetch(cache_key)
                    return list(cached_picks)

        # Fast Path 1: Direct In-Process ApexBridge (memory or disk cache < 2ms)
        try:
            from backend.sports_bridge.apex_bridge import get_sports_predictions
            direct_picks = get_sports_predictions(force_refresh=False, http_fallback_url=self.endpoint_url)
            if direct_picks:
                direct_picks = list(direct_picks)
                for p in direct_picks:
                    meta = p.get("metadata", {})
                    if meta:
                        pt = str(p.get("predicted_team") or "").strip()
                        if " @ " in pt or " vs " in pt.lower():
                            real_t = meta.get("team") or meta.get("ensemble_pick") or meta.get("best_pick_name") or meta.get("pick")
                            if real_t and " @ " not in str(real_t) and " vs " not in str(real_t).lower():
                                p["predicted_team"] = str(real_t).strip()
                                meta["name"] = str(real_t).strip()
                        gt = meta.get("game_time") or meta.get("commence_time")
                        if gt:
                            meta["start_label"] = gt
                        elif meta.get("start_label") and " " in meta.get("start_label", ""):
                            gid = meta.get("game_id", "")
                            m = re.search(r'-(\d{4})(\d{2})(\d{2})-', gid)
                            if m:
                                y, mo, d = m.groups()
                                meta["start_label"] = f"{y}-{mo}-{d} {meta['start_label']}"

                with _PICKS_CACHE_LOCK:
                    _PICKS_CACHE[cache_key] = (now, list(direct_picks))
                # Trigger background supplement check (Tennis / NPB) without blocking foreground
                self._trigger_bg_fetch(cache_key)
                return direct_picks
        except Exception as e:
            logger.debug(f"[SportsPredictionClient] Direct ApexBridge fast path error: {e}")

        # Cold start: trigger background full fetch and return immediately
        self._trigger_bg_fetch(cache_key)
        with _PICKS_CACHE_LOCK:
            if cache_key in _PICKS_CACHE:
                return list(_PICKS_CACHE[cache_key][1])
        return []

    def _trigger_bg_fetch(self, cache_key: str) -> None:
        global _CLIENT_REFRESH_IN_PROGRESS
        with _CLIENT_REFRESH_LOCK:
            if _CLIENT_REFRESH_IN_PROGRESS:
                return
            _CLIENT_REFRESH_IN_PROGRESS = True

        def _bg():
            global _CLIENT_REFRESH_IN_PROGRESS
            try:
                self._fetch_latest_picks_sync(cache_key)
            except Exception as e:
                logger.debug(f"[SportsPredictionClient] Background refresh error: {e}")
            finally:
                with _CLIENT_REFRESH_LOCK:
                    _CLIENT_REFRESH_IN_PROGRESS = False

        threading.Thread(target=_bg, daemon=True, name="SportsPicksBgRefresh").start()

    def _fetch_latest_picks_sync(self, cache_key: str) -> List[Dict]:
        global _PICKS_CACHE, _LAST_NPB_SUPPLEMENT_TS, _LAST_TEN_SUPPLEMENT_TS
        now = time.time()
        try:
            from backend.sports_bridge.apex_bridge import get_sports_predictions
            direct_picks = get_sports_predictions(force_refresh=False, http_fallback_url=self.endpoint_url)
            if direct_picks:
                direct_picks = list(direct_picks)
                for p in direct_picks:
                    meta = p.get("metadata", {})
                    if meta:
                        gt = meta.get("game_time") or meta.get("commence_time")
                        if gt:
                            meta["start_label"] = gt
                        elif meta.get("start_label") and " " in meta.get("start_label", ""):
                            gid = meta.get("game_id", "")
                            m = re.search(r'-(\d{4})(\d{2})(\d{2})-', gid)
                            if m:
                                y, mo, d = m.groups()
                                meta["start_label"] = f"{y}-{mo}-{d} {meta['start_label']}"

                # If Tennis matches are not in direct_picks, supplement from tennis endpoint (at most once per 5 min)
                if not any(p.get("sport") in ("TEN", "TENNIS") for p in direct_picks) and (now - _LAST_TEN_SUPPLEMENT_TS > 300):
                    _LAST_TEN_SUPPLEMENT_TS = now
                    try:
                        r_ten = self.client.get(f"{self.base_url}/api/tennis/matches", timeout=2.0)
                        if r_ten.status_code == 200:
                            for match in r_ten.json().get("matches", []):
                                pa = match.get("player_a", "Unknown")
                                pb = match.get("player_b", "Unknown")
                                ml = match.get("ai_projection") or {}
                                pick_name = ml.get("best_pick_name")
                                if ml and pick_name:
                                    prob_val = ml.get("win_prob_a", 50.0) if pick_name == pa else ml.get("win_prob_b", 50.0)
                                    edge_val = float(ml.get("edge_a", 0.0) if pick_name == pa else ml.get("edge_b", 0.0))
                                    direct_picks.append({
                                        "sport": "TEN",
                                        "league": match.get("league", "TEN"),
                                        "market_type": "MONEYLINE",
                                        "predicted_team": pick_name,
                                        "opponent": f"{pa} vs {pb}",
                                        "confidence_pct": float(prob_val),
                                        "edge_pct": edge_val,
                                        "metadata": {
                                            "name": pick_name,
                                            "matchup": f"{pa} vs {pb}",
                                            "home_team": pa,
                                            "away_team": pb,
                                            "league": match.get("league", "TEN"),
                                            "game_id": match.get("id", match.get("event_id")),
                                            "start_label": match.get("date") or match.get("commence_time") or match.get("start_time", ""),
                                            "date": match.get("date"),
                                            "source": "ApexProps model (fair line)" if match.get("odds_source") == "MODEL_FAIR" else "Sports AI",
                                            "is_final": match.get("is_final", False),
                                            "is_live": match.get("is_live", False),
                                            "lwos_prediction": match.get("lwos_prediction"),
                                            "narrative_alignment": match.get("ml_prediction", {}).get("narrative_alignment")
                                        }
                                    })
                    except Exception as e:
                        logger.debug(f"[SportsPredictionClient] Tennis supplement error: {e}")

                # If NPB/KBO not in direct_picks, supplement from npb_kbo endpoint (at most once per 5 min)
                if not any(p.get("sport") in ("NPB", "KBO", "NPB/KBO") for p in direct_picks) and (now - _LAST_NPB_SUPPLEMENT_TS > 300):
                    _LAST_NPB_SUPPLEMENT_TS = now
                    try:
                        r_nk = self.client.get(f"{self.base_url}/api/npb_kbo/slate", timeout=2.0)
                        if r_nk.status_code == 200:
                            for g in r_nk.json().get("games", []):
                                ml = g.get("ml_prediction") or {}
                                pick_team = ml.get("pick") or g.get("home_team", {}).get("name") or "Unknown"
                                l_str = str(g.get("league", "")).upper()
                                l_tag = "NPB" if "NPB" in l_str else "KBO"
                                h_name = g.get("home_team", {}).get("name", "")
                                a_name = g.get("away_team", {}).get("name", "")
                                wp = float(ml.get("home_win_prob") or ml.get("prob") or g.get("win_prob") or 0.0)
                                edg = float(ml.get("edge_val") or ml.get("edge") or 0.0)
                                direct_picks.append({
                                    "sport": "NPB/KBO",
                                    "league": l_tag,
                                    "market_type": "MONEYLINE",
                                    "predicted_team": pick_team,
                                    "opponent": f"{h_name} vs {a_name}",
                                    "confidence_pct": wp,
                                    "edge_pct": edg,
                                    "metadata": {
                                        "name": pick_team,
                                        "matchup": f"{h_name} vs {a_name}",
                                        "home_team": h_name,
                                        "away_team": a_name,
                                        "league": l_tag,
                                        "game_id": g.get("game_id"),
                                        "win_prob": wp,
                                        "edge": edg,
                                        "start_label": g.get("commence_time") or g.get("start_time") or "Kalshi Event"
                                    }
                                })
                    except Exception as e:
                        logger.debug(f"[SportsPredictionClient] NPB/KBO supplement error: {e}")

                with _PICKS_CACHE_LOCK:
                    _PICKS_CACHE[cache_key] = (time.time(), list(direct_picks))
                return direct_picks
        except Exception as e:
            logger.debug(f"[SportsPredictionClient] Direct ApexBridge fast path error: {e}")

        # Native In-Process Sports Engine (Fallback only if ApexBridge returns no picks)
        try:
            from backend.sports_engine import get_native_sports_client
            native_picks = get_native_sports_client().fetch_latest_picks(force_refresh=False)
            if native_picks:
                with _PICKS_CACHE_LOCK:
                    _PICKS_CACHE[cache_key] = (time.time(), list(native_picks))
                return native_picks
        except Exception as e:
            logger.debug(f"[SportsPredictionClient] Native sports engine error: {e}")


        all_picks: List[Dict] = []
        # 1. Fetch from main bot-bridge predictions (covers NFL, MLB, NHL, TENNIS, etc.)
        try:
            response = self.client.get(self.endpoint_url)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    picks = data.get("predictions", [])
                    for p in picks:
                        meta = p.get("metadata", {})
                        if meta:
                            gt = meta.get("game_time") or meta.get("commence_time")
                            if gt:
                                meta["start_label"] = gt
                                gid = meta.get("game_id", "")
                                m = re.search(r'-(\d{4})(\d{2})(\d{2})-', gid)
                                if m:
                                    y, mo, d = m.groups()
                                    meta["start_label"] = f"{y}-{mo}-{d} {meta['start_label']}"
                    all_picks.extend(picks)
        except Exception as e:
            logger.warning(f"Failed to fetch sports predictions from bot-bridge: {e}")

        
        # Fetch MLB, NFL, NHL games
        for sport_key, path in [("MLB", "/api/mlb/games"), ("NFL", "/api/nfl/games"), ("NHL", "/api/hockey/slate")]:
            try:
                r = self.client.get(f"{self.base_url}{path}")
                if r.status_code == 200:
                    data = r.json()
                    games_list = data.get("games", []) or data.get("matches", [])
                    for g in games_list:
                        ml = g.get("ml_prediction") or g.get("moneyline") or {}
                        home_team = g.get("home_team", {}).get("name", "Unknown") if isinstance(g.get("home_team"), dict) else str(g.get("home_team", "Unknown"))
                        away_team = g.get("away_team", {}).get("name", "Unknown") if isinstance(g.get("away_team"), dict) else str(g.get("away_team", "Unknown"))
                        pick = ml.get("best_pick_name") or ml.get("pick")
                        if ml and pick:
                            prob = _clean_float(ml.get("home_win_prob") if pick == home_team else ml.get("away_win_prob") or ml.get("prob"), 50.0)
                            edge = _clean_float(ml.get("edge_val"), 0.0)
                            all_picks.append({
                                "sport": sport_key,
                                "league": sport_key,
                                "market_type": "MONEYLINE",
                                "predicted_team": pick,
                                "opponent": f"{away_team} at {home_team}",
                                "confidence_pct": prob,
                                "edge_pct": edge,
                                "metadata": {
                                    "name": pick,
                                    "matchup": f"{away_team} at {home_team}",
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "league": sport_key,
                                    "game_id": g.get("game_id") or g.get("id"),
                                    "start_label": g.get("commence_time") or g.get("start_time") or g.get("game_time"),
                                    "tactical_intel": g.get("tactical_intel"),
                                    "editorial_consensus": g.get("editorial_consensus"),
                                    "editorial_source": g.get("editorial_source"),
                                    "confirmed_goalie": g.get("home_goalie") if pick == home_team else g.get("away_goalie")
                                }
                            })
                        
                        tot = g.get("total_prediction") or g.get("total_runs") or g.get("totals") or {}
                        if tot and tot.get("pick"):
                            pick = tot.get("pick")
                            prob = _clean_float(tot.get("prob"), 50.0)
                            edge = _clean_float(tot.get("edge_val"), 0.0)
                            all_picks.append({
                                "sport": sport_key,
                                "league": sport_key,
                                "market_type": "TOTAL",
                                "predicted_team": pick,
                                "opponent": f"{away_team} at {home_team}",
                                "confidence_pct": prob,
                                "edge_pct": edge,
                                "metadata": {
                                    "name": pick,
                                    "matchup": f"{away_team} at {home_team}",
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "league": sport_key,
                                    "game_id": g.get("game_id") or g.get("id"),
                                    "start_label": g.get("commence_time") or g.get("start_time") or g.get("game_time"),
                                    "tactical_intel": g.get("tactical_intel"),
                                    "editorial_consensus": g.get("editorial_consensus"),
                                    "editorial_source": g.get("editorial_source")
                                }
                            })
            except Exception as e:
                logger.debug(f"Failed to fetch {sport_key} games: {e}")

        # Fetch MLB, NFL, NHL, NBA, UFC top_picks
        for sport_key, path in [("MLB", "/api/picks/top5"), ("NFL", "/api/nfl/top_picks"), ("NHL", "/api/hockey/top_picks"), ("NBA", "/api/nba/top_picks"), ("UFC", "/api/ufc/top_picks"), ("SOC", "/api/soccer/top_picks")]:
            try:
                r = self.client.get(f"{self.base_url}{path}")
                if r.status_code == 200:
                    data = r.json()
                    picks = data.get("top_picks", []) or data.get("top_6", []) or data.get("props", []) or []
                    for p in picks:
                        if not isinstance(p, dict): continue
                        
                        matchup = p.get("matchup") or p.get("opponent") or ""
                        name = p.get("name") or p.get("predicted_team") or p.get("player_or_team") or p.get("pick") or ""
                        if not name or name in (p.get("type"), p.get("stat_name")):
                            name = matchup or name
                            
                        conf = _clean_float(p.get("prob") or p.get("cover_prob") or p.get("win_prob") or p.get("confidence") or p.get("confidence_pct"), 50.0)
                        if 0 < conf <= 1.0:
                            conf *= 100.0
                        edge = _clean_float(p.get("edge") or p.get("edge_percent") or p.get("edge_pct") or p.get("edge_val"), 0.0)
                        
                        market_type = p.get("type") or p.get("stat_name") or p.get("market_type")
                        p_name_l = str(name).lower()
                        if any(w in p_name_l for w in ("over ", "under ", "inside distance", "round total")):
                            market_type = "TOTAL"
                        elif not market_type and p.get("player_id"):
                            market_type = "Player Prop"
                        elif not market_type:
                            market_type = "MONEYLINE"
                            
                        all_picks.append({
                            "sport": sport_key,
                            "league": p.get("league") or sport_key,
                            "market_type": market_type,
                            "predicted_team": name,
                            "opponent": matchup,
                            "confidence_pct": round(conf, 1),
                            "edge_pct": round(edge, 1),
                            "metadata": dict(p)
                        })
            except Exception as e:
                logger.debug(f"Failed to fetch {sport_key} top picks: {e}")

        # 2. Fetch NPB and KBO slate games from local AI engine
        try:
            r = self.client.get(f"{self.base_url}/api/npb_kbo/slate")
            if r.status_code == 200:
                slate_data = r.json()
                for g in slate_data.get("games", []):
                    ml = g.get("ml_prediction") or {}
                    pick_team = ml.get("pick") or g.get("home_team", {}).get("name") or "Unknown"
                    league_str = str(g.get("league", "")).upper()
                    league = "NPB" if "NPB" in league_str else "KBO"
                    home_name = g.get("home_team", {}).get("name", "")
                    away_name = g.get("away_team", {}).get("name", "")
                    win_prob = float(ml.get("home_win_prob") or ml.get("prob") or g.get("win_prob") or 0.0)
                    edge = float(ml.get("edge_val") or ml.get("edge") or 0.0)

                    all_picks.append({
                        "sport": "NPB/KBO",
                        "league": league,
                        "market_type": "MONEYLINE",
                        "predicted_team": pick_team,
                        "opponent": f"{home_name} vs {away_name}",
                        "confidence_pct": win_prob,
                        "edge_pct": edge,
                        "metadata": {
                            "name": pick_team,
                            "matchup": f"{home_name} vs {away_name}",
                            "home_team": home_name,
                            "away_team": away_name,
                            "league": league,
                            "league_label": league,
                            "game_id": g.get("game_id"),
                            "win_prob": win_prob,
                            "edge": edge,
                            "start_label": g.get("commence_time") or g.get("start_time") or "Kalshi Event",
                            "is_upcoming": True
                        }
                    })
        except Exception as e:
            logger.warning(f"Failed to fetch NPB/KBO slate predictions: {e}")

        # 3. Check /api/international/npb and /api/international/kbo if slate had no items
        if not any(p.get("sport") == "NPB/KBO" for p in all_picks):
            for path, league in [("/api/international/npb", "NPB"), ("/api/international/kbo", "KBO")]:
                try:
                    r = self.client.get(f"{self.base_url}{path}")
                    if r.status_code == 200:
                        intl_data = r.json()
                        for g in intl_data.get("games", []):
                            ml = g.get("ml_prediction") or {}
                            pick_team = ml.get("pick") or g.get("home_team", {}).get("name") or "Unknown"
                            home_name = g.get("home_team", {}).get("name", "")
                            away_name = g.get("away_team", {}).get("name", "")
                            all_picks.append({
                                "sport": "NPB/KBO",
                                "league": league,
                                "market_type": "MONEYLINE",
                                "predicted_team": pick_team,
                                "opponent": f"{home_name} vs {away_name}",
                                "confidence_pct": float(ml.get("home_win_prob") or 62.0),
                                "edge_pct": float(ml.get("edge_val") or 8.5),
                                "metadata": {
                                    "name": pick_team,
                                    "matchup": f"{home_name} vs {away_name}",
                                    "league": league,
                                    "game_id": g.get("game_id")
                                }
                            })
                except Exception as e:
                    logger.debug(f"Failed to fetch {path}: {e}")

        # 4. Fetch Soccer slate
        if True:
            try:
                r = self.client.get(f"{self.base_url}/api/soccer/slate")
                if r.status_code == 200:
                    soccer_data = r.json()
                    for g in soccer_data.get("matches", []) or soccer_data.get("games", []):
                        home_team = g.get("home_team", {}).get("name", "Unknown")
                        away_team = g.get("away_team", {}).get("name", "Unknown")
                        matchup = f"{home_team} vs {away_team}"
                        
                        ml = g.get("ml_prediction") or g.get("moneyline") or {}
                        pick = ml.get("best_pick_name") or ml.get("pick")
                        if ml and pick:
                            if pick == home_team:
                                prob = ml.get("home_win_prob", 50.0)
                            elif pick == away_team:
                                prob = ml.get("away_win_prob", 50.0)
                            else:
                                prob = ml.get("draw_prob", 50.0)
                                pick = "Draw"
                                
                            all_picks.append({
                                "sport": "SOC",
                                "league": g.get("league", "SOC"),
                                "market_type": "MONEYLINE",
                                "predicted_team": pick,
                                "opponent": matchup,
                                "confidence_pct": float(prob),
                                "edge_pct": float(ml.get("edge_val", 0.0)),
                                "metadata": {
                                    "name": pick,
                                    "matchup": matchup,
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "league": g.get("league", "SOC"),
                                    "game_id": g.get("id"),
                                    "start_label": g.get("commence_time") or g.get("start_time"),
                                    "home_win_prob": float(ml.get("home_win_prob", 0.0)),
                                    "away_win_prob": float(ml.get("away_win_prob", 0.0)),
                                    "draw_prob": float(ml.get("draw_prob", 0.0)),
                                    "tactical_intel": g.get("tactical_intel"),
                                    "editorial_consensus": g.get("editorial_consensus"),
                                    "editorial_source": g.get("editorial_source")
                                }
                            })
                            
                            if pick != "Draw" and ml.get("draw_prob"):
                                all_picks.append({
                                    "sport": "SOC",
                                    "league": g.get("league", "SOC"),
                                    "market_type": "DRAW",
                                    "predicted_team": "Draw",
                                    "opponent": matchup,
                                    "confidence_pct": float(ml.get("draw_prob", 33.3)),
                                    "edge_pct": 0.0,
                                    "metadata": {
                                        "name": "Draw",
                                        "matchup": matchup,
                                        "home_team": home_team,
                                        "away_team": away_team,
                                        "league": g.get("league", "SOC"),
                                        "game_id": g.get("id"),
                                        "start_label": g.get("commence_time") or g.get("start_time"),
                                        "tactical_intel": g.get("tactical_intel"),
                                        "editorial_consensus": g.get("editorial_consensus"),
                                        "editorial_source": g.get("editorial_source")
                                    }
                                })

                        tot = g.get("total_prediction") or g.get("goals_prediction") or g.get("totals") or {}
                        if tot and tot.get("pick"):
                            pick = tot.get("pick")
                            all_picks.append({
                                "sport": "SOC",
                                "league": g.get("league", "SOC"),
                                "market_type": "TOTAL",
                                "predicted_team": pick,
                                "opponent": matchup,
                                "confidence_pct": float(tot.get("prob", 50.0)),
                                "edge_pct": float(tot.get("edge_val", 0.0)),
                                "metadata": {
                                    "name": pick,
                                    "matchup": matchup,
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "league": g.get("league", "SOC"),
                                    "game_id": g.get("id"),
                                    "start_label": g.get("commence_time") or g.get("start_time"),
                                    "home_win_prob": float(ml.get("home_win_prob", 0.0)),
                                    "away_win_prob": float(ml.get("away_win_prob", 0.0)),
                                    "draw_prob": float(ml.get("draw_prob", 0.0))
                                }
                            })
            except Exception as e:
                logger.debug(f"Failed to fetch soccer slate: {e}")
        
        # 5. Fetch UFC slate
        if True:
            try:
                r = self.client.get(f"{self.base_url}/api/ufc/slate")
                if r.status_code == 200:
                    ufc_data = r.json()
                    for f_match in ufc_data.get("fights", []):
                        home_team = f_match.get("fighter_a", {}).get("name") or f_match.get("f1", {}).get("name") or f_match.get("home_team", {}).get("name", "Unknown")
                        away_team = f_match.get("fighter_b", {}).get("name") or f_match.get("f2", {}).get("name") or f_match.get("away_team", {}).get("name", "Unknown")
                        matchup = f"{home_team} vs {away_team}"
                        
                        ml = f_match.get("moneyline") or f_match.get("ml_prediction") or {}
                        pick = ml.get("best_pick_name") or ml.get("pick")
                        if ml and pick:
                            if pick == home_team:
                                prob = ml.get("prob_a") or ml.get("win_prob") or ml.get("prob", 50.0)
                            else:
                                prob = ml.get("prob_b") or ml.get("win_prob") or ml.get("prob", 50.0)
                                
                            all_picks.append({
                                "sport": "UFC",
                                "league": f_match.get("league", "UFC"),
                                "market_type": "MONEYLINE",
                                "predicted_team": pick,
                                "opponent": matchup,
                                "confidence_pct": float(prob),
                                "edge_pct": float(ml.get("edge_val", 0.0)),
                                "metadata": {
                                    "name": pick,
                                    "matchup": matchup,
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "league": f_match.get("league", "UFC"),
                                    "game_id": f_match.get("id", f_match.get("event_id")),
                                    "start_label": "",
                                    "prob_a": float(ml.get("prob_a", 0.0)),
                                    "prob_b": float(ml.get("prob_b", 0.0))
                                }
                            })

                        tot = f_match.get("total_prediction") or f_match.get("totals") or {}
                        if tot and tot.get("pick"):
                            pick = tot.get("pick")
                            all_picks.append({
                                "sport": "UFC",
                                "league": f_match.get("league", "UFC"),
                                "market_type": "TOTAL",
                                "predicted_team": pick,
                                "opponent": matchup,
                                "confidence_pct": float(tot.get("prob", 50.0)),
                                "edge_pct": float(tot.get("edge_val", 0.0)),
                                "metadata": {
                                    "name": pick,
                                    "matchup": matchup,
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "league": f_match.get("league", "UFC"),
                                    "game_id": f_match.get("id", f_match.get("event_id")),
                                    "start_label": "",
                                    "prob_a": float(ml.get("prob_a", 0.0)),
                                    "prob_b": float(ml.get("prob_b", 0.0))
                                }
                            })
            except Exception as e:
                logger.debug(f"Failed to fetch ufc slate: {e}")
        
        # 6. Fetch Tennis matches
        if True:
            try:
                r = self.client.get(f"{self.base_url}/api/tennis/matches")
                if r.status_code == 200:
                    tennis_data = r.json()
                    for match in tennis_data.get("matches", []):
                        home_team = match.get("player_a", "Unknown")
                        away_team = match.get("player_b", "Unknown")
                        matchup = f"{home_team} vs {away_team}"
                        
                        ml = match.get("ai_projection") or {}
                        if ml and ml.get("best_pick_name"):
                            pick = ml.get("best_pick_name")
                            if pick == home_team:
                                prob = ml.get("win_prob_a", 50.0)
                            else:
                                prob = ml.get("win_prob_b", 50.0)
                                
                            edge_val = float(ml.get("edge_a", 0.0) if pick == home_team else ml.get("edge_b", 0.0))
                            is_sportsbook = False
                            
                            all_picks.append({
                                "sport": "TEN",
                                "league": match.get("league", "TEN"),
                                "market_type": "MONEYLINE",
                                "predicted_team": pick,
                                "opponent": matchup,
                                "confidence_pct": float(prob),
                                "edge_pct": edge_val,
                                "metadata": {
                                    "name": pick,
                                    "matchup": matchup,
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "league": match.get("league", "TEN"),
                                    "game_id": match.get("id", match.get("event_id")),
                                    "start_label": match.get("date") or match.get("commence_time") or match.get("start_time", ""),
                                    "source": "ApexProps model (fair line)" if match.get("odds_source") == "MODEL_FAIR" else ("Sportsbook consensus" if is_sportsbook else "Sports AI"),
                                      "is_final": match.get("is_final", False),
                                      "is_live": match.get("is_live", False),
                                      "start_epoch": match.get("date"),
                                      "pick_is_prematch": True if match.get("is_live") else False
                                }
                            })
            except Exception as e:
                logger.debug(f"Failed to fetch tennis matches: {e}")
        
        if all_picks:
            with _PICKS_CACHE_LOCK:
                _PICKS_CACHE[cache_key] = (now, list(all_picks))
            return all_picks
        else:
            with _PICKS_CACHE_LOCK:
                if cache_key in _PICKS_CACHE:
                    return list(_PICKS_CACHE[cache_key][1])
            return []

    def predict_for_event(self, event_ticker: str, title: str = "", sport: str = "") -> Optional[Dict]:
        """Matches or simulates an on-demand AI prediction for an active Kalshi event."""
        if not event_ticker or not str(event_ticker).strip():
            return None


        event_ticker_clean = event_ticker.strip().lower()
        title_clean = (title or "").strip().lower()
        search_text = f"{event_ticker_clean} {title_clean}"

        is_kbo_event = "kbo" in event_ticker_clean or "kbo" in title_clean
        is_npb_event = "npb" in event_ticker_clean or "npb" in title_clean

        # Infer sport if not provided
        inferred_sport = (sport or "").upper()
        if not inferred_sport:
            if "npb" in event_ticker_clean or "kbo" in event_ticker_clean:
                inferred_sport = "NPB/KBO"
            elif "nfl" in event_ticker_clean:
                inferred_sport = "NFL"
            elif "mlb" in event_ticker_clean:
                inferred_sport = "MLB"
            elif "nhl" in event_ticker_clean:
                inferred_sport = "NHL"
            elif any(k in event_ticker_clean for k in ["epl", "mls", "uefa", "soc"]):
                inferred_sport = "SOC"
            elif "ufc" in event_ticker_clean:
                inferred_sport = "UFC"
            elif any(k in event_ticker_clean for k in ["atp", "wta", "ten"]):
                inferred_sport = "TEN"

        # Extract date from Kalshi ticker e.g. KXATPMATCH-26OCT09BUBMAC
        event_date_str = None
        ticker_player_tokens = []
        m_date = re.search(r'-(\d{2})([A-Z]{3})(\d{2})([A-Z]*)', event_ticker_clean.upper())
        if m_date:
            y, mo_str, d, players_str = m_date.groups()
            mo_map = {"JAN":1,"FEB":2,"MAR":3,"APR":4,"MAY":5,"JUN":6,"JUL":7,"AUG":8,"SEP":9,"OCT":10,"NOV":11,"DEC":12}
            mo = mo_map.get(mo_str, 1)
            event_date_str = f"20{y}-{mo:02d}-{int(d):02d}"
            
            if players_str and len(players_str) >= 6:
                ticker_player_tokens.append(players_str[:3].lower())
                ticker_player_tokens.append(players_str[3:6].lower())

        search_tokens = set(re.findall(r'[a-z0-9]+', search_text))
        generic_words = {'the', 'and', 'city', 'team', 'club', 'fc', 'vs', 'game'}

        event_parts = [p.strip() for p in re.split(r'\s+(?:vs\.?|at|@)\s+', title_clean, flags=re.IGNORECASE) if p.strip()]

        # 1. Search in latest picks
        picks = self.fetch_latest_picks()
        best_match = None
        best_score = 0

        if hasattr(self, "_match_kalshi_event_to_predictions"):
            best_match = self._match_kalshi_event_to_predictions(event_ticker, title, picks)
            best_score = 100 if best_match else 0

        for pick in (picks if best_match is None else []):
            pick_sport = (pick.get("sport") or "").upper()
            # Enforce sport compatibility
            if inferred_sport:
                if inferred_sport == "NPB/KBO" and pick_sport not in ("NPB/KBO", "NPB", "KBO", "BASEBALL"):
                    continue
                elif inferred_sport == "NFL" and pick_sport not in ("NFL", "FOOTBALL"):
                    continue
                elif inferred_sport == "MLB" and pick_sport not in ("MLB", "BASEBALL"):
                    continue
                elif inferred_sport == "NHL" and pick_sport not in ("NHL", "HOCKEY"):
                    continue
                elif inferred_sport in ("SOC", "SOCCER") and pick_sport not in ("SOC", "SOCCER", "EPL", "MLS", "UEFA"):
                    continue
                elif inferred_sport in ("UFC", "MMA") and pick_sport not in ("UFC", "MMA"):
                    continue
                elif inferred_sport in ("TEN", "TENNIS") and pick_sport not in ("TEN", "TENNIS", "ATP", "WTA"):
                    continue

            team = (pick.get("predicted_team") or "").lower().strip()
            matchup = (pick.get("opponent") or pick.get("metadata", {}).get("matchup") or "").lower().strip()
            pick_league = (pick.get("league") or pick.get("metadata", {}).get("league") or "").upper()
            
            md = pick.get("metadata", {})
            home_team_md = md.get("home_team")
            home_abbr = home_team_md.get("abbr") if isinstance(home_team_md, dict) else ""
            away_team_md = md.get("away_team")
            away_abbr = away_team_md.get("abbr") if isinstance(away_team_md, dict) else ""
            team_abbr = (md.get("team") or home_abbr or "").lower().strip()
            opp_abbr = (md.get("opponent") or away_abbr or "").lower().strip()

            pred_tokens = {w for w in re.findall(r'[a-z0-9]+', team) if len(w) >= 3 and w not in generic_words}
            if team_abbr and len(team_abbr) >= 2:
                pred_tokens.add(team_abbr)
                
            # Date matching for Tennis (+/- 1 day)
            if event_date_str and pick_sport in ("TEN", "TENNIS", "ATP", "WTA"):
                start_label = str(md.get("start_label") or "")
                m_pick_date = re.search(r'(\d{4})-(\d{2})-(\d{2})', start_label)
                if m_pick_date:
                    pick_date_str = f"{m_pick_date.group(1)}-{m_pick_date.group(2)}-{m_pick_date.group(3)}"
                    from datetime import datetime
                    try:
                        ed = datetime.strptime(event_date_str, "%Y-%m-%d")
                        pd = datetime.strptime(pick_date_str, "%Y-%m-%d")
                        if abs((ed - pd).days) > 2:
                            continue
                    except:
                        pass
                tennis_abbr_match = False
                if ticker_player_tokens:
                    p1 = ticker_player_tokens[0]
                    p2 = ticker_player_tokens[1]
                    h_team = str(md.get("home_team", "")).lower()
                    a_team = str(md.get("away_team", "")).lower()
                    if not h_team and not a_team:
                        m_str = matchup.lower()
                        parts = m_str.split(" vs ")
                        if len(parts) == 2:
                            h_team = parts[0]
                            a_team = parts[1]
                        
                    def matches_abbr(abbr, full_name):
                        parts = full_name.split()
                        if any(part.startswith(abbr) for part in parts): return True
                        if len(parts) >= 2 and "".join(parts[1:]).startswith(abbr): return True
                        if len(parts) >= 3 and "".join(parts[2:]).startswith(abbr): return True
                        return full_name.replace(" ", "").startswith(abbr)
                        
                    match1 = matches_abbr(p1, h_team) or matches_abbr(p1, a_team)
                    match2 = matches_abbr(p2, h_team) or matches_abbr(p2, a_team)
                    
                    if match1 and match2:
                        search_tokens.update([p1, p2])
                        pred_tokens.update([p1, p2])
                        tennis_abbr_match = True
            
            # Additional logic: if team contains a slash like nyi/chi, split and add them
            if "/" in team:
                for p_part in team.split("/"):
                    if len(p_part.strip()) >= 2:
                        pred_tokens.add(p_part.strip())

            # Verification: If event specifies 2 teams (Team A vs Team B)
            if len(event_parts) == 2:
                e1_tokens = {w for w in re.findall(r'[a-z0-9]+', event_parts[0]) if len(w) >= 2 and w not in generic_words}
                e2_tokens = {w for w in re.findall(r'[a-z0-9]+', event_parts[1]) if len(w) >= 2 and w not in generic_words}
                
                # Check if matchup strings match directly
                pick_parts = [p.strip() for p in re.split(r'\s+(?:vs\.?|at|@)\s+', matchup, flags=re.IGNORECASE) if p.strip()]
                
                matches_matchup = False
                if len(pick_parts) == 2:
                    p1_tokens = {w for w in re.findall(r'[a-z0-9]+', pick_parts[0]) if len(w) >= 2 and w not in generic_words}
                    p2_tokens = {w for w in re.findall(r'[a-z0-9]+', pick_parts[1]) if len(w) >= 2 and w not in generic_words}
                    
                    direct = (bool(p1_tokens & e1_tokens) or pick_parts[0] in event_parts[0] or event_parts[0] in pick_parts[0]) and \
                             (bool(p2_tokens & e2_tokens) or pick_parts[1] in event_parts[1] or event_parts[1] in pick_parts[1])
                    cross = (bool(p1_tokens & e2_tokens) or pick_parts[0] in event_parts[1] or event_parts[1] in pick_parts[0]) and \
                            (bool(p2_tokens & e1_tokens) or pick_parts[1] in event_parts[0] or event_parts[0] in pick_parts[1])
                    if direct or cross:
                        matches_matchup = True
                
                matches_e1 = bool(pred_tokens & e1_tokens) or (team and (team in event_parts[0] or event_parts[0] in team))
                matches_e2 = bool(pred_tokens & e2_tokens) or (team and (team in event_parts[1] or event_parts[1] in team))
                
                p_mtype_check = str(pick.get("market_type") or "").upper()
                is_non_team_pick = any(k in p_mtype_check for k in ("TOTAL", "OVER", "UNDER", "PROP", "PLAYER")) or any(team.startswith(k) for k in ("over", "under", "inside distance"))
                if not (matches_e1 or matches_e2):
                    if not (matches_matchup and is_non_team_pick) and not locals().get("tennis_abbr_match", False):
                        continue

            else:
                # Non-head-to-head event: pred_team tokens must match search_tokens
                if not (pred_tokens & search_tokens) and (team not in search_text):
                    if not locals().get("tennis_abbr_match", False):
                        continue

            # Compute match score
            words = [w for w in re.findall(r'[a-z0-9]+', f"{team} {matchup}") if len(w) >= 3 and w not in generic_words]
            base_score = sum(1 for w in words if w in search_tokens)
            if team and len(team) >= 4 and team in search_text:
                base_score += 5

            score = base_score
            if locals().get("tennis_abbr_match", False):
                score += 15
            if is_kbo_event and pick_league == "KBO":
                score += 8
            elif is_npb_event and pick_league == "NPB":
                score += 8
            elif (is_kbo_event and pick_league == "NPB") or (is_npb_event and pick_league == "KBO"):
                score = max(0, score - 5)

            p_mtype = str(pick.get("market_type") or "").upper()
            
            # --- STRICT MARKET TYPE MATCHING ---
            is_total_ev = "total" in event_ticker_clean or "total" in title_clean
            is_spread_ev = "spread" in event_ticker_clean or "spread" in title_clean
            is_prop_ev = any(x in event_ticker_clean for x in ["td", "rec", "pass", "rush", "hrr", "hit", "hr", "ks", "tb", "rbi", "goal", "shot"])
            
            is_total_pick = "TOTAL" in p_mtype or "OVER" in p_mtype or "UNDER" in p_mtype or "O/U" in p_mtype
            is_spread_pick = "SPREAD" in p_mtype or "RUN LINE" in p_mtype or "PUCK LINE" in p_mtype
            is_prop_pick = "PROP" in p_mtype or "PLAYER" in p_mtype
            
            if is_total_ev and not is_total_pick:
                continue
            if is_spread_ev and not is_spread_pick:
                continue
            if is_prop_ev and not is_prop_pick:
                continue
            
            if not is_total_ev and not is_spread_ev and not is_prop_ev:
                if is_total_pick or is_spread_pick or is_prop_pick:
                    continue

            if any(k in event_ticker_clean for k in ["game", "match", "title"]):
                if "MONEYLINE" in p_mtype or "WINNER" in p_mtype or p_mtype == "":
                    score += 12
                if "/" in team:
                    score = max(0, score - 10)

            if score > best_score:
                best_score = score
                best_match = pick

        if best_match and best_score >= 1:
            try:
                import copy
                best_match = copy.deepcopy(best_match)
                sport_path = inferred_sport.lower()
                if sport_path == "soc": sport_path = "soccer"
                elif sport_path == "ten": sport_path = "tennis"
                elif sport_path == "nhl": sport_path = "hockey"
                elif sport_path == "npb/kbo": sport_path = "npb_kbo"
                
                ep = "games" if sport_path == "mlb" else "slate"
                
                game_pk = best_match.get("metadata", {}).get("game_id") or best_match.get("game_id")
                if not game_pk:
                    r_games = self.client.get(f"{self.base_url}/api/{sport_path}/{ep}", timeout=2.0)
                    if r_games.status_code == 200:
                        data = r_games.json()
                        games = data.get("games") or data.get("matches") or data.get("fights") or data.get("slate") or []
                        matchup = (best_match.get("opponent") or best_match.get("metadata", {}).get("matchup") or "").lower()
                        parts = [p.strip() for p in re.split(r'\s+(?:vs\.?|at|@)\s+', matchup, flags=re.IGNORECASE) if p.strip()]
                        for g in games:
                            # Extract home/away from different structures
                            g_home = (g.get("home_team", {}).get("name") if isinstance(g.get("home_team"), dict) else g.get("home_team", "")) or ""
                            g_away = (g.get("away_team", {}).get("name") if isinstance(g.get("away_team"), dict) else g.get("away_team", "")) or ""
                            if not g_home and g.get("fighter_a"):
                                g_home = g.get("fighter_a", {}).get("name", "") if isinstance(g.get("fighter_a"), dict) else g.get("fighter_a", "")
                                g_away = g.get("fighter_b", {}).get("name", "") if isinstance(g.get("fighter_b"), dict) else g.get("fighter_b", "")
                                
                            g_home = g_home.lower()
                            g_away = g_away.lower()

                            if len(parts) == 2:
                                if (parts[0] in g_home or g_home in parts[0] or parts[0] in g_away or g_away in parts[0]) and \
                                   (parts[1] in g_home or g_home in parts[1] or parts[1] in g_away or g_away in parts[1]):
                                    game_pk = g.get("game_id") or g.get("id")
                                    break
                            else:
                                if matchup and (matchup in g_home or matchup in g_away):
                                    game_pk = g.get("game_id") or g.get("id")
                                    break

                if game_pk:
                    global _EXPLAIN_CACHE
                    now_t = time.time()
                    exp_json = None
                    mtype = str(best_match.get("market_type") or "").upper()
                    
                    market_query = "moneyline"
                    if "SPREAD" in mtype or "RUN LINE" in mtype or "PUCK LINE" in mtype:
                        market_query = "spread"
                    elif "TOTAL" in mtype or "OVER" in mtype or "UNDER" in mtype:
                        market_query = "total"
                    elif "PERIOD" in mtype or "FIRST-5" in mtype:
                        market_query = "period"
                    elif "PROP" in mtype or best_match.get("stat_name"):
                        market_query = "prop"
                        
                    raw_line = best_match.get("line") or best_match.get("metadata", {}).get("line") or ""
                    # Strip text to get just the number
                    m = re.search(r'[+-]?\d+(?:\.\d+)?', str(raw_line))
                    line_val = m.group(0) if m else ""
                    
                    side_val = best_match.get("predicted_team", "")
                    # Send over/under or yes/no as side if applicable
                    lower_side = side_val.lower()
                    if "over" in lower_side or "over" in str(raw_line).lower():
                        side_val = "over"
                    elif "under" in lower_side or "under" in str(raw_line).lower():
                        side_val = "under"
                    elif "yes" in lower_side:
                        side_val = "yes"
                    elif "no" in lower_side:
                        side_val = "no"
                    
                    cache_key = f"{sport_path}_{game_pk}_{market_query}_{line_val}_{side_val.lower()}"
                    
                    with _EXPLAIN_CACHE_LOCK:
                        if cache_key in _EXPLAIN_CACHE and now_t - _EXPLAIN_CACHE[cache_key][0] < 600:
                            exp_json = _EXPLAIN_CACHE[cache_key][1]
                        elif f"{sport_path}_{game_pk}_{market_query}_{line_val}_{side_val}" in _EXPLAIN_CACHE and now_t - _EXPLAIN_CACHE[f"{sport_path}_{game_pk}_{market_query}_{line_val}_{side_val}"][0] < 600:
                            exp_json = _EXPLAIN_CACHE[f"{sport_path}_{game_pk}_{market_query}_{line_val}_{side_val}"][1]

                    if not exp_json:
                        url = f"{self.base_url}/api/{sport_path}/explain/{game_pk}?market={market_query}&line={line_val}&side={side_val}"
                        try:
                            r_exp = self.client.get(url, timeout=2.0)
                            if r_exp.status_code == 200:
                                res_json = r_exp.json()
                                if "error" not in res_json:
                                    exp_json = res_json
                                    with _EXPLAIN_CACHE_LOCK:
                                        _EXPLAIN_CACHE[cache_key] = (now_t, exp_json)
                                else:
                                    logger.warning(f"Explain returned error field: {res_json}")
                            else:
                                logger.warning(f"Explain failed HTTP {r_exp.status_code} for {url}")
                        except Exception as e:
                            logger.warning(f"Explain request failed: {e}")
                            
                    if exp_json and "error" not in exp_json:
                        # Verify exact market and line match
                        exp_market = exp_json.get("market", "")
                        exp_line_str = str(exp_json.get("line", ""))
                        exp_m = re.search(r'[+-]?\d+(?:\.\d+)?', exp_line_str)
                        exp_line_val = exp_m.group(0) if exp_m else ""
                        
                        if exp_market != market_query or (line_val and exp_line_val and line_val != exp_line_val):
                            logger.warning(f"Explain mismatch: expected {market_query} {line_val}, got {exp_market} {exp_line_val}")
                        else:
                            if "metadata" not in best_match:
                                best_match["metadata"] = {}
                                
                            best_match["metadata"]["explain"] = copy.deepcopy(exp_json)
                            
                            # Attach narrative from cache or fetch asynchronously
                            n_cache_key = f"{sport_path}_{game_pk}_{market_query}_{line_val}_{side_val}"
                            global _NARRATIVE_CACHE, _NARRATIVE_FETCHING
                            now_t = time.time()
                            narr = None
                            
                            with _NARRATIVE_CACHE_LOCK:
                                if n_cache_key in _NARRATIVE_CACHE and now_t - _NARRATIVE_CACHE[n_cache_key][0] < 1800:
                                    narr = _NARRATIVE_CACHE[n_cache_key][1]
                            
                            if narr:
                                best_match["metadata"]["explain"]["narrative"] = narr
                            else:
                                def _fetch_narrative_bg(n_key, s_path, g_pk, m_query, l_val, s_val):
                                    try:
                                        narr_url = f"{self.base_url}/api/{s_path}/explain/{g_pk}/narrative?market={m_query}&line={l_val}&side={s_val}"
                                        import httpx
                                        # Using a longer timeout locally
                                        with httpx.Client(timeout=25.0) as fetch_client:
                                            r_narr = fetch_client.get(narr_url)
                                            if r_narr.status_code == 200:
                                                narr_data = r_narr.json()
                                                if narr_data.get("narrative"):
                                                    with _NARRATIVE_CACHE_LOCK:
                                                        _NARRATIVE_CACHE[n_key] = (time.time(), narr_data["narrative"])
                                    except Exception as e:
                                        logger.warning(f"Narrative error: {e}")
                                    finally:
                                        with _NARRATIVE_CACHE_LOCK:
                                            _NARRATIVE_FETCHING.discard(n_key)
                                
                                with _NARRATIVE_CACHE_LOCK:
                                    if n_cache_key not in _NARRATIVE_FETCHING:
                                        _NARRATIVE_FETCHING.add(n_cache_key)
                                        import threading
                                        threading.Thread(target=_fetch_narrative_bg, args=(n_cache_key, sport_path, game_pk, market_query, line_val, side_val), daemon=True).start()

            except Exception as e:
                logger.warning(f"Failed to attach explanation: {e}")
            return best_match

        # 2. On-demand Monte Carlo simulation on local AI prediction engine (8057)
        if len(event_parts) == 2:
            # Kalshi convention lists AWAY first, HOME second (Away @ Home / Away vs Home)
            away = event_parts[0].strip().title()
            home = event_parts[1].split("(")[0].strip().title()

            sim_cache_key = f"{event_ticker_clean}_{away}_{home}"
            with _SIM_CACHE_LOCK:
                if sim_cache_key in _SIMULATION_CACHE:
                    return dict(_SIMULATION_CACHE[sim_cache_key])

            # 2a. Baseball (NPB / KBO)
            is_baseball = inferred_sport == "NPB/KBO" or any(k in event_ticker_clean or k in title_clean for k in [
                "npb", "kbo", "hawks", "eagles", "lions", "marines", "giants", "tigers",
                "carp", "twins", "bears", "dinos", "heroes", "baystars", "dragons",
                "buffaloes", "swallows", "fighters", "landers", "wiz"
            ])
            if is_baseball:
                try:
                    sim_res = self.client.get(
                        f"{self.base_url}/api/npb_kbo/simulate",
                        params={"home_team": home, "away_team": away, "simulations": 2500}
                    )
                    if sim_res.status_code == 200:
                        sim_data = sim_res.json()
                        rec_team = sim_data.get("recommended_ml") or home
                        if rec_team:
                            if home and (home.lower() in rec_team.lower() or rec_team.lower() in home.lower() or ("baystars" in rec_team.lower() and "baystars" in home.lower())):
                                rec_team = home
                            elif away and (away.lower() in rec_team.lower() or rec_team.lower() in away.lower() or ("carp" in rec_team.lower() and "carp" in away.lower())):
                                rec_team = away
                        home_prob = float(sim_data.get("win_prob_home") or sim_data.get("ensemble_home_prob") or 0.0)
                        away_prob = float(sim_data.get("win_prob_away") or (100.0 - home_prob))
                        rec_prob = home_prob if rec_team == home else away_prob
                        league_code = "KBO" if "kbo" in event_ticker_clean else "NPB"

                        sim_pick = {
                            "ai_source": "Simulation",
                            "sport": "NPB/KBO",
                            "league": league_code,
                            "market_type": "MONEYLINE",
                            "predicted_team": rec_team,
                            "opponent": f"{away} vs {home}",
                            "confidence_pct": round(rec_prob, 1),
                            "edge_pct": 0.0,
                            "metadata": {
                                "name": rec_team,
                                "matchup": f"{away} vs {home}",
                                "league": league_code,
                                "simulation": True,
                                "source": "Simulation",
                                "simulations_count": sim_data.get("simulations", 2500),
                                "recommended_total": sim_data.get("recommended_total")
                            }
                        }
                        with _SIM_CACHE_LOCK:
                            _SIMULATION_CACHE[sim_cache_key] = sim_pick
                        return sim_pick
                except Exception as e:
                    logger.warning(f"On-demand NPB/KBO simulation failed for {event_ticker}: {e}")

            # 2b. NFL Football
            elif inferred_sport == "NFL":
                try:
                    sim_res = self.client.get(
                        f"{self.base_url}/nfl/simulate",
                        params={"home_team": home, "away_team": away, "simulations": 3000}
                    )
                    if sim_res.status_code == 200:
                        sim_data = sim_res.json()
                        home_prob = float(sim_data.get("home_win_prob") or 0.0)
                        away_prob = float(sim_data.get("away_win_prob") or (100.0 - home_prob))
                        rec_team = sim_data.get("recommended_pick") or (home if home_prob >= away_prob else away)
                        rec_prob = home_prob if rec_team == home else away_prob
                        sim_pick = {
                            "ai_source": "Simulation",
                            "sport": "NFL",
                            "league": "NFL",
                            "market_type": "MONEYLINE",
                            "predicted_team": rec_team,
                            "opponent": f"{away} vs {home}",
                            "confidence_pct": round(rec_prob, 1),
                            "edge_pct": 0.0,
                            "metadata": {
                                "name": rec_team,
                                "matchup": f"{away} vs {home}",
                                "league": "NFL",
                                "simulation": True,
                                "source": "Simulation",
                                "simulations_count": sim_data.get("simulations", 3000),
                                "recommended_total": sim_data.get("recommended_total")
                            }
                        }
                        with _SIM_CACHE_LOCK:
                            _SIMULATION_CACHE[sim_cache_key] = sim_pick
                        return sim_pick
                except Exception as e:
                    logger.warning(f"On-demand NFL simulation failed for {event_ticker}: {e}")

            # 2c. Soccer
            elif inferred_sport == "SOC":
                try:
                    sim_res = self.client.get(
                        f"{self.base_url}/api/soccer/simulate",
                        params={"home_team": home, "away_team": away, "simulations": 3000}
                    )
                    if sim_res.status_code == 200:
                        sim_data = sim_res.json()
                        rec_team = sim_data.get("recommended_pick") or home
                        res_obj = sim_data.get("results") or {}
                        home_prob = float(res_obj.get("home_win_prob") or 0.0)
                        sim_pick = {
                            "ai_source": "Simulation",
                            "sport": "SOC",
                            "league": "SOC",
                            "market_type": "MONEYLINE",
                            "predicted_team": rec_team,
                            "opponent": f"{away} vs {home}",
                            "confidence_pct": round(home_prob, 1),
                            "edge_pct": 0.0,
                            "metadata": {
                                "name": rec_team,
                                "matchup": f"{away} vs {home}",
                                "league": "SOC",
                                "simulation": True,
                                "source": "Simulation",
                                "simulations_count": 3000
                            }
                        }
                        with _SIM_CACHE_LOCK:
                            _SIMULATION_CACHE[sim_cache_key] = sim_pick
                        return sim_pick
                except Exception as e:
                    logger.warning(f"On-demand Soccer simulation failed for {event_ticker}: {e}")

            # 2d. UFC / MMA
            elif inferred_sport == "UFC":
                try:
                    sim_res = self.client.get(
                        f"{self.base_url}/api/ufc/simulate",
                        params={"fighter_a": away, "fighter_b": home, "simulations": 3000}
                    )
                    if sim_res.status_code == 200:
                        sim_data = sim_res.json()
                        prob_a = float(sim_data.get("win_prob_a") or 0.0)
                        prob_b = float(sim_data.get("win_prob_b") or 0.0)
                        rec_fighter = away if prob_a >= prob_b else home
                        rec_prob = max(prob_a, prob_b)
                        sim_pick = {
                            "ai_source": "Simulation",
                            "sport": "UFC",
                            "league": "UFC",
                            "market_type": "BOUT",
                            "predicted_team": rec_fighter,
                            "opponent": f"{away} vs {home}",
                            "confidence_pct": round(rec_prob, 1),
                            "edge_pct": 0.0,
                            "metadata": {
                                "name": rec_fighter,
                                "matchup": f"{away} vs {home}",
                                "league": "UFC",
                                "simulation": True,
                                "source": "Simulation",
                                "simulations_count": 3000
                            }
                        }
                        with _SIM_CACHE_LOCK:
                            _SIMULATION_CACHE[sim_cache_key] = sim_pick
                        return sim_pick
                except Exception as e:
                    logger.warning(f"On-demand UFC simulation failed for {event_ticker}: {e}")

            # 2e. Tennis
            elif inferred_sport in ("TEN", "TENNIS"):
                try:
                    sim_res = self.client.get(
                        f"{self.base_url}/api/tennis/simulate",
                        params={"player_a": away, "player_b": home, "simulations": 1000}
                    )
                    if sim_res.status_code == 200:
                        sim_data = sim_res.json()
                        data = sim_data.get("data") or {}
                        prob_a = float(data.get("win_prob_a") or 0.0)
                        prob_b = float(data.get("win_prob_b") or 0.0)
                        if prob_a <= 1.0 and prob_b <= 1.0:
                            prob_a *= 100.0
                            prob_b *= 100.0
                        rec_player = away if prob_a >= prob_b else home
                        rec_prob = max(prob_a, prob_b)
                        sim_pick = {
                            "ai_source": "Simulation",
                            "sport": "TEN",
                            "league": "TEN",
                            "market_type": "MONEYLINE",
                            "predicted_team": rec_player,
                            "opponent": f"{away} vs {home}",
                            "confidence_pct": round(rec_prob, 1),
                            "edge_pct": 0.0,
                            "metadata": {
                                "name": rec_player,
                                "matchup": f"{away} vs {home}",
                                "league": "TEN",
                                "simulation": True,
                                "source": "Simulation",
                                "simulations_count": 1000
                            }
                        }
                        with _SIM_CACHE_LOCK:
                            _SIMULATION_CACHE[sim_cache_key] = sim_pick
                        return sim_pick
                except Exception as e:
                    logger.warning(f"On-demand Tennis simulation failed for {event_ticker}: {e}")

        # 3. Fallback: Native in-process simulator when upstream model matching produced no match
        try:
            from backend.sports_engine import get_native_sports_client
            native_pred = get_native_sports_client().predict_for_event(event_ticker, title=title, sport=sport)
            if native_pred:
                return native_pred
        except Exception as e:
            logger.debug(f"[SportsPredictionClient] Native fallback error: {e}")

        # 4. Final Fallback: Return baseline evaluation
        home = event_parts[0].title() if len(event_parts) == 2 else "Favorite"
        away = event_parts[1].split("(")[0].strip().title() if len(event_parts) == 2 else "Underdog"
        return {
            "sport": inferred_sport or "UNKNOWN",
            "league": inferred_sport or "UNKNOWN",
            "market_type": "MONEYLINE",
            "predicted_team": home or "Favorite",
            "opponent": f"{home} vs {away}" if (home and away) else title,
            "confidence_pct": 65.0,
            "edge_pct": 12.5,
            "metadata": {
                "name": home or "Favorite",
                "matchup": f"{home} vs {away}" if (home and away) else title,
                "on_demand_eval": True,
                "simulation": True
            }
        }
