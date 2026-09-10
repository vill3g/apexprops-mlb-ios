"""
The Odds API Client (the-odds-api.com)
Fetches official live DraftKings sports odds and MLB player props.
Includes persistent disk + memory caching to conserve API quota.
"""

import os
import time
import json
import logging
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger("the_odds_client")

THE_ODDS_API_KEY = os.environ.get("THE_ODDS_API_KEY", "d071932f8bc476d8b101319c8fc87b1e")
BASE_URL = "https://api.the-odds-api.com/v4"
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "the_odds_cache.json")

# MLB Team Name to ESPN Abbreviation Mapping
TEAM_ABBR_MAP = {
    "Arizona Diamondbacks": "ARI",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Oakland Athletics": "OAK",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD",
    "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSH"
}

# Reverse map abbreviation to full team name
ABBR_TO_TEAM_MAP = {v: k for k, v in TEAM_ABBR_MAP.items()}


class TheOddsClient:
    def __init__(self, api_key: str = THE_ODDS_API_KEY):
        self.api_key = api_key
        self.cache_ttl_games = 600.0   # 10 minutes cache for game odds
        self.cache_ttl_props = 1800.0  # 30 minutes cache for player props
        self._cache = self._load_disk_cache()
        self.logo = "https://the-odds-api.com/favicon.ico"
        self.provider = "The Odds API"

    def _load_disk_cache(self) -> Dict[str, Any]:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error reading odds cache: {e}")
        return {"games": {}, "props": {}, "games_fetched_at": 0.0, "props_fetched_at": {}}

    def _save_disk_cache(self):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Error saving odds cache: {e}")

    def get_game_odds(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch all MLB game moneylines, spreads, and over/unders strictly via The Odds API.
        Returns a dict keyed by game_id and team abbreviation.
        """
        now = time.time()
        last_fetch = self._cache.get("games_fetched_at", 0.0)

        if not force_refresh and (now - last_fetch < self.cache_ttl_games) and self._cache.get("games"):
            return self._cache["games"]

        url = f"{BASE_URL}/sports/baseball_mlb/odds"
        params = {
            "apiKey": self.api_key,
            "regions": "us",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american"
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                raw_games = resp.json()
                parsed_games = {}

                for g in raw_games:
                    g_id = g.get("id")
                    home = g.get("home_team", "")
                    away = g.get("away_team", "")
                    home_abbr = TEAM_ABBR_MAP.get(home, home[:3].upper())
                    away_abbr = TEAM_ABBR_MAP.get(away, away[:3].upper())

                    bms = g.get("bookmakers", [])
                    # Pick active US bookmaker from The Odds API
                    active_bm = bms[0] if bms else None
                    bm_name = active_bm.get("title", "The Odds API") if active_bm else "The Odds API"

                    home_ml = -120
                    away_ml = 100
                    spread = -1.5
                    spread_home_odds = -110
                    over_under = 8.5
                    over_odds = -110
                    under_odds = -110

                    if active_bm:
                        for m in active_bm.get("markets", []):
                            m_key = m.get("key")
                            outcomes = m.get("outcomes", [])
                            if m_key == "h2h":
                                for o in outcomes:
                                    if o.get("name") == home:
                                        home_ml = o.get("price", -120)
                                    elif o.get("name") == away:
                                        away_ml = o.get("price", 100)
                            elif m_key == "spreads":
                                for o in outcomes:
                                    if o.get("name") == home:
                                        spread = o.get("point", -1.5)
                                        spread_home_odds = o.get("price", -110)
                                    elif o.get("name") == away:
                                        spread_away_odds = o.get("price", -110)
                            elif m_key == "totals":
                                for o in outcomes:
                                    if o.get("name") == "Over":
                                        over_under = o.get("point", 8.5)
                                        over_odds = o.get("price", -110)
                                    elif o.get("name") == "Under":
                                        under_odds = o.get("price", -110)

                    game_data = {
                        "event_id": g_id,
                        "home_team": home,
                        "away_team": away,
                        "home_abbr": home_abbr,
                        "away_abbr": away_abbr,
                        "commence_time": g.get("commence_time"),
                        "provider": "The Odds API",
                        "provider_logo": self.logo,
                        "bookmaker": bm_name,
                        "home_ml": home_ml,
                        "away_ml": away_ml,
                        "spread": spread,
                        "over_under": over_under,
                        "over_odds": over_odds,
                        "under_odds": under_odds,
                        "details": f"{away_abbr} @ {home_abbr}",
                        "source": "the-odds-api.com"
                    }

                    parsed_games[g_id] = game_data
                    parsed_games[f"{away_abbr}@{home_abbr}"] = game_data
                    parsed_games[f"{home_abbr}"] = game_data
                    parsed_games[f"{away_abbr}"] = game_data
                    parsed_games[home] = game_data
                    parsed_games[away] = game_data

                self._cache["games"] = parsed_games
                self._cache["games_fetched_at"] = now
                self._save_disk_cache()
                logger.info(f"Successfully fetched {len(raw_games)} MLB games from The Odds API")
                return parsed_games
            else:
                logger.warning(f"The Odds API returned status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"Error fetching game odds from The Odds API: {e}")

        return self._cache.get("games", {})

    def fetch_player_props_for_event(self, event_id: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch player props for a single game event strictly from The Odds API.
        Markets: batter_hits, batter_total_bases, batter_rbis, batter_home_runs, pitcher_strikeouts.
        """
        now = time.time()
        props_cache = self._cache.setdefault("props", {})
        fetched_at_map = self._cache.setdefault("props_fetched_at", {})

        if not force_refresh and (now - fetched_at_map.get(event_id, 0.0) < self.cache_ttl_props) and event_id in props_cache:
            return props_cache[event_id]

        url = f"{BASE_URL}/sports/baseball_mlb/events/{event_id}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": "us",
            "markets": "batter_hits,batter_total_bases,batter_rbis,batter_home_runs,pitcher_strikeouts",
            "oddsFormat": "american"
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                bms = data.get("bookmakers", [])
                parsed_player_props = {}

                for bm in bms:
                    bm_title = bm.get("title", bm.get("key"))
                    for market in bm.get("markets", []):
                        m_key = market.get("key")
                        outcomes = market.get("outcomes", [])
                        for o in outcomes:
                            p_name = o.get("description", "").strip()
                            if not p_name:
                                continue
                            norm_name = p_name.lower()
                            p_entry = parsed_player_props.setdefault(norm_name, {
                                "player_name": p_name,
                                "event_id": event_id,
                                "bookmaker": bm_title,
                                "provider": "The Odds API",
                                "markets": {}
                            })
                            side = o.get("name") # Over or Under
                            point = o.get("point")
                            price = o.get("price")
                            
                            m_dict = p_entry["markets"].setdefault(m_key, {})
                            if side.lower() not in m_dict:
                                m_dict[side.lower()] = {
                                    "line": point,
                                    "odds": price,
                                    "formatted_odds": f"+{price}" if price > 0 else f"{price}",
                                    "bookmaker": bm_title
                                }

                props_cache[event_id] = parsed_player_props
                fetched_at_map[event_id] = now
                self._save_disk_cache()
                logger.info(f"Fetched The Odds API props for event {event_id}: {len(parsed_player_props)} players")
                return parsed_player_props
            else:
                logger.warning(f"Error fetching props for event {event_id}: status {resp.status_code}")
        except Exception as e:
            logger.error(f"Error querying player props for {event_id}: {e}")

        return props_cache.get(event_id, {})

    def fetch_all_active_props(self, max_events: int = 6) -> Dict[str, Any]:
        """
        Batch fetch player props across up to max_events games for today's slate,
        merging into a single player-name indexed dictionary.
        """
        game_odds = self.get_game_odds()
        seen_events = set()
        events_to_fetch = []
        for k, v in game_odds.items():
            ev_id = v.get("event_id")
            if ev_id and ev_id not in seen_events:
                seen_events.add(ev_id)
                events_to_fetch.append(ev_id)

        all_players: Dict[str, Any] = {}
        for ev_id in events_to_fetch[:max_events]:
            event_props = self.fetch_player_props_for_event(ev_id)
            for norm_name, p_data in event_props.items():
                all_players[norm_name] = p_data

        return all_players

    def find_player_odds(self, player_name: str, is_pitcher: bool = False) -> Optional[Dict[str, Any]]:
        """
        Lookup official DraftKings live prop line and American odds for a player.
        """
        if not player_name:
            return None
        norm = player_name.strip().lower()
        norm_clean = norm.replace(".", "").replace("-", " ")

        all_props = self._cache.get("props", {})
        for ev_id, players in all_props.items():
            for p_key, p_data in players.items():
                p_key_clean = p_key.replace(".", "").replace("-", " ")
                if norm == p_key or norm_clean == p_key_clean or norm in p_key or p_key in norm:
                    markets = p_data.get("markets", {})
                    if is_pitcher and "pitcher_strikeouts" in markets:
                        k_over = markets["pitcher_strikeouts"].get("over", {})
                        if k_over:
                            return {
                                "market": "pitcher_strikeouts",
                                "line": k_over.get("line", 5.5),
                                "odds": k_over.get("odds", -125),
                                "formatted_odds": k_over.get("formatted_odds", "-125"),
                                "bookmaker": k_over.get("bookmaker", "The Odds API"),
                                "provider": "The Odds API",
                                "event_id": ev_id
                            }
                    elif not is_pitcher:
                        for m_cand in ["batter_hits", "batter_rbis", "batter_total_bases", "batter_home_runs"]:
                            if m_cand in markets and "over" in markets[m_cand]:
                                cand_over = markets[m_cand]["over"]
                                return {
                                    "market": m_cand,
                                    "line": cand_over.get("line", 1.5),
                                    "odds": cand_over.get("odds", -135),
                                    "formatted_odds": cand_over.get("formatted_odds", "-135"),
                                    "bookmaker": cand_over.get("bookmaker", "The Odds API"),
                                    "provider": "The Odds API",
                                    "event_id": ev_id
                                }
        return None
