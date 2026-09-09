"""
ESPN MLB API Client
Fetches real-time MLB scoreboards, confirmed starting lineups, probable pitchers,
DraftKings game totals/spreads, and athlete metadata.
Optimized with concurrent fetching and in-memory caching.
"""

import json
import logging
import urllib.request
import urllib.error
import time
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary?event={event_id}"

def parse_game_datetime(iso_date: str, status_detail: str = "") -> Dict[str, str]:
    """Parse ISO date and status_detail into human-friendly date and ET time."""
    game_date = "Today, Sep 9"
    game_time = "7:05 PM ET"
    game_datetime = "Today • 7:05 PM ET"
    
    if iso_date:
        try:
            clean_iso = iso_date.replace("Z", "+00:00")
            dt_utc = datetime.datetime.fromisoformat(clean_iso)
            edt_tz = datetime.timezone(datetime.timedelta(hours=-4))
            dt_et = dt_utc.astimezone(edt_tz)
            
            h = dt_et.strftime("%I").lstrip("0")
            game_time = f"{h}:{dt_et.strftime('%M %p')} ET"
            
            now_et = datetime.datetime.now(edt_tz)
            if dt_et.date() == now_et.date():
                game_date = f"Today, {dt_et.strftime('%b %d')}"
                game_datetime = f"Today • {game_time}"
            elif dt_et.date() == (now_et.date() + datetime.timedelta(days=1)):
                game_date = f"Tomorrow, {dt_et.strftime('%b %d')}"
                game_datetime = f"Tomorrow • {game_time}"
            else:
                game_date = dt_et.strftime("%b %d, %Y")
                game_datetime = f"{dt_et.strftime('%b %d')} • {game_time}"
        except Exception:
            pass

    return {
        "game_date": game_date,
        "game_time": game_time,
        "game_datetime": game_datetime
    }

# Ballpark baseline run factors relative to 1.00
PARK_FACTORS = {
    "Coors Field": 1.34,
    "Great American Ball Park": 1.18,
    "Fenway Park": 1.14,
    "Yankee Stadium": 1.09,
    "Globe Life Field": 1.06,
    "Wrigley Field": 1.05,
    "Oriole Park at Camden Yards": 0.98,
    "Dodger Stadium": 1.02,
    "Minute Maid Park": 1.01,
    "Truist Park": 1.03,
    "Oracle Park": 0.88,
    "Petco Park": 0.91,
    "T-Mobile Park": 0.90,
}

class ESPNClient:
    def __init__(self, cache_ttl_seconds: int = 300):
        self.cache_ttl = cache_ttl_seconds
        self._slate_cache: Optional[List[Dict[str, Any]]] = None
        self._slate_cache_time: float = 0.0
        self._game_cache: Dict[str, Any] = {}

    def fetch_json(self, url: str) -> Optional[Dict[str, Any]]:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "curl/8.0.1"}
            )
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

        edt_tz = datetime.timezone(datetime.timedelta(hours=-4))
        now_et = datetime.datetime.now(edt_tz)
        today_str = now_et.strftime("%Y%m%d")

        data = self.fetch_json(f"{SCOREBOARD_URL}?dates={today_str}")
        if not data:
            data = self.fetch_json(SCOREBOARD_URL)
        if not data:
            return self._get_fallback_slate()

        raw_events = data.get("events", [])

        # Filter out completed / final games - strictly keep upcoming
        upcoming_events = []
        for ev in raw_events:
            st = ev.get("status", {}).get("type", {})
            state = st.get("state", "pre")
            completed = st.get("completed", False)
            short_detail = st.get("shortDetail", "").lower()
            if state == "post" or completed or "final" in short_detail or "f/" in short_detail:
                continue
            upcoming_events.append(ev)

        # If today has few or no upcoming games left, roll forward to tomorrow's slate
        if len(upcoming_events) < 3:
            tomorrow_str = (now_et + datetime.timedelta(days=1)).strftime("%Y%m%d")
            tomorrow_data = self.fetch_json(f"{SCOREBOARD_URL}?dates={tomorrow_str}")
            if tomorrow_data:
                for ev in tomorrow_data.get("events", []):
                    st = ev.get("status", {}).get("type", {})
                    state = st.get("state", "pre")
                    completed = st.get("completed", False)
                    short_detail = st.get("shortDetail", "").lower()
                    if state != "post" and not completed and "final" not in short_detail and "f/" not in short_detail:
                        upcoming_events.append(ev)

        if not upcoming_events:
            upcoming_events = raw_events # fallback if all dates empty

        games = []
        for ev in upcoming_events:
            game_id = ev.get("id")
            name = ev.get("name", "")
            short_name = ev.get("shortName", "")
            status = ev.get("status", {}).get("type", {}).get("state", "pre")
            status_detail = ev.get("status", {}).get("type", {}).get("shortDetail", "")
            
            comp = ev.get("competitions", [{}])[0]
            venue = comp.get("venue", {}).get("fullName", "Standard Park")
            venue_city = comp.get("venue", {}).get("address", {}).get("city", "")

            home_comp = next((c for c in comp.get("competitors", []) if c.get("homeAway") == "home"), {})
            away_comp = next((c for c in comp.get("competitors", []) if c.get("homeAway") == "away"), {})

            home_team = {
                "id": home_comp.get("team", {}).get("id"),
                "abbreviation": home_comp.get("team", {}).get("abbreviation", "HOME"),
                "name": home_comp.get("team", {}).get("displayName", "Home Team"),
                "logo": home_comp.get("team", {}).get("logo") or f"https://a.espncdn.com/i/teamlogos/mlb/500/{home_comp.get('team', {}).get('abbreviation', '').lower()}.png",
                "score": home_comp.get("score", "0")
            }

            away_team = {
                "id": away_comp.get("team", {}).get("id"),
                "abbreviation": away_comp.get("team", {}).get("abbreviation", "AWAY"),
                "name": away_comp.get("team", {}).get("displayName", "Away Team"),
                "logo": away_comp.get("team", {}).get("logo") or f"https://a.espncdn.com/i/teamlogos/mlb/500/{away_comp.get('team', {}).get('abbreviation', '').lower()}.png",
                "score": away_comp.get("score", "0")
            }

            # Probable pitchers
            home_prob = (home_comp.get("probables") or [{}])[0]
            away_prob = (away_comp.get("probables") or [{}])[0]

            home_pitcher = self._parse_pitcher(home_prob)
            away_pitcher = self._parse_pitcher(away_prob)
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
                "venue_city": venue_city,
                "park_factor": PARK_FACTORS.get(venue, 1.00),
                "home_team": home_team,
                "away_team": away_team,
                "home_pitcher": home_pitcher,
                "away_pitcher": away_pitcher,
            })

        self._slate_cache = games
        self._slate_cache_time = now
        return games

    def _parse_pitcher(self, prob_data: Dict[str, Any]) -> Dict[str, Any]:
        ath = prob_data.get("athlete", {})
        stats = prob_data.get("statistics", [])
        era = "4.20"
        for s in stats:
            if s.get("name") == "ERA":
                era = s.get("displayValue", "4.20")
        
        return {
            "id": ath.get("id"),
            "name": ath.get("displayName", "Probable Pitcher"),
            "headshot": ath.get("headshot") or (f"https://a.espncdn.com/i/headshots/mlb/players/full/{ath.get('id')}.png" if ath.get("id") else ""),
            "era": era,
            "record": prob_data.get("record", "")
        }

    def get_game_details(self, game_id: str) -> Dict[str, Any]:
        if game_id in self._game_cache:
            return self._game_cache[game_id]

        url = SUMMARY_URL.format(event_id=game_id)
        data = self.fetch_json(url)
        if not data:
            return {
                "lineups": [],
                "odds": {"overUnder": 8.5, "spread": -1.5},
                "dk_event_url": "https://sportsbook.draftkings.com/leagues/baseball/mlb",
                "dk_slip_link": ""
            }

        # PickCenter Odds (DraftKings)
        pickcenter = data.get("pickcenter", [])
        over_under = 8.5
        spread = -1.5
        dk_event_url = "https://sportsbook.draftkings.com/leagues/baseball/mlb"
        dk_slip_link = ""

        for p in pickcenter:
            if "overUnder" in p and p["overUnder"] is not None:
                over_under = float(p["overUnder"])
            if "spread" in p and p["spread"] is not None:
                spread = float(p["spread"])
            
            # Extract DraftKings deep link
            for link in p.get("links", []):
                href = link.get("href", "")
                if "draftkings.com" in href:
                    dk_slip_link = href
                    if "preurl=" in href:
                        import urllib.parse
                        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        if "preurl" in qs:
                            dk_event_url = qs["preurl"][0]
                    break
            if dk_slip_link:
                break

        # Lineup batters from Boxscore
        boxscore = data.get("boxscore", {})
        players_data = boxscore.get("players", [])
        lineups = []

        for team_entry in players_data:
            team_info = team_entry.get("team", {})
            team_abbr = team_info.get("abbreviation", "")
            
            for s in team_entry.get("statistics", []):
                if s.get("type") == "batting":
                    athletes = s.get("athletes", [])
                    for idx, a_entry in enumerate(athletes):
                        ath = a_entry.get("athlete", {})
                        bat_order = a_entry.get("batOrder") or (idx + 1)
                        if bat_order > 9:
                            continue # Substitute or bench player
                        
                        pos = a_entry.get("position", {}).get("abbreviation", "DH")
                        stats = a_entry.get("stats", [])
                        avg = float(stats[9]) if len(stats) > 9 and stats[9].replace('.', '').isdigit() else 0.260
                        obp = float(stats[10]) if len(stats) > 10 and stats[10].replace('.', '').isdigit() else 0.330
                        slg = float(stats[11]) if len(stats) > 11 and stats[11].replace('.', '').isdigit() else 0.420

                        lineups.append({
                            "id": int(ath.get("id", 0)) if str(ath.get("id", "0")).isdigit() else idx,
                            "name": ath.get("displayName", "Player"),
                            "team": team_abbr,
                            "order": int(bat_order),
                            "pos": pos,
                            "headshot": f"https://a.espncdn.com/i/headshots/mlb/players/full/{ath.get('id')}.png",
                            "team_logo": f"https://a.espncdn.com/i/teamlogos/mlb/500/{team_abbr.lower()}.png",
                            "avg": avg,
                            "obp": obp,
                            "slg": slg
                        })

        result = {
            "odds": {"overUnder": over_under, "spread": spread},
            "lineups": lineups,
            "dk_event_url": dk_event_url,
            "dk_slip_link": dk_slip_link
        }
        self._game_cache[game_id] = result
        return result

    def batch_fetch_games(self, game_ids: List[str], max_workers: int = 8) -> Dict[str, Dict[str, Any]]:
        """Fetch multiple game details concurrently for sub-2 second response."""
        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_id = {executor.submit(self.get_game_details, gid): gid for gid in game_ids}
            for future in as_completed(future_to_id):
                gid = future_to_id[future]
                try:
                    results[gid] = future.result()
                except Exception as e:
                    logger.warning(f"Error in batch fetch for {gid}: {e}")
                    results[gid] = {"lineups": [], "odds": {"overUnder": 8.5, "spread": -1.5}}
        return results

    def _get_fallback_slate(self) -> List[Dict[str, Any]]:
        return [
            {
                "game_id": "401816863",
                "name": "Cincinnati Reds at Los Angeles Dodgers",
                "short_name": "CIN @ LAD",
                "status": "pre",
                "status_detail": "7:10 PM ET",
                "game_date": "Today, Sep 9",
                "game_time": "7:10 PM ET",
                "game_datetime": "Today • 7:10 PM ET",
                "venue": "Dodger Stadium",
                "venue_city": "Los Angeles",
                "park_factor": 1.02,
                "home_team": {"id": "19", "abbreviation": "LAD", "name": "Los Angeles Dodgers", "logo": "https://a.espncdn.com/i/teamlogos/mlb/500/lad.png", "score": "0"},
                "away_team": {"id": "17", "abbreviation": "CIN", "name": "Cincinnati Reds", "logo": "https://a.espncdn.com/i/teamlogos/mlb/500/cin.png", "score": "0"},
                "home_pitcher": {"id": "41158", "name": "Yoshinobu Yamamoto", "headshot": "https://a.espncdn.com/i/headshots/mlb/players/full/41158.png", "era": "2.92", "record": "(11-2)"},
                "away_pitcher": {"id": "42398", "name": "Hunter Greene", "headshot": "https://a.espncdn.com/i/headshots/mlb/players/full/42398.png", "era": "2.75", "record": "(9-4)"}
            }
        ]
