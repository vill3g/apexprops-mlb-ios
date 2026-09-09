"""
FastAPI Application for ApexProps MLB & International Baseball Engine.
Serves REST API and hosts the graphical user interface.
"""

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Optional, List, Dict, Any
import os
import time

from backend.data.espn_client import ESPNClient
from backend.data.draftkings_client import DraftKingsClient
from backend.engine.simulator import HRRBISimulator
from backend.engine.top5_selector import Top5Selector
from backend.engine.pitcher_k_model import PitcherKModel
from backend.engine.international_model import InternationalBaseballModel
from backend.engine.bvp_weather import BvPWeatherModel

app = FastAPI(
    title="ApexProps Baseball Analytics Engine",
    version="3.0.0",
    description="Real-time MLB, NPB, and KBO baseball analytics, H+R+RBI, Ks, and BvP."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize singletons
espn_client = ESPNClient(cache_ttl_seconds=300)
draftkings_client = DraftKingsClient()
simulator = HRRBISimulator(num_simulations=5000)
selector = Top5Selector(espn_client=espn_client, simulator=simulator)
pitcher_k_model = PitcherKModel()
intl_model = InternationalBaseballModel()
bvp_weather_model = BvPWeatherModel()

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")

@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": "3.0.0", "service": "ApexProps Engine"}

@app.get("/api/slate")
def get_slate():
    slate = espn_client.get_todays_slate()
    return {
        "count": len(slate),
        "games": slate
    }

@app.get("/api/picks/top5")
def get_top5_picks(refresh: bool = False):
    picks_data = selector.generate_daily_picks(force_refresh=refresh)
    return {
        "timestamp": picks_data["timestamp"],
        "slate_count": picks_data["slate_count"],
        "total_props": picks_data["total_props"],
        "top_5": picks_data["top_5"]
    }

@app.get("/api/props")
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

@app.get("/api/pitchers/k-props")
def get_pitcher_k_props():
    slate = espn_client.get_todays_slate()
    k_data = pitcher_k_model.get_pitcher_k_data(slate)
    return {
        "count": len(k_data["props"]),
        "top5": k_data["top5"],
        "props": k_data["props"]
    }

@app.get("/api/international/npb")
def get_npb_predictions():
    games = intl_model.get_npb_slate()
    return {
        "league": "Japan NPB",
        "count": len(games),
        "games": games
    }

@app.get("/api/international/npb/standings")
def get_npb_standings():
    standings = intl_model.get_npb_standings()
    return {
        "league": "Japan NPB",
        "count": len(standings),
        "standings": standings
    }

@app.get("/api/international/kbo")
def get_kbo_predictions():
    games = intl_model.get_kbo_slate()
    return {
        "league": "Korea KBO",
        "count": len(games),
        "games": games
    }

@app.get("/api/international/kbo/standings")
def get_kbo_standings():
    standings = intl_model.get_kbo_standings()
    return {
        "league": "Korea KBO",
        "count": len(standings),
        "standings": standings
    }

@app.get("/api/international/historical")
def get_international_historical():
    results = intl_model.get_historical_results()
    return {
        "count": len(results),
        "results": results
    }

@app.get("/api/international/h2h/{league}/{game_id}")
def get_international_h2h(league: str, game_id: str):
    games = intl_model.get_npb_slate() if "npb" in league.lower() else intl_model.get_kbo_slate()
    match = next((g for g in games if str(g.get("game_id")) == str(game_id)), None)
    if match:
        return {
            "game_id": game_id,
            "league": match.get("league"),
            "matchup": f"{match['away_team']['name']} vs {match['home_team']['name']}",
            "h2h_history": match.get("h2h_history")
        }
    return {"error": "Game not found", "game_id": game_id}

@app.get("/api/draftkings/odds")
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
                "draftkings": dk_data
            })
    return {
        "count": len(odds_list),
        "provider": "DraftKings",
        "logo": draftkings_client.dk_logo,
        "games": odds_list
    }

@app.get("/api/bvp")
def get_bvp_matchups():
    matchups = bvp_weather_model.get_bvp_matchups()
    return {
        "count": len(matchups),
        "matchups": matchups
    }

@app.get("/api/weather")
def get_weather_radar():
    weather = bvp_weather_model.get_weather_radar()
    return {
        "count": len(weather),
        "venues": weather
    }

@app.get("/api/live/poll")
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
        "server_time": time.strftime("%H:%M:%S ET"),
        "live_count": len(live_games),
        "games": live_games
    }

# Mount static directory and route index
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.api_route("/", methods=["GET", "HEAD"])
def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "ApexProps Backend Running. Frontend index.html not found."}
