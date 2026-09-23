import sys
import asyncio

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
"""
FastAPI Application for ApexProps MLB & International Baseball Engine.
Serves REST API and hosts the graphical user interface.
"""

from fastapi import FastAPI, Request, Query, Header, HTTPException, Depends, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ScalpConfigUpdate(BaseModel):
    """Validated input model for scalp engine configuration updates."""
    enabled: Optional[bool] = None
    mode: Optional[str] = Field(None, pattern="^(PAPER|LIVE)$")
    price_move_threshold: Optional[float] = Field(None, ge=0.01, le=10.0)
    profit_target: Optional[float] = Field(None, ge=0.01, le=50.0)
    loss_target: Optional[float] = Field(None, ge=0.01, le=50.0)
    take_profit_atr: Optional[float] = Field(None, ge=0.1, le=20.0)
    max_contracts: Optional[int] = Field(None, ge=1, le=500)
    max_trades_per_interval: Optional[int] = Field(None, ge=1, le=50)
    interval_seconds: Optional[int] = Field(None, ge=60, le=86400)
    minimum_conviction: Optional[str] = Field(None, pattern="^(A\\+|A|B\\+|B|C|D)$")

class DirectionEnum(str, Enum):
    ABOVE = "ABOVE"
    BELOW = "BELOW"
    BUY = "BUY"
    SELL = "SELL"
    AI_START = "AI_START"
    YES = "YES"
    NO = "NO"
import os
import time
import math
import json
import threading
import hmac
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from backend.engine.multi_asset_fetcher import fetch_asset_candles, get_asset_ticker
from backend.btc.data_fetcher import get_candle_countdown, get_live_15m_target_data, format_volume_series
from backend.btc.indicators import add_all_indicators
from backend.btc.pattern_detector import detect_candlestick_patterns
from backend.btc.analyzer import analyze_btc
from backend.btc.auto_executor import get_auto_executor

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
    title="BTC 15M Pattern & Confluence Engine",
    version="4.0.0",
    description="Real-time Bitcoin 15-Minute Pattern & Confluence Analyzer."
)

from backend.database.models import init_db
init_db()
from backend.auth.routes import router as auth_router
app.include_router(auth_router)


@app.on_event("startup")
def _setup_socket_exception_handler():
    """Silently catch benign client drops on Windows (e.g. mobile lock screen, Wi-Fi handoff)."""
    try:
        loop = asyncio.get_running_loop()
        def _silent_network_disconnect_handler(loop, context):
            exc = context.get("exception")
            if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
                return
            if isinstance(exc, OSError) and getattr(exc, "winerror", None) in (64, 121, 10053, 10054):
                return
            loop.default_exception_handler(context)
        loop.set_exception_handler(_silent_network_disconnect_handler)
        logger.info("[Startup] Windows socket disconnect handler installed.")
    except Exception as e:
        logger.warning(f"[Startup] Could not set loop exception handler: {e}")

@app.on_event("startup")
def _start_liquidation_feed():
    """C6 FIX: Safe startup hook — won't crash the server if the stream fails."""
    try:
        from backend.btc.liquidation_stream import start_stream as start_liquidation_stream
        start_liquidation_stream()
    except Exception as e:
        logger.warning(f"[Startup] Liquidation stream failed to start: {e}. Trading will continue without live liquidation data.")

# Allowed CORS origins
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "").strip()
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
if not allowed_origins:
    allowed_origins = [
        "http://localhost:8056",
        "http://127.0.0.1:8056",
        "http://localhost:8055",
        "http://127.0.0.1:8055",
        "capacitor://localhost",
        "https://localhost",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Token", "Accept"],
)

# Shared-Secret API Authentication for Sensitive Trading & Scalp Endpoints
# If APP_API_TOKEN is set in the environment, requests must provide a matching X-API-Token header.
# If APP_API_TOKEN is empty/unset, authentication is bypassed for seamless local desktop/LAN use.
API_TOKEN = os.environ.get("APP_API_TOKEN", "").strip()

def require_auth(
    request: Request,
    x_api_token: Optional[str] = Header(None, alias="X-API-Token")
):
    """Shared-secret or JWT authentication dependency."""
    # 1. Try SaaS JWT
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            from backend.auth.security import decode_jwt_token
            payload = decode_jwt_token(token)
            if payload:
                request.state.user_id = payload.get("user_id")
                return
        except Exception:
            pass
            
    # 2. Try Master API Token
    if not API_TOKEN:
        return
    if not x_api_token or not hmac.compare_digest(x_api_token, API_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Token header.")

# ── Guest Session Middleware ──────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from backend.guest_manager import is_valid_guest

class GuestMiddleware(BaseHTTPMiddleware):
    """Extract guest_id from ?guest= query parameter and store on request.state."""
    async def dispatch(self, request: Request, call_next):
        from urllib.parse import parse_qs
        qs = parse_qs(request.url.query)
        guest_id = (qs.get("guest") or [None])[0]
        if guest_id:
            if not is_valid_guest(guest_id):
                return JSONResponse({"error": "Invalid guest token"}, status_code=401)
            request.state.guest_id = guest_id
        else:
            request.state.guest_id = None
        response = await call_next(request)
        return response

app.add_middleware(GuestMiddleware)

def _get_guest_id(request: Request) -> Optional[str]:
    """Helper to extract guest_id from request.state (set by middleware or JWT auth)."""
    # First check if the JWT auth set a user_id
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return str(user_id)
    # Fallback to the ?guest= query parameter middleware
    return getattr(request.state, "guest_id", None)

def require_owner(request: Request):
    """Dependency that blocks guest users from owner-only operations."""
    guest_id = _get_guest_id(request)
    if guest_id:
        raise HTTPException(status_code=403, detail="This operation is not available in guest mode.")


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
    return {"status": "ok", "version": "4.1.0", "service": "BTC 15M Engine"}

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
            "matchup": f"{match.get('away_team', {}).get('name', 'Unknown')} vs {match.get('home_team', {}).get('name', 'Unknown')}",
            "h2h_history": match.get("h2h_history")
        }
    return JSONResponse({"error": "Game not found", "game_id": game_id}, status_code=404)

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
                "odds": dk_data,
                "draftkings": dk_data
            })
    return {
        "count": len(odds_list),
        "provider": "The Odds API",
        "logo": draftkings_client.logo,
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
        "server_time": datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M:%S %p ET").lstrip("0"),
        "live_count": len(live_games),
        "games": live_games
    }

btc_timeframe_cache: Dict[str, Any] = {}
_btc_cache_lock = threading.Lock()

def get_cached_btc_analysis(asset: str = "BTC", timeframe: str = "15m", max_age_seconds: int = 10):
    """Retrieve or compute BTC analysis with smart per-timeframe caching."""
    now = time.time()
    tf = timeframe.lower()
    with _btc_cache_lock:
        if f"{asset}_{tf}" in btc_timeframe_cache and (now - btc_timeframe_cache[f"{asset}_{tf}"]["last_fetched"]) < max_age_seconds:
            if btc_timeframe_cache[f"{asset}_{tf}"].get("df") is not None:
                return btc_timeframe_cache[f"{asset}_{tf}"]["df"], btc_timeframe_cache[f"{asset}_{tf}"]["analysis"]

        try:
            df = fetch_asset_candles(asset, timeframe=tf, limit=1000)
            analysis = analyze_btc(df, asset=asset, timeframe=tf)
            analysis["generated_at"] = datetime.now(timezone.utc).isoformat()
            
            btc_timeframe_cache[f"{asset}_{tf}"] = {
                "df": df,
                "analysis": analysis,
                "last_fetched": time.time()
            }
            return df, analysis
        except Exception as e:
            logger.error(f"Error fetching live BTC candles for {tf}: {e}")
            if f"{asset}_{tf}" in btc_timeframe_cache and btc_timeframe_cache[f"{asset}_{tf}"].get("df") is not None:
                return btc_timeframe_cache[f"{asset}_{tf}"]["df"], btc_timeframe_cache[f"{asset}_{tf}"]["analysis"]
            raise e

def sanitize_btc_json(val):
    """Recursively convert NumPy scalars/types to standard Python types for JSON serialization.

    Also strips NaN/Infinity floats (-> None), since Python's json module emits the
    non-standard `NaN`/`Infinity` tokens for these, which are NOT valid JSON and will
    throw a SyntaxError in the browser's JSON.parse().
    """
    if isinstance(val, dict):
        return {k: sanitize_btc_json(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple)):
        return [sanitize_btc_json(v) for v in val]
    elif hasattr(val, "item"):
        val = val.item()

    if isinstance(val, pd.Timestamp):
        return str(val)
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return 0.0
    return val

@app.get("/api/engine/{asset}/analyze")
def api_btc_analyze(asset: str, timeframe: str = "15m"):
    """Returns comprehensive directional analysis, score, and trade setup for selected timeframe."""
    from backend.forex.auto_executor import ACTIVE_PAIRS
    if asset in ACTIVE_PAIRS:
        from backend.forex.analyzer import analyze_forex_pair
        analysis = analyze_forex_pair(asset, timeframe)
        # Adapt keys to match UI expectations
        price = analysis.get("price", 1.0)
        signal = analysis.get("signal", "HOLD")
        tp = analysis.get("tp") or price
        sl = analysis.get("sl") or price
        dir_ui = "ABOVE" if signal == "BUY" else ("BELOW" if signal == "SELL" else "HOLD")
        bias = "UP" if signal == "BUY" else ("DOWN" if signal == "SELL" else "NEUTRAL")
        prob_pct = int(analysis.get("ml_probability", 0.5) * 100)

        forex_dict = {
            "price": price,
            "direction": dir_ui,
            "primary_bias": bias,
            "predicted_probability": analysis.get("ml_probability", 0.5),
            "confidence_percent": prob_pct,
            "confluence_score": 75 if signal in ["BUY", "SELL"] else 50,
            "conviction_grade": "A" if signal in ["BUY", "SELL"] else "NEUTRAL",
            "catalysts": analysis.get("reasons", []),
            "reasons_bullish": analysis.get("reasons", []) if signal == "BUY" else [],
            "reasons_bearish": analysis.get("reasons", []) if signal == "SELL" else [],
            "trade_setup": {
                "entry_price": price,
                "entry_zone": price,
                "stop_loss": sl,
                "take_profit_1": tp
            },
            "ticker": {"price": price},
            "indicators": analysis.get("indicators", {}),
            "market_structure": {},
            "target_benchmark": {
                "current_price": price,
                "target_price": tp,
                "distance_pct": round(((price - tp) / tp) * 100, 4) if tp else 0.0,
                "time_remaining_str": "FOREX",
                "next_contract_forecast": {
                    "direction": dir_ui,
                    "recommendation": f"Session: {analysis.get('session', 'N/A')} ({signal})",
                    "probability_percent": prob_pct,
                    "conviction_badge": "ML GATE",
                    "conviction_grade": "A",
                    "primary_edge": f"SMC / {analysis.get('session', 'N/A')}",
                    "target_settlement_zone": f"SL: {sl:.5f} | TP: {tp:.5f}",
                    "catalysts": analysis.get("reasons", [])
                }
            }
        }
        return JSONResponse(sanitize_btc_json(forex_dict))

    try:
        _, analysis = get_cached_btc_analysis(asset=asset, timeframe=timeframe)
        return JSONResponse(sanitize_btc_json(analysis))
    except Exception as e:
        static_backup = os.path.join(STATIC_DIR, "data", "btc_analysis.json")
        if os.path.exists(static_backup):
            try:
                with open(static_backup, "r", encoding="utf-8") as f:
                    return JSONResponse(json.load(f))
            except Exception as e:
                logger.warning(f"Failed to load static backup: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/engine/{asset}/prediction/accuracy/reset")
def api_btc_prediction_accuracy_reset(asset: str):
    """Reset prediction accuracy tracker by marking past trades ineligible."""
    try:
        get_auto_executor(asset).reset_prediction_accuracy()
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.error(f"[API] Error resetting prediction accuracy: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/api/engine/{asset}/prediction/accuracy")
def api_btc_prediction_accuracy(asset: str):
    """Return accuracy based only on settled automated Kalshi predictions."""
    try:
        from backend.btc.auto_executor import get_auto_executor
        trades = get_auto_executor(asset).get_trades_history()
        get_auto_executor(asset).check_settlements(trades)
        accuracy = get_auto_executor(asset).get_prediction_accuracy(trades)
        latest = accuracy.get("recent_outcomes", [])[-1] if accuracy.get("recent_outcomes") else None
        return JSONResponse({
            "accuracy": accuracy,
            "forecast": {
                "direction": latest.get("predicted"),
                "generated_at": latest.get("time"),
                "conviction_grade": latest.get("conviction_grade"),
                "confidence": latest.get("confidence"),
            } if latest else None,
            "trade": latest,
            "correct": bool(latest.get("correct")) if latest else False,
        })
    except Exception as e:
        logger.error(f"[API] Error in prediction accuracy endpoint: {e}")
        return JSONResponse({
            "accuracy": {"total_evaluated": 0, "correct_picks": 0, "ratio_text": "0 of 0 Correct", "recent_outcomes": []},
            "forecast": None,
            "trade": None,
            "correct": False,
            "error": str(e)
        }, status_code=500)

@app.get("/api/engine/{asset}/live")
def api_btc_live(asset: str):
    """
    Ultra-low latency endpoint returning live price, 15m target benchmark,
    spread delta, 5-target trend box, and candle countdown for 1s polling.
    Autonomous rollover execution is handled in a dedicated background worker.
    """
    try:
        from backend.forex.auto_executor import ACTIVE_PAIRS
        if asset.upper() in ACTIVE_PAIRS:
            from backend.forex.data_fetcher import get_forex_ticker
            from backend.btc.data_fetcher import get_candle_countdown
            from backend.forex.analyzer import analyze_forex_pair
            
            ticker = get_forex_ticker(asset.upper())
            curr_price = float(ticker.get("price", 1.0))
            analysis = analyze_forex_pair(asset.upper(), "15m")
            tp = float(analysis.get("tp") or curr_price)
            delta = round(curr_price - tp, 5)
            delta_pct = round((delta / tp) * 100, 4) if tp else 0.0
            cd = get_candle_countdown("15m")
            
            data = {
                "price": curr_price,
                "target_price": tp,
                "target_source": f"Forex {analysis.get('session', 'NY')}",
                "delta": delta,
                "delta_pct": delta_pct,
                "status": "ABOVE" if delta >= 0 else "BELOW",
                "seconds_left": cd["seconds_left"],
                "formatted_countdown": cd["formatted"],
                "last_5_targets": [tp],
                "streak_summary": f"Forex AI {analysis.get('signal', 'HOLD')}",
                "volume_24h": float(ticker.get("volume_24h", 0)),
                "kalshi": {
                    "is_synthetic": False,
                    "source": "Forex Spot Engine",
                    "yes_prob": int(analysis.get("ml_probability", 0.5) * 100),
                    "no_prob": 100 - int(analysis.get("ml_probability", 0.5) * 100),
                    "volume_24h": 0
                }
            }
            return JSONResponse(sanitize_btc_json(data))

        data = get_live_15m_target_data(asset.upper())
        return JSONResponse(sanitize_btc_json(data))
    except Exception as e:
        return JSONResponse({
            "price": 0.0,
            "target_price": 0.0,
            "target_source": "--",
            "delta": 0.0,
            "delta_pct": 0.0,
            "status": "NEUTRAL",
            "seconds_left": 0,
            "formatted_countdown": "--:--",
            "last_5_targets": [],
            "streak_summary": "--",
            "error": str(e)
        }, status_code=500)

@app.get("/api/engine/{asset}/ticker")
def api_btc_ticker(asset: str):
    """Returns live 24h ticker info."""
    try:
        from backend.forex.auto_executor import ACTIVE_PAIRS
        if asset.upper() in ACTIVE_PAIRS:
            from backend.forex.data_fetcher import get_forex_ticker
            return JSONResponse(sanitize_btc_json(get_forex_ticker(asset.upper())))
        ticker = get_asset_ticker(asset.upper())
        return JSONResponse(sanitize_btc_json(ticker))
    except Exception as e:
        static_backup = os.path.join(STATIC_DIR, "data", "btc_ticker.json")
        if os.path.exists(static_backup):
            try:
                with open(static_backup, "r", encoding="utf-8") as f:
                    return JSONResponse(json.load(f))
            except Exception as e:
                logger.warning(f"Failed to load static backup: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/engine/{asset}/countdown")
def api_btc_countdown(asset: str, timeframe: str = "15m"):
    """Returns countdown to current candle close for selected timeframe."""
    try:
        return JSONResponse(sanitize_btc_json(get_candle_countdown(timeframe=timeframe)))
    except Exception as e:
        logger.error(f"Error in countdown: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/engine/{asset}/kalshi")
def api_btc_kalshi(asset: str):
    """Returns active Kalshi 15M target strike and market odds."""
    try:
        from backend.forex.auto_executor import ACTIVE_PAIRS
        if asset.upper() in ACTIVE_PAIRS:
            from backend.forex.data_fetcher import get_forex_ticker
            from backend.forex.analyzer import analyze_forex_pair
            ticker = get_forex_ticker(asset.upper())
            p = float(ticker.get("price", 1.0))
            analysis = analyze_forex_pair(asset.upper(), "15m")
            tp = float(analysis.get("tp") or p)
            sl = float(analysis.get("sl") or p)
            ml_p = float(analysis.get("ml_probability", 0.5))
            buy_prob = int(round(ml_p * 100))
            sell_prob = 100 - buy_prob
            pair_fmt = f"{asset.upper()[:3]}/{asset.upper()[3:]}"
            return JSONResponse({
                "status": "active",
                "ticker": f"{pair_fmt} · SPOT FX",
                "target_price": tp,
                "entry_price": p,
                "sl_price": sl,
                "tp_price": tp,
                "yes_prob": buy_prob,
                "no_prob": sell_prob,
                "is_synthetic": False,
                "source": "Forex Spot Engine"
            })
        from backend.btc.kalshi_client import get_kalshi_15m_market
        data = get_kalshi_15m_market(series_ticker=f"KX{asset.upper()}15M")
        if not data:
            return JSONResponse({"status": "unavailable", "target_price": None, "is_synthetic": True})
        data = dict(data)
        data["is_synthetic"] = (data.get("status") == "synthetic") or (data.get("source") == "Kalshi Synthetic")
        try:
            _, analysis = get_cached_btc_analysis(asset=asset, timeframe="15m")
            data["ml_reasoning"] = sanitize_btc_json(analysis)
        except:
            pass
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e), "target_price": None, "is_synthetic": True}, status_code=500)

@app.get("/api/engine/{asset}/kalshi/orderbook")
@app.get("/api/engine/{asset}/kalshi/pricebook")
def api_btc_kalshi_orderbook(asset: str):
    """Returns top-of-book market depth, spread, bid/ask sizes and order imbalance."""
    try:
        from backend.btc.kalshi_client import get_kalshi_15m_market
        data = get_kalshi_15m_market(series_ticker=f"KX{asset.upper()}15M")
        if not data:
            return JSONResponse({"status": "unavailable", "bids": [], "asks": [], "is_synthetic": True})
        
        is_synthetic = (data.get("status") == "synthetic") or (data.get("source") == "Kalshi Synthetic")
        yes_bid = data.get("yes_bid", 0.0)
        yes_ask = data.get("yes_ask", 0.0)
        no_bid = data.get("no_bid", 0.0)
        no_ask = data.get("no_ask", 0.0)
        spread = data.get("spread", 0.04)
        yes_bid_size = data.get("yes_bid_size", 0)
        yes_ask_size = data.get("yes_ask_size", 0)
        imbalance = data.get("orderbook_imbalance", 0.0)
        bias = data.get("market_bias", "NEUTRAL")

        return JSONResponse({
            "ticker": data.get("ticker", ""),
            "target_price": data.get("target_price", 0.0),
            "yes_prob": data.get("yes_prob", 50.0),
            "no_prob": data.get("no_prob", 50.0),
            "is_synthetic": is_synthetic,
            "top_of_book": {
                "yes_bid": yes_bid,
                "yes_ask": yes_ask,
                "no_bid": no_bid,
                "no_ask": no_ask,
                "yes_bid_size": yes_bid_size,
                "yes_ask_size": yes_ask_size,
                "spread": spread,
                "spread_cents": round(spread * 100, 1),
                "orderbook_imbalance_percent": imbalance,
                "market_bias": bias,
                "is_synthetic": is_synthetic
            },
            "bids": [{"side": "YES", "price": yes_bid, "size": yes_bid_size}, {"side": "NO", "price": no_bid, "size": 0}],
            "asks": [{"side": "YES", "price": yes_ask, "size": yes_ask_size}, {"side": "NO", "price": no_ask, "size": 0}],
            "timestamp": int(time.time())
        })
    except Exception as e:
        return JSONResponse({"error": str(e), "is_synthetic": True}, status_code=500)

# =====================================================================
# AUTONOMOUS KALSHI TRADING REST ENDPOINTS
# =====================================================================

@app.get("/api/engine/{asset}/trade/status", dependencies=[Depends(require_auth)])
def api_btc_trade_status(asset: str, request: Request):
    """Returns full status of the automated trading engine."""
    try:
        from backend.forex.auto_executor import ACTIVE_PAIRS
        if asset.upper() in ACTIVE_PAIRS:
            from backend.forex.auto_executor import _is_running
            from backend.forex.paper_trader import get_balance, get_open_positions, get_trade_history, calculate_pip_value
            from backend.forex.data_fetcher import get_forex_ticker
            
            balance = get_balance()
            open_pos = get_open_positions()
            history = get_trade_history()
            
            ticker = get_forex_ticker(asset.upper())
            curr_price = float(ticker.get("price", 1.0))
            pip_decimal = 0.01 if "JPY" in asset.upper() else 0.0001
            
            open_pnl = 0.0
            annotated_open = []
            for p in open_pos:
                pos = dict(p)
                entry = float(pos.get("entry_price", curr_price))
                size = int(pos.get("size", 10000))
                pips = ((curr_price - entry) if pos.get("side") == "BUY" else (entry - curr_price)) / pip_decimal
                pip_val = calculate_pip_value(pos.get("pair", asset.upper()), size, curr_price)
                live_pnl = round(pips * (pip_val / pip_decimal) * pip_decimal, 2)
                pos["live_pnl"] = live_pnl
                pos["pips"] = round(pips, 1)
                pos["current_price"] = curr_price
                pos["mode"] = "PAPER"
                open_pnl += live_pnl
                annotated_open.append(pos)
                
            wins = sum(1 for t in history if float(t.get("realized_pnl", 0)) > 0)
            losses = sum(1 for t in history if float(t.get("realized_pnl", 0)) < 0)
            total_closed = len(history)
            win_rate = round((wins / total_closed) * 100, 1) if total_closed > 0 else 0.0
            total_pnl = round(sum(float(t.get("realized_pnl", 0)) for t in history), 2)
            
            formatted_trades = []
            for t in annotated_open:
                formatted_trades.append({
                    "id": t.get("id"),
                    "mode": "PAPER",
                    "ticker": f"{t.get('pair')} SPOT",
                    "recommendation": f"{t.get('side')} {(t.get('size', 10000)/100000):.2f} Lots",
                    "side": t.get("side"),
                    "status": "OPEN",
                    "result": "OPEN",
                    "entry_price": t.get("entry_price"),
                    "count": f"{(t.get('size', 10000)/100000):.2f} Lots",
                    "lots": round(t.get('size', 10000)/100000, 2),
                    "pnl": t.get("live_pnl", 0.0),
                    "live_pnl": t.get("live_pnl", 0.0),
                    "pips": t.get("pips", 0.0),
                    "created_at": t.get("opened_at", "")
                })
            for t in history[:10]:
                is_win = float(t.get("realized_pnl", 0)) > 0
                formatted_trades.append({
                    "id": t.get("id"),
                    "mode": "PAPER",
                    "ticker": f"{t.get('pair')} SPOT",
                    "recommendation": f"{t.get('side')} {(t.get('size', 10000)/100000):.2f} Lots",
                    "side": t.get("side"),
                    "status": "CLOSED",
                    "result": "WIN" if is_win else "LOSS",
                    "entry_price": t.get("entry_price"),
                    "count": f"{(t.get('size', 10000)/100000):.2f} Lots",
                    "lots": round(t.get('size', 10000)/100000, 2),
                    "pnl": t.get("realized_pnl", 0.0),
                    "live_pnl": t.get("realized_pnl", 0.0),
                    "created_at": t.get("closed_at", "")
                })

            pair_fmt = f"{asset.upper()[:3]}/{asset.upper()[3:]}"
            return JSONResponse({
                "enabled": _is_running,
                "mode": "PAPER",
                "asset": asset.upper(),
                "balance_dollars": balance,
                "balance": balance,
                "equity": round(balance + open_pnl, 2),
                "open_pnl_dollars": round(open_pnl, 2),
                "total_pnl_dollars": total_pnl,
                "win_rate_pct": win_rate,
                "wins": wins,
                "losses": losses,
                "trades_count": total_closed,
                "open_trades": annotated_open,
                "recent_trades": formatted_trades,
                "active_market": {
                    "ticker": f"{pair_fmt} · SPOT FX",
                    "yes_bid": 1.0,
                    "no_bid": 1.0
                },
                "market_type": "SPOT"
            })

        guest_id = _get_guest_id(request)
        status = get_auto_executor(asset, guest_id=guest_id).get_status()
        if guest_id:
            status["is_guest"] = True
            status["mode"] = "PAPER"
        return JSONResponse(sanitize_btc_json(status))
    except Exception as e:
        return JSONResponse({"error": str(e), "enabled": False, "mode": "PAPER"}, status_code=500)

@app.post("/api/engine/{asset}/trade/toggle", dependencies=[Depends(require_auth)])
def api_btc_trade_toggle(asset: str, enabled: bool = Query(...), request: Request = None):
    """Toggle auto-trading execution ON or OFF."""
    try:
        from backend.forex.auto_executor import ACTIVE_PAIRS
        if asset.upper() in ACTIVE_PAIRS:
            from backend.forex.auto_executor import start_forex_executor, stop_forex_executor
            if enabled:
                start_forex_executor()
            else:
                stop_forex_executor()
            return JSONResponse({"status": "ok", "enabled": enabled})

        guest_id = _get_guest_id(request) if request else None
        user_id = getattr(request.state, "user_id", None) if request else None
        
        # Determine the target ID (SaaS user or Guest)
        target_id = user_id if user_id else guest_id
        
        res = get_auto_executor(asset, guest_id=target_id).set_enabled(enabled)
        
        if target_id:
            from backend.database.models import update_user_ai_enabled
            update_user_ai_enabled(target_id, enabled)
            
        return JSONResponse(res)
    except Exception as e:
        return JSONResponse({"success": False, "error": f"Toggle error: {str(e)}"}, status_code=500)

@app.post("/api/engine/{asset}/trade/mode", dependencies=[Depends(require_auth)])
def api_btc_trade_mode(asset: str, mode: str = Query(...), request: Request = None):
    """Switch trading mode between PAPER (simulation) and LIVE (real money)."""
    guest_id = _get_guest_id(request) if request else None

    if guest_id:
        if str(mode).upper() == "LIVE":
            raise HTTPException(status_code=403, detail="Guest users cannot switch to LIVE trading mode.")
        res = get_auto_executor(asset, guest_id=guest_id).set_mode("PAPER")
        return JSONResponse(res)
    # FIX #7: The previous guard `not API_TOKEN` was dead code — require_auth already
    # blocks the request with HTTP 401 when APP_API_TOKEN is empty.
    # Replace with a meaningful check: LIVE mode also requires Kalshi credentials.
    if str(mode).upper() == "LIVE" and not get_auto_executor(asset).mode == "LIVE":
        from backend.btc.kalshi_trader import kalshi_trader as _kt
        if not _kt.is_authenticated():
            raise HTTPException(
                status_code=403,
                detail="Kalshi API credentials must be configured before switching to LIVE trading."
            )
    res = get_auto_executor(asset).set_mode(mode)
    return JSONResponse(res)

@app.post("/api/engine/{asset}/trade/prediction_mode", dependencies=[Depends(require_auth)])
def api_btc_trade_prediction_mode(asset: str, enabled: bool = Query(...), request: Request = None):
    """Toggle prediction mode ON or OFF."""
    guest_id = _get_guest_id(request) if request else None

    get_auto_executor(asset, guest_id=guest_id).prediction_mode = enabled
    get_auto_executor(asset, guest_id=guest_id)._save_config()
    return JSONResponse({"status": "ok", "prediction_mode": enabled})

@app.post("/api/engine/{asset}/trade/threshold", dependencies=[Depends(require_auth)])
def api_btc_trade_threshold(asset: str, threshold: str = Query(...), request: Request = None):
    """Set minimum conviction threshold (e.g. 'A+' or 'A')."""
    guest_id = _get_guest_id(request) if request else None

    res = get_auto_executor(asset, guest_id=guest_id).set_conviction_threshold(threshold)
    return JSONResponse(res)

@app.post("/api/engine/{asset}/trade/contracts", dependencies=[Depends(require_auth)])
def api_btc_trade_contracts(asset: str, count: int = Query(...), request: Request = None):
    """Set number of contracts per trade."""
    guest_id = _get_guest_id(request) if request else None

    res = get_auto_executor(asset, guest_id=guest_id).set_max_contracts(count)


@app.get("/api/engine/{asset}/trade/config", dependencies=[Depends(require_auth)])
def api_btc_trade_config_get(asset: str, request: Request = None):
    """Retrieve the full current configuration from the server (source of truth)."""
    guest_id = _get_guest_id(request) if request else None

    ex = get_auto_executor(asset, guest_id=guest_id)
    return JSONResponse({
        "mode": "PAPER" if guest_id else ex.mode,
        "prediction_mode": ex.prediction_mode,
        "max_daily_risk": ex.max_daily_risk,
        "max_daily_trades": ex.max_daily_trades,
        "min_conviction": ex.min_conviction,
        "max_contracts": ex.max_contracts,
        "enabled": ex.enabled,
        "ai_settings": ex.ai_settings,
        "is_guest": bool(guest_id),
    })

@app.get("/api/engine/{asset}/trade/ai_settings", dependencies=[Depends(require_auth)])
def api_btc_trade_ai_settings_get(asset: str, request: Request = None):
    """Retrieve the current AI settings from the server (source of truth)."""
    guest_id = _get_guest_id(request) if request else None

    return JSONResponse(get_auto_executor(asset, guest_id=guest_id).ai_settings)

def _retrain_ml_engines(data: dict):
    from backend.btc.ml_engine import get_ml_engine
    style = data.get("tradingStyle", "SNIPER")
    # Update settings for all active engine styles
    for st in ["SNIPER", "MOMENTUM_SURFER", "AMBUSH", "CHOP"]:
        eng = get_ml_engine(trading_style=st)
        eng.apply_settings(data)
        
        # Force retraining using historical candles in the background
        try:
            from backend.btc.data_fetcher import fetch_15m_candles_history
            from backend.btc.indicators import add_all_indicators
            hist_df = fetch_15m_candles_history(days=60)
            if hist_df is not None and not hist_df.empty:
                df_ind = add_all_indicators(hist_df)
                eng.self_train_on_historical_market(df_ind)
        except Exception as e:
            pass

@app.post("/api/engine/{asset}/trade/ai_settings", dependencies=[Depends(require_auth)])
async def api_btc_trade_ai_settings(asset: str, request: Request, background_tasks: BackgroundTasks):
    try:
        guest_id = _get_guest_id(request)
        data = await request.json()
        res = get_auto_executor(asset, guest_id=guest_id).set_ai_settings(data)
        if not guest_id:
            # Only retrain ML engines for owner, not guests
            background_tasks.add_task(_retrain_ml_engines, data)
        return JSONResponse({"status": "ok", "settings": data})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})

@app.post("/api/engine/{asset}/trade/risk_limits", dependencies=[Depends(require_auth)])
def api_btc_trade_risk_limits(asset: str, 
    max_daily_risk: Optional[float] = Query(None),
    max_daily_trades: Optional[int] = Query(None),
    request: Request = None
):
    """Set maximum daily risk ($) and maximum daily trades."""
    guest_id = _get_guest_id(request) if request else None

    res = get_auto_executor(asset, guest_id=guest_id).set_risk_limits(max_daily_risk=max_daily_risk, max_daily_trades=max_daily_trades)
    return JSONResponse(res)

@app.post("/api/engine/{asset}/trade/manual", dependencies=[Depends(require_auth)])
def api_btc_trade_manual(asset: str, direction: DirectionEnum = Query(...), lots: Optional[float] = Query(None), request: Request = None):
    """1-Click manual execution for Spot BUY/SELL or Binary ABOVE/BELOW."""
    try:
        from backend.forex.auto_executor import ACTIVE_PAIRS
        if asset.upper() in ACTIVE_PAIRS:
            from backend.forex.paper_trader import open_position
            from backend.forex.data_fetcher import get_forex_ticker
            from backend.forex.analyzer import analyze_forex_pair
            
            side = "BUY" if direction.value in ["BUY", "ABOVE"] else "SELL"
            ticker = get_forex_ticker(asset.upper())
            curr_price = float(ticker.get("price", 1.0))
            analysis = analyze_forex_pair(asset.upper(), "15m")
            sl = analysis.get("sl")
            tp = analysis.get("tp")
            size_units = int(round(lots * 100_000)) if lots and lots > 0 else 10000
            lots_fmt = size_units / 100_000
            pos = open_position(asset.upper(), side, size_units, curr_price, sl, tp)
            return JSONResponse({
                "success": True,
                "trade": {
                    "recommendation": f"{side} {lots_fmt:.2f} Lots {asset.upper()}",
                    "side": side,
                    "price": curr_price,
                    "sl": sl,
                    "tp": tp,
                    "lots": lots_fmt
                }
            })

        guest_id = _get_guest_id(request) if request else None

        res = get_auto_executor(asset, guest_id=guest_id).execute_manual_trade(direction.value)
        return JSONResponse(sanitize_btc_json(res))
    except Exception as e:
        return JSONResponse({"success": False, "error": f"Manual trade error: {str(e)}"}, status_code=500)

@app.post("/api/engine/{asset}/trade/reverse", dependencies=[Depends(require_auth)])
def api_btc_trade_reverse(asset: str, request: Request = None):
    """1-Click manual reverse of open position."""
    try:
        from backend.forex.auto_executor import ACTIVE_PAIRS
        if asset.upper() in ACTIVE_PAIRS:
            from backend.forex.paper_trader import get_open_positions, close_position, open_position
            from backend.forex.data_fetcher import get_forex_ticker
            from backend.forex.analyzer import analyze_forex_pair
            ticker = get_forex_ticker(asset.upper())
            curr_price = float(ticker.get("price", 1.0))
            open_pos = [p for p in get_open_positions() if p["pair"] == asset.upper()]
            if not open_pos:
                return JSONResponse({"success": False, "error": f"No open positions for {asset.upper()} to reverse."})
            last_pos = open_pos[-1]
            old_side = last_pos["side"]
            new_side = "SELL" if old_side == "BUY" else "BUY"
            close_position(last_pos["id"], curr_price, "REVERSE")
            analysis = analyze_forex_pair(asset.upper(), "15m")
            new_pos = open_position(asset.upper(), new_side, last_pos.get("size", 10000), curr_price, analysis.get("sl"), analysis.get("tp"))
            return JSONResponse({"success": True, "trade": new_pos})

        guest_id = _get_guest_id(request) if request else None

        executor = get_auto_executor(asset, guest_id=guest_id)
        trades = executor.get_trades_history()
        open_trades = [t for t in trades if t.get("status") == "OPEN"]
        if not open_trades:
            return JSONResponse({"success": False, "error": "No open trades to reverse."})
        
        trade = open_trades[-1]
        side = trade.get("side", "").upper()
        opposite_dir = "ABOVE" if side == "NO" else "BELOW"
        
        close_res = executor.close_open_trades()
        if not close_res.get("success") and "No open trades" not in str(close_res.get("error", "")):
            return JSONResponse({"success": False, "error": f"Failed to close current trade: {close_res.get('error')}"})
            
        res = executor.execute_manual_trade(opposite_dir)
        return JSONResponse(sanitize_btc_json(res))
    except Exception as e:
        import traceback
        error_msg = f"Reverse Error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return JSONResponse({"success": False, "error": f"Server Error: {str(e)}"})

@app.post("/api/engine/{asset}/trade/close", dependencies=[Depends(require_auth)])
def api_btc_trade_close(asset: str, request: Request = None):
    """1-Click manual close of all open trades."""
    try:
        from backend.forex.auto_executor import ACTIVE_PAIRS
        if asset.upper() in ACTIVE_PAIRS:
            from backend.forex.paper_trader import get_open_positions, close_position
            from backend.forex.data_fetcher import get_forex_ticker
            ticker = get_forex_ticker(asset.upper())
            curr_price = float(ticker.get("price", 1.0))
            open_pos = [p for p in get_open_positions() if p["pair"] == asset.upper()]
            closed = []
            for p in open_pos:
                c = close_position(p["id"], curr_price, "MANUAL_CLOSE")
                if c: closed.append(c)
            return JSONResponse({"success": True, "closed_count": len(closed)})

        guest_id = _get_guest_id(request) if request else None

        res = get_auto_executor(asset, guest_id=guest_id).close_open_trades()
        return JSONResponse(sanitize_btc_json(res))
    except Exception as e:
        return JSONResponse({"success": False, "error": f"Close trade error: {str(e)}"}, status_code=500)

@app.get("/api/engine/{asset}/trade/history", dependencies=[Depends(require_auth)])
def api_btc_trade_history(asset: str, mode: Optional[str] = None, request: Request = None):
    """Returns list of all historical trades and P&L results."""
    from backend.forex.auto_executor import ACTIVE_PAIRS
    if asset.upper() in ACTIVE_PAIRS:
        from backend.forex.paper_trader import get_trade_history
        history = get_trade_history()
        pair_trades = [t for t in history if t.get("pair") == asset.upper()]
        res = []
        for t in pair_trades:
            is_win = float(t.get("realized_pnl", 0)) > 0
            size_units = int(t.get("size", 10000))
            lots = size_units / 100000
            res.append({
                "id": t.get("id"),
                "ticker": f"{t.get('pair')} SPOT",
                "side": t.get("side"),
                "direction": t.get("side"),
                "count": f"{lots:.2f} Lots",
                "entry_price": t.get("entry_price"),
                "exit_price": t.get("close_price"),
                "pnl": t.get("realized_pnl", 0.0),
                "result": "WIN" if is_win else "LOSS",
                "status": "CLOSED",
                "mode": "PAPER",
                "timestamp": t.get("opened_at"),
                "settled_at": t.get("closed_at"),
                "exit_reason": t.get("close_reason", "MANUAL"),
                "recommendation": f"{t.get('side')} {lots:.2f} Lots {t.get('pair')}",
                "conviction_grade": "FOREX AI",
                "conviction_badge": "SPOT FX",
                "catalysts": [f"SL: {t.get('sl', 'N/A')}", f"TP: {t.get('tp', 'N/A')}"]
            })
        return JSONResponse(res)

    guest_id = _get_guest_id(request) if request else None

    history = get_auto_executor(asset, guest_id=guest_id).get_trades_history()
    if mode:
        history = [t for t in history if t.get("mode") == mode.upper()]
    return JSONResponse(sanitize_btc_json(history[::-1]))

@app.get("/api/engine/{asset}/calibration/drift")
def api_btc_calibration_drift(asset: str, min_samples: int = 40, window: int = 100):
    res = get_auto_executor(asset).check_live_calibration_drift(min_samples=min_samples, window=window)
    return JSONResponse(sanitize_btc_json(res))

@app.get("/api/engine/{asset}/mode", dependencies=[Depends(require_auth)])
def api_btc_mode(asset: str, request: Request = None):
    guest_id = _get_guest_id(request) if request else None

    if guest_id:
        return JSONResponse({"mode": "PAPER"})
    return JSONResponse({"mode": get_auto_executor(asset).mode})

@app.get("/api/engine/{asset}/paper/balance", dependencies=[Depends(require_auth)])
def api_btc_paper_balance(asset: str, request: Request = None):
    from backend.btc.paper_balance import load_balance
    guest_id = _get_guest_id(request) if request else None

    return JSONResponse({"balance": load_balance(guest_id=guest_id)})

@app.post("/api/engine/{asset}/paper/balance/reset", dependencies=[Depends(require_auth)])
def api_btc_paper_balance_reset(asset: str, request: Request = None):
    from backend.btc.paper_balance import reset_balance
    guest_id = _get_guest_id(request) if request else None

    new_bal = reset_balance(guest_id=guest_id)
    return JSONResponse({"balance": new_bal})

# ── Scalp Engine Endpoints ────────────────────────────────────────────
from backend.btc.scalp_engine import get_scalp_engine

@app.post("/api/engine/{asset}/scalp/start", dependencies=[Depends(require_auth), Depends(require_owner)])
def api_btc_scalp_start(asset: str):
    """Start the scalp engine background monitor."""
    get_scalp_engine(asset).start()
    return JSONResponse({"status": "scalp engine started"})

@app.post("/api/engine/{asset}/scalp/stop", dependencies=[Depends(require_auth), Depends(require_owner)])
def api_btc_scalp_stop(asset: str):
    """Stop the scalp engine background monitor."""
    get_scalp_engine(asset).stop()
    return JSONResponse({"status": "scalp engine stopped"})

@app.get("/api/engine/{asset}/scalp/config", dependencies=[Depends(require_auth), Depends(require_owner)])
def api_btc_scalp_config(asset: str):
    """Get current scalp engine configuration."""
    return JSONResponse(get_scalp_engine(asset).load_config())

@app.get("/api/engine/{asset}/scalp/status", dependencies=[Depends(require_auth), Depends(require_owner)])
def api_btc_scalp_status(asset: str):
    """Get current scalp engine runtime status and monitored positions."""
    return JSONResponse(get_scalp_engine(asset).get_status())

@app.patch("/api/engine/{asset}/scalp/config", dependencies=[Depends(require_auth), Depends(require_owner)])
async def api_btc_scalp_config_update(asset: str, config: ScalpConfigUpdate):
    """Update scalp engine configuration with validated input."""
    body = config.model_dump(exclude_none=True)
    if not body:
        raise HTTPException(status_code=400, detail="No valid configuration fields provided")
    get_scalp_engine(asset).save_config(body)
    return JSONResponse({"status": "config updated", "config": get_scalp_engine(asset).load_config()})

# ── Guest Admin Endpoints ─────────────────────────────────────────────

@app.post("/api/admin/guests/create", dependencies=[Depends(require_auth), Depends(require_owner)])
async def api_admin_guest_create(request: Request):
    """Create a new guest session. Returns the guest_id and shareable URL."""
    from backend.guest_manager import create_guest
    try:
        body = await request.json()
    except Exception:
        body = {}
    label = body.get("label", "")
    guest = create_guest(label=label)
    # Build a shareable URL
    host = request.headers.get("host", "localhost:8056")
    scheme = "https" if "https" in str(request.url) else "http"
    guest["guest_url"] = f"{scheme}://{host}/?guest={guest['guest_id']}"
    return JSONResponse(guest)

@app.get("/api/admin/guests", dependencies=[Depends(require_auth), Depends(require_owner)])
def api_admin_guest_list():
    """List all guest sessions with balance and trade stats."""
    from backend.guest_manager import list_guests
    return JSONResponse({"guests": list_guests()})

@app.delete("/api/admin/guests/{guest_id}", dependencies=[Depends(require_auth), Depends(require_owner)])
def api_admin_guest_delete(guest_id: str):
    """Delete a guest and all their data."""
    from backend.guest_manager import delete_guest
    success = delete_guest(guest_id)
    if not success:
        raise HTTPException(status_code=404, detail="Guest not found")
    return JSONResponse({"status": "deleted", "guest_id": guest_id})

# ── Guest Identity Endpoint ───────────────────────────────────────────

@app.get("/api/guest/me")
def api_guest_me(request: Request):
    """Returns the current guest identity, or null if not a guest."""
    guest_id = _get_guest_id(request)
    if not guest_id:
        return JSONResponse({"is_guest": False})
    from backend.guest_manager import _load_registry
    registry = _load_registry()
    meta = registry.get(guest_id, {})
    return JSONResponse({
        "is_guest": True,
        "guest_id": guest_id,
        "label": meta.get("label", ""),
    })

@app.get("/api/engine/{asset}/candles")
def api_btc_candles(asset: str, timeframe: str = "15m"):
    """
    Returns formatted candlestick data + indicators + pattern markers + volume series
    for TradingView Lightweight Charts for the selected timeframe.
    """
    from backend.forex.auto_executor import ACTIVE_PAIRS
    
    try:
        is_fx = asset in ACTIVE_PAIRS
        prec = 5 if is_fx else 2

        if is_fx:
            from backend.forex.data_fetcher import fetch_forex_candles
            from backend.btc.indicators import add_all_indicators
            from backend.forex.analyzer import analyze_forex_pair
            df = fetch_forex_candles(asset, timeframe)
            df_ind = add_all_indicators(df)
            fx_analysis = analyze_forex_pair(asset, timeframe)
            analysis = {
                "trade_setup": {
                    "entry_price": fx_analysis.get("price"),
                    "stop_loss": fx_analysis.get("sl"),
                    "take_profit_1": fx_analysis.get("tp")
                },
                "target_benchmark": {
                    "target_price": fx_analysis.get("tp") or fx_analysis.get("price")
                }
            }
        else:
            df, analysis = get_cached_btc_analysis(asset=asset, timeframe=timeframe)
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
                "open": round(float(row["open"]), prec),
                "high": round(float(row["high"]), prec),
                "low": round(float(row["low"]), prec),
                "close": round(float(row["close"]), prec),
            })

            if not pd.isna(row.get("ema_9", None)):
                ema9_data.append({"time": t, "value": round(float(row["ema_9"]), prec)})
            if not pd.isna(row.get("ema_21", None)):
                ema21_data.append({"time": t, "value": round(float(row["ema_21"]), prec)})
            if not pd.isna(row.get("ema_50", None)):
                ema50_data.append({"time": t, "value": round(float(row["ema_50"]), prec)})
            if not pd.isna(row.get("ema_200", None)):
                ema200_data.append({"time": t, "value": round(float(row["ema_200"]), prec)})

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

        if asset in ACTIVE_PAIRS:
            from backend.forex.data_fetcher import get_forex_ticker
            ticker = get_forex_ticker(asset)
        else:
            ticker = get_asset_ticker(asset)
            
        volume_series = format_volume_series(df_ind)
        target_benchmark = analysis.get("target_benchmark", {})

        return JSONResponse(sanitize_btc_json({
            "candles": candles,
            "volume": volume_series,
            "ema9": ema9_data,
            "ema21": ema21_data,
            "ema50": ema50_data,
            "ema200": ema200_data,
            "markers": markers,
            "ticker": ticker,
            "target_price": target_benchmark.get("target_price"),
            "trade_setup": analysis.get("trade_setup"),
            "target_benchmark": target_benchmark
        }))
    except Exception as e:
        static_backup = os.path.join(STATIC_DIR, "data", "btc_candles.json")
        if os.path.exists(static_backup):
            try:
                with open(static_backup, "r", encoding="utf-8") as f:
                    return JSONResponse(json.load(f))
            except Exception as e:
                logger.warning(f"Failed to load static backup: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# =====================================================================
# BACKGROUND AUTO-TRADER TASK & WATCHDOG
# =====================================================================
import threading
_last_autotrader_heartbeat = time.time()

def _auto_trader_background_loop():
    global _last_autotrader_heartbeat
    settle_tick = 0  # Incremented each 2s tick; triggers check_settlements every 5 ticks (10s)
    logger.info("[AutoTrader Worker] Loop started.")
    while True:
        try:
            _last_autotrader_heartbeat = time.time()
            for asset in ["BTC", "ETH", "GOLD"]:
                try:
                    ae = get_auto_executor(asset)
                    ae.check_and_execute_rollover()
                    ae.evaluate_and_execute_saas_users()
                except Exception as e:
                    import traceback
                    logger.error(f"[AutoTrader Loop] Exception for {asset}: {e}")
                    traceback.print_exc()
            settle_tick += 1
            if settle_tick % 5 == 0:  # Fires every 10s (5 ticks * 2s)
                try:
                    from backend.saas_settler import settle_saas_trades, process_auto_force_trades
                    settle_saas_trades()
                    process_auto_force_trades()
                except Exception as e:
                    logger.error(f"[SaaSSettler] execution error: {e}")
                for asset in ["BTC", "ETH", "GOLD"]:
                    try:
                        get_auto_executor(asset).check_settlements()
                    except Exception:
                        pass
            # Check early stop-loss and position reversal on active open positions
            for asset in ["BTC", "ETH", "GOLD"]:
                try:
                    get_auto_executor(asset).check_active_trades_stop_and_reversal()
                except Exception:
                    pass
            _last_autotrader_heartbeat = time.time()
        except Exception as e:
            logger.error(f"[AutoTrader Background] Error in loop: {e}", exc_info=True)
        time.sleep(2)

_autotrader_thread = None

def _watchdog_monitor_loop():
    """Watchdog thread to monitor and revive the auto-trader thread if it terminates."""
    global _last_autotrader_heartbeat, _autotrader_thread
    while True:
        try:
            time.sleep(15)
            stalled_seconds = time.time() - _last_autotrader_heartbeat
            thread_dead = (_autotrader_thread is None or not _autotrader_thread.is_alive())
            if stalled_seconds > 90 and thread_dead:
                logger.warning(
                    f"[AutoTrader Watchdog] Background worker thread terminated (inactive for {stalled_seconds:.1f}s). "
                    f"Reviving worker thread..."
                )
                _last_autotrader_heartbeat = time.time()
                _autotrader_thread = threading.Thread(target=_auto_trader_background_loop, daemon=True, name="AutoTraderRevived")
                _autotrader_thread.start()
            elif stalled_seconds > 90 and not thread_dead:
                logger.warning(
                    f"[AutoTrader Watchdog] Background worker loop delayed ({stalled_seconds:.1f}s) "
                    f"but thread is still alive. Not spawning duplicate worker."
                )
        except Exception as e:
            logger.error(f"[AutoTrader Watchdog] Error: {e}")

# =====================================================================
# FOREX ROUTES & INTEGRATION
# =====================================================================
from backend.forex.auto_executor import start_forex_executor, get_forex_status
from backend.forex.paper_trader import get_balance as get_forex_balance, get_open_positions as get_forex_positions, get_trade_history as get_forex_history
from backend.forex.analyzer import analyze_forex_pair
from backend.forex.data_fetcher import get_forex_ticker

@app.get("/api/forex/trade/status")
def api_forex_status():
    return JSONResponse({
        "status": get_forex_status(),
        "balance": get_forex_balance(),
        "positions": get_forex_positions(),
        "history": get_forex_history()
    })

@app.get("/api/forex/analysis/{pair}")
def api_forex_analysis(pair: str):
    ticker = get_forex_ticker(pair)
    analysis = analyze_forex_pair(pair)
    return JSONResponse({
        "pair": pair,
        "ticker": ticker,
        "analysis": analysis
    })

@app.on_event("startup")
def start_background_tasks():
    global _autotrader_thread
    _autotrader_thread = threading.Thread(target=_auto_trader_background_loop, daemon=True, name="AutoTraderMain")
    _autotrader_thread.start()
    t2 = threading.Thread(target=_watchdog_monitor_loop, daemon=True, name="AutoTraderWatchdog")
    t2.start()
    logger.info("[AutoTrader] Background thread & watchdog monitor started.")
    
    # Start Forex Engine
    start_forex_executor()

# Mount static directory and route index

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/api/ui_version")
def get_ui_version():
    index_path = os.path.join(STATIC_DIR, "index.html")
    mtime = os.path.getmtime(index_path) if os.path.exists(index_path) else 0
    return JSONResponse(
        {"version": "4.1.0", "mtime": mtime},
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

@app.api_route("/", methods=["GET", "HEAD"])
def serve_index():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login.html")

@app.api_route("/trades", methods=["GET", "HEAD"])
@app.api_route("/trade-list", methods=["GET", "HEAD"])
@app.api_route("/trades.html", methods=["GET", "HEAD"])
def serve_trades():
    trades_path = os.path.join(STATIC_DIR, "trades.html")
    if os.path.exists(trades_path):
        return FileResponse(
            trades_path,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return {"message": "Trade list page not found."}



@app.get("/login.html")
def get_login():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "static", "login.html"))

@app.get("/saas_dashboard.html")
@app.get("/saas_dashboard")
def get_saas_dashboard():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "static", "saas_dashboard.html"))
