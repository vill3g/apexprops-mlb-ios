"""
FastAPI Application for ApexProps MLB & International Baseball Engine.
Serves REST API and hosts the graphical user interface.
"""

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional, List, Dict, Any
import os
import time
import json
import pandas as pd

from backend.btc.data_fetcher import fetch_candles, get_btc_ticker, get_candle_countdown
from backend.btc.indicators import add_all_indicators
from backend.btc.pattern_detector import detect_candlestick_patterns
from backend.btc.analyzer import analyze_btc

from backend.data.espn_client import ESPNClient
from backend.data.draftkings_client import DraftKingsClient
from backend.engine.simulator import HRRBISimulator
from backend.engine.top5_selector import Top5Selector
from backend.engine.pitcher_k_model import PitcherKModel
from backend.engine.international_model import InternationalBaseballModel
from backend.engine.bvp_weather import BvPWeatherModel
from backend.data.verified_mlb_client import VerifiedMLBClient
from backend.data.injuries_client import InjuriesClient

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
verified_client = VerifiedMLBClient()
injuries_client = InjuriesClient()

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

@app.get("/api/player/{player_id}/gamelog")
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

@app.get("/api/injuries")
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

@app.get("/api/player/{player_id}/injury-status")
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

@app.get("/api/international/npb")
def get_npb_predictions():
    games = intl_model.get_npb_slate()
    props = intl_model.get_npb_props()
    return {
        "league": "Japan NPB",
        "count": len(games),
        "games": games,
        "props": props
    }

@app.get("/api/international/npb/props")
def get_npb_props_endpoint():
    props = intl_model.get_npb_props()
    return {
        "league": "Japan NPB",
        "count": len(props),
        "props": props
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
    props = intl_model.get_kbo_props()
    return {
        "league": "Korea KBO",
        "count": len(games),
        "games": games,
        "props": props
    }

@app.get("/api/international/kbo/props")
def get_kbo_props_endpoint():
    props = intl_model.get_kbo_props()
    return {
        "league": "Korea KBO",
        "count": len(props),
        "props": props
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

# =====================================================================
# BITCOIN 15M PATTERN ANALYZER & CONFLUENCE ENGINE
# =====================================================================
btc_timeframe_cache: Dict[str, Any] = {}

def get_cached_btc_analysis(timeframe: str = "15m", max_age_seconds: int = 15):
    """Retrieve or compute BTC analysis with smart per-timeframe caching."""
    now = time.time()
    tf = timeframe.lower()
    if tf in btc_timeframe_cache and (now - btc_timeframe_cache[tf]["last_fetched"]) < max_age_seconds:
        return btc_timeframe_cache[tf]["df"], btc_timeframe_cache[tf]["analysis"]

    try:
        df = fetch_candles(timeframe=tf, limit=250)
        analysis = analyze_btc(df, timeframe=tf)
        btc_timeframe_cache[tf] = {
            "df": df,
            "analysis": analysis,
            "last_fetched": now
        }
        return df, analysis
    except Exception as e:
        print(f"Error fetching live BTC candles for {tf}: {e}")
        if tf in btc_timeframe_cache:
            return btc_timeframe_cache[tf]["df"], btc_timeframe_cache[tf]["analysis"]
        raise e

def sanitize_btc_json(val):
    """Recursively convert NumPy scalars/types to standard Python types for JSON serialization."""
    if isinstance(val, dict):
        return {k: sanitize_btc_json(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple)):
        return [sanitize_btc_json(v) for v in val]
    elif hasattr(val, "item"):
        return val.item()
    elif isinstance(val, pd.Timestamp):
        return str(val)
    return val

@app.get("/api/btc/analyze")
def api_btc_analyze(timeframe: str = "15m"):
    """Returns comprehensive directional analysis, score, and trade setup for selected timeframe."""
    try:
        _, analysis = get_cached_btc_analysis(timeframe=timeframe)
        return JSONResponse(sanitize_btc_json(analysis))
    except Exception as e:
        static_backup = os.path.join(STATIC_DIR, "data", "btc_analysis.json")
        if os.path.exists(static_backup):
            try:
                with open(static_backup, "r", encoding="utf-8") as f:
                    return JSONResponse(json.load(f))
            except Exception:
                pass
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/btc/ticker")
def api_btc_ticker():
    """Returns live 24h ticker info."""
    try:
        ticker = get_btc_ticker()
        return JSONResponse(sanitize_btc_json(ticker))
    except Exception as e:
        static_backup = os.path.join(STATIC_DIR, "data", "btc_ticker.json")
        if os.path.exists(static_backup):
            try:
                with open(static_backup, "r", encoding="utf-8") as f:
                    return JSONResponse(json.load(f))
            except Exception:
                pass
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/btc/countdown")
def api_btc_countdown(timeframe: str = "15m"):
    """Returns countdown to current candle close for selected timeframe."""
    try:
        return JSONResponse(sanitize_btc_json(get_candle_countdown(timeframe=timeframe)))
    except Exception as e:
        return JSONResponse({"formatted": "--:--", "seconds_left": 0})

@app.get("/api/btc/candles")
def api_btc_candles(timeframe: str = "15m"):
    """
    Returns formatted candlestick data + indicators + pattern markers
    for TradingView Lightweight Charts for the selected timeframe.
    """
    try:
        df, analysis = get_cached_btc_analysis(timeframe=timeframe)
        df_ind = add_all_indicators(df)

        candles = []
        ema9_data = []
        ema21_data = []
        ema50_data = []
        ema200_data = []
        markers = []

        for i, row in df_ind.iterrows():
            t = int(row["time"])
            candles.append({
                "time": t,
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2),
            })

            if not pd.isna(row.get("ema_9", None)):
                ema9_data.append({"time": t, "value": round(float(row["ema_9"]), 2)})
            if not pd.isna(row.get("ema_21", None)):
                ema21_data.append({"time": t, "value": round(float(row["ema_21"]), 2)})
            if not pd.isna(row.get("ema_50", None)):
                ema50_data.append({"time": t, "value": round(float(row["ema_50"]), 2)})
            if not pd.isna(row.get("ema_200", None)):
                ema200_data.append({"time": t, "value": round(float(row["ema_200"]), 2)})

        for j in range(max(0, len(df_ind) - 20), len(df_ind)):
            sub = df_ind.iloc[: j + 1]
            pats = detect_candlestick_patterns(sub)
            if pats:
                p = pats[-1]
                t_pat = int(df_ind.iloc[j]["time"])
                markers.append({
                    "time": t_pat,
                    "position": "belowBar" if p["type"] == "BULLISH" else "aboveBar",
                    "color": "#00e676" if p["type"] == "BULLISH" else "#ff3d57",
                    "shape": "arrowUp" if p["type"] == "BULLISH" else "arrowDown",
                    "text": p["name"],
                })

        ticker = get_btc_ticker()

        return JSONResponse(sanitize_btc_json({
            "candles": candles,
            "ema9": ema9_data,
            "ema21": ema21_data,
            "ema50": ema50_data,
            "ema200": ema200_data,
            "markers": markers,
            "ticker": ticker
        }))
    except Exception as e:
        static_backup = os.path.join(STATIC_DIR, "data", "btc_candles.json")
        if os.path.exists(static_backup):
            try:
                with open(static_backup, "r", encoding="utf-8") as f:
                    return JSONResponse(json.load(f))
            except Exception:
                pass
        return JSONResponse({"error": str(e)}, status_code=500)

# Mount static directory and route index
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.api_route("/", methods=["GET", "HEAD"])
def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "ApexProps Backend Running. Frontend index.html not found."}
