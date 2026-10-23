import json
import logging
import time
import urllib.request
from typing import Any, Dict, List, Optional
from backend.data.espn_client import parse_game_datetime

logger = logging.getLogger(__name__)
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

class NBAClient:
    def __init__(self, cache_ttl_seconds: int = 300):
        self.cache_ttl = cache_ttl_seconds
        self._slate_cache: Optional[List[Dict[str, Any]]] = None
        self._slate_cache_time: float = 0.0

    def fetch_json(self, url: str) -> Optional[Dict[str, Any]]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0.1"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"Error querying {url}: {e}")
        return None

    def get_todays_slate(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        now = time.time()
        if not force_refresh and self._slate_cache and (now - self._slate_cache_time < self.cache_ttl):
            return self._slate_cache

        data = self.fetch_json(SCOREBOARD_URL)
        if not data:
            return []

        raw_events = data.get("events", [])
        games = []
        for ev in raw_events:
            game_id = ev.get("id")
            name = ev.get("name", "")
            short_name = ev.get("shortName", "")
            status = ev.get("status", {}).get("type", {}).get("state", "pre")
            status_detail = ev.get("status", {}).get("type", {}).get("shortDetail", "")
            
            competitions = ev.get("competitions")
            comp = competitions[0] if (competitions and isinstance(competitions, list)) else {}
            venue = comp.get("venue", {}).get("fullName", "Standard Arena")
            
            home_comp = next((c for c in comp.get("competitors", []) if c.get("homeAway") == "home"), {})
            away_comp = next((c for c in comp.get("competitors", []) if c.get("homeAway") == "away"), {})

            home_team = {
                "id": home_comp.get("team", {}).get("id"),
                "abbreviation": home_comp.get("team", {}).get("abbreviation", "HOME"),
                "name": home_comp.get("team", {}).get("displayName", "Home Team"),
                "logo": home_comp.get("team", {}).get("logo", ""),
                "score": home_comp.get("score", "0")
            }

            away_team = {
                "id": away_comp.get("team", {}).get("id"),
                "abbreviation": away_comp.get("team", {}).get("abbreviation", "AWAY"),
                "name": away_comp.get("team", {}).get("displayName", "Away Team"),
                "logo": away_comp.get("team", {}).get("logo", ""),
                "score": away_comp.get("score", "0")
            }

            dt_info = parse_game_datetime(ev.get("date", ""), status_detail)

            games.append({
                "game_id": game_id,
                "name": name,
                "short_name": short_name,
                "status": status,
                "status_detail": status_detail,
                "game_date": dt_info["game_date"],
                "game_time": dt_info["game_time"],
                "game_datetime": dt_info["game_datetime"],
                "venue": venue,
                "home_team": home_team,
                "away_team": away_team,
            })

        self._slate_cache = games
        self._slate_cache_time = now
        return games
