import logging
import os
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

from datetime import datetime
from zoneinfo import ZoneInfo

# Main imports
from backend.auth.dependencies import STATIC_DIR
from backend.data.draftkings_client import DraftKingsClient
from backend.data.espn_client import ESPNClient
from backend.data.injuries_client import InjuriesClient
from backend.data.verified_mlb_client import VerifiedMLBClient
from backend.engine.bvp_weather import BvPWeatherModel
from backend.engine.international_model import InternationalBaseballModel
from backend.engine.pitcher_k_model import PitcherKModel
from backend.engine.simulator import HRRBISimulator
from backend.engine.top5_selector import Top5Selector

# Singletons used by the sports endpoints (previously created in main.py, which these
# routes could not see after the router split — every sports endpoint raised NameError).
espn_client = ESPNClient(cache_ttl_seconds=300)
draftkings_client = DraftKingsClient()
simulator = HRRBISimulator(num_simulations=5000)
selector = Top5Selector(espn_client=espn_client, simulator=simulator)
pitcher_k_model = PitcherKModel()
intl_model = InternationalBaseballModel()
bvp_weather_model = BvPWeatherModel()
verified_client = VerifiedMLBClient()
injuries_client = InjuriesClient()

router = APIRouter()

@router.get("/api/slate")
def get_slate():
    slate = espn_client.get_todays_slate()
    return {
        "count": len(slate),
        "games": slate
    }

@router.get("/api/picks/top5")
def get_top5_picks(refresh: bool = False):
    picks_data = selector.generate_daily_picks(force_refresh=refresh)
    return {
        "timestamp": picks_data["timestamp"],
        "slate_count": picks_data["slate_count"],
        "total_props": picks_data["total_props"],
        "top_5": picks_data["top_5"]
    }

@router.get("/api/props")
def get_all_props(
    search: Optional[str] = None,
    min_prob: Optional[float] = 0.0,
    line: Optional[str] = "all",
    team: Optional[str] = None
):
    picks_data = selector.generate_daily_picks(force_refresh=False)
    props = picks_data["all_props"]

    if search:
        s = search.lower()
        props = [p for p in props if s in p["name"].lower() or s in p["team"].lower() or s in p["opponent"].lower()]

    if min_prob and min_prob > 0:
        props = [p for p in props if p["win_prob"] >= min_prob]

    if team and team != "all":
        props = [p for p in props if p["team"].upper() == team.upper()]

    return {
        "count": len(props),
        "props": props
    }

@router.get("/api/pitchers/k-props")
def get_pitcher_k_props():
    slate = espn_client.get_todays_slate()
    k_data = pitcher_k_model.get_pitcher_k_data(slate)
    return {
        "count": len(k_data["props"]),
        "top5": k_data["top5"],
        "props": k_data["props"]
    }

@router.get("/api/player/{player_id}/gamelog")
def get_player_gamelog(player_id: str, type: Optional[str] = "hitting"):
    """Returns official 10-game recent logs for the requested athlete."""
    # Check batter props
    picks = selector.generate_daily_picks(force_refresh=False)
    for p in picks.get("all_props", []):
        if str(p.get("id")) == str(player_id) or str(p.get("name")).lower() == str(player_id).lower():
            return {
                "player_id": player_id,
                "name": p.get("name"),
                "type": "hitting",
                "game_log": p.get("game_log", []),
                "verified_source": p.get("verified_source", "Official MLB & ESPN Verified"),
                "is_verified": p.get("is_verified", True)
            }
    
    # Check pitcher props
    slate = espn_client.get_todays_slate()
    k_data = pitcher_k_model.get_pitcher_k_data(slate)
    for p in k_data.get("props", []):
        if str(p.get("id")) == str(player_id) or str(p.get("name")).lower() == str(player_id).lower():
            return {
                "player_id": player_id,
                "name": p.get("name"),
                "type": "pitching",
                "game_log": p.get("game_log", []),
                "verified_source": p.get("verified_source", "Official MLB & ESPN Verified"),
                "is_verified": p.get("is_verified", True)
            }

    # Query VerifiedMLBClient directly if not in active cached slate
    if type == "pitching":
        logs = verified_client.get_pitcher_game_log(player_id, player_id)
    else:
        logs = verified_client.get_batter_game_log(player_id, player_id)

    return {
        "player_id": player_id,
        "name": player_id,
        "type": type,
        "game_log": logs,
        "verified_source": "Official MLB & ESPN Verified",
        "is_verified": any(g.get("verified", False) for g in logs)
    }

@router.get("/api/injuries")
def get_mlb_injuries(force_refresh: bool = False):
    """Returns official league-wide MLB Injured List."""
    if force_refresh:
        injuries_client.refresh_injuries()
    all_inj = injuries_client.get_all_injured()
    return {
        "count": len(all_inj),
        "injuries": all_inj,
        "teams": injuries_client.get_raw_teams()
    }

@router.get("/api/player/{player_id}/injury-status")
def get_player_injury_status(player_id: str):
    """Checks if a player is currently on the MLB Injured List."""
    inj = injuries_client.get_injury(player_id, player_id)
    if inj:
        return {
            "player_id": player_id,
            "name": inj.get("name"),
            "is_injured": True,
            "status": inj.get("status"),
            "team": inj.get("team"),
            "position": inj.get("position"),
            "description": inj.get("description"),
            "return_date": inj.get("return_date")
        }
    return {
        "player_id": player_id,
        "name": player_id,
        "is_injured": False,
        "status": "Active"
    }

@router.get("/api/international/npb")
def get_npb_predictions():
    games = intl_model.get_npb_slate()
    props = intl_model.get_npb_props()
    return {
        "league": "Japan NPB",
        "count": len(games),
        "games": games,
        "props": props
    }

@router.get("/api/international/npb/props")
def get_npb_props_endpoint():
    props = intl_model.get_npb_props()
    return {
        "league": "Japan NPB",
        "count": len(props),
        "props": props
    }

@router.get("/api/international/npb/standings")
def get_npb_standings():
    standings = intl_model.get_npb_standings()
    return {
        "league": "Japan NPB",
        "count": len(standings),
        "standings": standings
    }

@router.get("/api/international/kbo")
def get_kbo_predictions():
    games = intl_model.get_kbo_slate()
    props = intl_model.get_kbo_props()
    return {
        "league": "Korea KBO",
        "count": len(games),
        "games": games,
        "props": props
    }

@router.get("/api/international/kbo/props")
def get_kbo_props_endpoint():
    props = intl_model.get_kbo_props()
    return {
        "league": "Korea KBO",
        "count": len(props),
        "props": props
    }

@router.get("/api/international/kbo/standings")
def get_kbo_standings():
    standings = intl_model.get_kbo_standings()
    return {
        "league": "Korea KBO",
        "count": len(standings),
        "standings": standings
    }

@router.get("/api/international/historical")
def get_international_historical():
    results = intl_model.get_historical_results()
    return {
        "count": len(results),
        "results": results
    }

@router.get("/api/international/h2h/{league}/{game_id}")
def get_international_h2h(league: str, game_id: str):
    games = intl_model.get_npb_slate() if "npb" in league.lower() else intl_model.get_kbo_slate()
    match = next((g for g in games if str(g.get("game_id")) == str(game_id)), None)
    if match:
        return {
            "game_id": game_id,
            "league": match.get("league"),
            "matchup": f"{match.get('away_team', {}).get('name', 'Unknown')} vs {match.get('home_team', {}).get('name', 'Unknown')}",
            "h2h_history": match.get("h2h_history")
        }
    return JSONResponse({"error": "Game not found", "game_id": game_id}, status_code=404)

@router.get("/api/draftkings/odds")
def get_draftkings_odds():
    slate = espn_client.get_todays_slate()
    odds_list = []
    for g in slate:
        ev_id = g.get("game_id")
        if ev_id:
            dk_data = draftkings_client.get_game_dk_odds(ev_id)
            odds_list.append({
                "game_id": ev_id,
                "matchup": f"{g.get('away_team', {}).get('abbreviation')} @ {g.get('home_team', {}).get('abbreviation')}",
                "home_team": g.get('home_team', {}).get('name'),
                "away_team": g.get('away_team', {}).get('name'),
                "venue": g.get('venue'),
                "odds": dk_data,
                "draftkings": dk_data
            })
    return {
        "count": len(odds_list),
        "provider": "The Odds API",
        "logo": draftkings_client.logo,
        "games": odds_list
    }

@router.get("/api/bvp")
def get_bvp_matchups():
    matchups = bvp_weather_model.get_bvp_matchups()
    return {
        "count": len(matchups),
        "matchups": matchups
    }

@router.get("/api/weather")
def get_weather_radar():
    weather = bvp_weather_model.get_weather_radar()
    return {
        "count": len(weather),
        "venues": weather
    }

@router.get("/api/live/poll")
def live_poll():
    """2-second live polling endpoint providing real-time game status and clocks."""
    slate = espn_client.get_todays_slate()
    live_games = [
        {
            "id": g.get("game_id"),
            "short_name": g.get("short_name"),
            "status": g.get("status"),
            "detail": g.get("status_detail"),
            "home_score": g.get("home_team", {}).get("score", "0"),
            "away_score": g.get("away_team", {}).get("score", "0")
        }
        for g in slate
    ]
    return {
        "server_time": datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M:%S %p ET").lstrip("0"),
        "live_count": len(live_games),
        "games": live_games
    }

@router.get("/api/ui_version")
def get_ui_version():
    index_path = os.path.join(STATIC_DIR, "index.html")
    mtime = os.path.getmtime(index_path) if os.path.exists(index_path) else 0
    return JSONResponse(
        {"version": "4.1.0", "mtime": mtime},
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )
