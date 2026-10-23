from backend.btc.data_fetcher import get_candle_countdown
from enum import Enum

from fastapi import (APIRouter, BackgroundTasks, Depends, HTTPException, Query,
                     Request)


class DirectionEnum(str, Enum):
    ABOVE = "ABOVE"
    BELOW = "BELOW"
    BUY = "BUY"
    SELL = "SELL"
    AI_START = "AI_START"
    YES = "YES"
    NO = "NO"
    AI_FORCE = "AI_FORCE"
    ai_force = "ai_force"

import json
import logging
import math
import os
import re
import sqlite3
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
import uuid

import requests.exceptions
from fastapi.responses import JSONResponse
from backend.sports_bridge.prediction_client import SportsPredictionClient

logger = logging.getLogger(__name__)

import traceback
USE_KALSHI_BRIDGE = True
_fx_cache = {}
import threading
_fx_cache_lock = threading.Lock()
def _cached_analyze_forex_pair(asset, tf):
    key = (asset, tf)
    now = time.time()
    with _fx_cache_lock:
        if key not in _fx_cache or now - _fx_cache[key][0] > 10:
            _fx_cache[key] = (now, analyze_forex_pair(asset, tf))
        return _fx_cache[key][1]

import pandas as pd

import backend.forex.auto_executor as _forex_exec  # read _is_running live, not a stale copy
# Main imports
from backend.auth.dependencies import (STATIC_DIR, _get_guest_id, caller_has_owner_access, require_auth,
                                       require_bot_control, require_owner)
from backend.btc.analysis_cache import (get_cached_btc_analysis,
                                        sanitize_btc_json)
from backend.btc.auto_executor import invalidate_saas_users_cache
from backend.btc.data_fetcher import (format_volume_series,
                                      
                                      get_live_15m_target_data)
from backend.btc.indicators import add_all_indicators
from backend.btc.kalshi_client import get_kalshi_15m_market, get_recent_trades
from backend.btc.kalshi_trader import kalshi_trader as _kt
from backend.btc.paper_balance import load_balance, reset_balance
from backend.btc.pattern_detector import detect_candlestick_patterns
from backend.core.registry import get_auto_executor
from backend.database.models import (enrich_trade_metadata, get_user_by_id,
                                     reset_user_paper_balance_and_pnl,
                                     update_user_ai_enabled,
                                     update_user_config)
from backend.engine.multi_asset_fetcher import get_asset_ticker
from backend.forex.analyzer import analyze_forex_pair
from backend.forex.auto_executor import (ACTIVE_PAIRS, start_forex_executor, stop_forex_executor)
from backend.forex.data_fetcher import fetch_forex_candles, get_forex_ticker
from backend.forex.paper_trader import (calculate_pip_value, close_position, get_balance, get_open_positions, get_trade_history, open_position)
from backend.core.registry import SUPPORTED_ASSETS
from backend.engine.multi_asset_fetcher import fetch_asset_candles



_SPORTS_ASSETS = {
    "SPORTS", "SPORT", "NFL", "MLB", "NBA", "NHL", "NPB", "KBO", "NPB/KBO", "NPB_KBO", "NPB-KBO",
    "SOC", "SOCCER", "UFC", "MMA", "TEN", "TENNIS", "ALL", "WNBA", "NCAAF", "NCAAB"
}

_SPORTS_SERIES_MAP = {
    "NPB": ["KXNPBGAME", "KXNPBSPREAD", "KXNPBTOTAL"],
    "KBO": ["KXKBOGAME", "KXKBOSPREAD", "KXKBOTOTAL"],
    "NFL": ["KXNFLSPREAD", "KXNFLTOTAL", "KXNFLWINS", "KXNFLGAME", "KXNFLTD", "KXNFLPASS", "KXNFLRUSH", "KXNFLREC"],
    "MLB": ["KXMLBGAME", "KXMLBSPREAD", "KXMLBTOTAL", "KXMLBF5", "KXMLBHRR"],
    "NHL": ["KXNHLGAME", "KXNHLSPREAD", "KXNHLTOTAL", "KXNHLTEAMTOTAL", "KXNHLF10G", "KXNHL1P", "KXNHL2P", "KXNHL3P", "KXNHL1PSPREAD", "KXNHL2PSPREAD", "KXNHL3PSPREAD", "KXNHL1PTOTAL", "KXNHL2PTOTAL", "KXNHL3PTOTAL", "KXNHLOT", "KXNHLGOAL", "KXNHLAST", "KXNHLPTS", "KXNHLFIRSTGOAL", "KXNHLSAVE"],
    "SOC": [
        "KXEPLGAME", "KXMLSGAME", "KXUEFAGAME", "KXUCLGAME", "KXWC", "KXBUNDESLIGA", "KXLALIGA",
        "KXMLSTOTAL", "KXUCLTOTAL", "KXEPLTOTAL", "KXLALIGATOTAL", "KXBUNDESLIGATOTAL", "KXSERIEATOTAL",
        "KXLIGUE1TOTAL", "KXLIGAMXTOTAL", "KXEFLCHAMPIONSHIPTOTAL", "KXUSLTOTAL", "KXCONMEBOLLIBTOTAL",
        "KXCONMEBOLSUDTOTAL", "KXARGPREMDIVTOTAL", "KXDIMAYORTOTAL", "KXBRASILEIROTOTAL", "KXEREDIVISIETOTAL",
        "KXSAUDIPLTOTAL", "KXSCOTTISHPREMTOTAL", "KXUELTOTAL", "KXUECLTOTAL",
        "KXMLS1HTOTAL", "KXMLS2HTOTAL", "KXMLSTEAMTOTAL",
        "KXEFLCHAMPIONSHIP1HTOTAL", "KXEFLCHAMPIONSHIP2HTOTAL", "KXEFLCHAMPIONSHIPTEAMTOTAL",
        "KXUCL1HTOTAL", "KXUCL2HTOTAL", "KXUCLTEAMTOTAL",
        "KXCONMEBOLLIB1HTOTAL", "KXCONMEBOLLIB2HTOTAL", "KXCONMEBOLLIBTEAMTOTAL",
        "KXCONMEBOLSUD1HTOTAL", "KXARGPREMDIV1HTOTAL", "KXUSL1HTOTAL",
        "KXEPL1HTOTAL", "KXEPL2HTOTAL", "KXEPLTEAMTOTAL",
        "KXLALIGA1HTOTAL", "KXLALIGA2HTOTAL", "KXLALIGATEAMTOTAL",
        "KXBUNDESLIGA1HTOTAL", "KXBUNDESLIGA2HTOTAL", "KXBUNDESLIGATEAMTOTAL",
        "KXSERIEA1HTOTAL", "KXSERIEA2HTOTAL", "KXSERIEATEAMTOTAL",
        "KXLIGUE11HTOTAL", "KXLIGUE12HTOTAL", "KXLIGUE1TEAMTOTAL"
    ],
    "UFC": ["KXUFCMIDDLEWEIGHTTITLE", "KXUFCLHEAVYWEIGHTTITLE", "KXUFCBANTAMWEIGHTTITLE", "KXUFCFIGHT", "KXUFC"],
    "TEN": ["KXATPMATCH", "KXWTAMATCH", "KXATP", "KXWTA"],
    "NBA": ["KXNBAGAME", "KXNBASPREAD", "KXNBATOTAL", "KXNBAPTS", "KXNBAREB", "KXNBAAST", "KXNBATHREE", "KXNBA3PT", "KXNBABLK", "KXNBASTL"],
    "NCAAF": ["KXNCAAFGAME", "KXNCAAFSPREAD", "KXNCAAFTOTAL"]
}

def _authenticated_user_id(request: Optional[Request]) -> Optional[int]:
    """The user id proven by the caller's login (JWT), or None."""
    if request is None:
        return None
    req_uid = getattr(request.state, "user_id", None)
    if req_uid:
        try:
            return int(req_uid)
        except (ValueError, TypeError):
            pass
    try:
        from backend.auth.dependencies import _extract_jwt
        from backend.auth.security import decode_jwt_token
        token = _extract_jwt(request)
        if token:
            payload = decode_jwt_token(token)
            if payload and payload.get("user_id"):
                return int(payload["user_id"])
    except Exception:
        pass
    return None

def _owner_default_user_id() -> Optional[int]:
    """For the owner on this PC / LAN / master token with no login: the account the
    owner bot trades for (admin first). Never used for other callers."""
    try:
        from backend.database.models import get_all_active_users
        users = get_all_active_users() or []
    except Exception:
        return None
    if not users:
        return None
    def _role(u): return (u.get("role") or "").lower()
    def _mode(u): return (u.get("trading_mode") or "").upper()
    def _univ(u): return (u.get("trading_universe") or "").upper()
    for pick in (
        lambda u: _role(u) == "admin" and _mode(u) == "LIVE" and _univ(u) in ("SPORTS", "BOTH", "ALL"),
        lambda u: _role(u) == "admin",
        lambda u: _mode(u) == "LIVE" and _univ(u) in ("SPORTS", "BOTH", "ALL"),
        lambda u: _mode(u) == "LIVE",
        lambda u: _univ(u) in ("SPORTS", "BOTH", "ALL"),
    ):
        for u in users:
            if pick(u):
                return int(u["id"])
    return int(users[0]["id"])

def _resolve_user_id(user_id: Optional[int], request: Optional[Request] = None) -> Optional[int]:
    """Which account a request acts on."""
    requested = None
    for raw in (
        user_id,
        request.query_params.get("user_id") if request is not None else None,
        request.headers.get("X-User-Id") if request is not None else None,
    ):
        if raw in (None, ""):
            continue
        try:
            requested = int(raw)
            break
        except (ValueError, TypeError):
            continue

    authed = _authenticated_user_id(request)
    is_owner = False
    if request is not None:
        try:
            is_owner = bool(getattr(request.state, "is_owner", False) or caller_has_owner_access(request))
        except Exception:
            is_owner = False
    else:
        is_owner = True

    if requested is not None and requested != authed:
        if is_owner:
            return requested
        logger.warning(f"[Auth] Ignoring client-supplied user_id={requested} (logged in as {authed}).")
    if authed:
        return authed
    if is_owner:
        return _owner_default_user_id()
    return None

def _require_user_id(user_id: Optional[int], request: Optional[Request] = None) -> int:
    """Like _resolve_user_id, but refuses to place an order without a known account."""
    uid = _resolve_user_id(user_id, request)
    if uid:
        if uid == 7:
            authed = _authenticated_user_id(request)
            is_owner = bool(request and (getattr(request.state, "is_owner", False) or caller_has_owner_access(request)))
            if authed != 7 and not is_owner:
                logger.warning(f"[Security] Denied attempt to trade on Vill3.G account (uid=7) by unverified caller (authed={authed})")
                raise HTTPException(status_code=403, detail="Unauthorized: Only the logged-in Vill3.G account can send orders on Vill3.G's Kalshi account.")
        return uid
    if request is not None and _get_guest_id(request):
        raise HTTPException(status_code=403, detail="Sports trades need a signed-in account.")
    raise HTTPException(status_code=401, detail="Session expired. Please log in again.")


def _is_sports_asset(asset: str) -> bool:
    if not asset:
        return False
    a = str(asset).strip().upper()
    if a in _SPORTS_ASSETS:
        return True
    if '_SPORTS_SERIES_MAP' in globals() and a in _SPORTS_SERIES_MAP:
        return True
    return False

def _validate_asset(request: Request):
    """Reject unknown /{asset} path values with 404 instead of a 500."""
    asset = str(request.path_params.get("asset", "") or "").upper().strip()
    if asset and asset not in SUPPORTED_ASSETS and asset not in ACTIVE_PAIRS and not _is_sports_asset(asset):
        raise HTTPException(status_code=404, detail=f"Unknown asset '{asset}'")




from fastapi import APIRouter
sports_router = APIRouter()

def _get_user_sports_criteria(user_id: int) -> dict:
    try:
        from backend.database.models import get_db_connection
        conn = get_db_connection()
        row = conn.execute("SELECT min_sports_confidence, min_sports_edge, sports_max_wager, sports_trade_size_dollars FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        if row:
            wager = row[3] if (len(row) > 3 and row[3] is not None) else (row[2] if row[2] is not None else 10.0)
            return {
                "min_confidence": float(row[0]) if row[0] is not None else 50.0,
                "min_edge": float(row[1]) if row[1] is not None else 0.0,
                "max_wager": float(wager) if wager is not None else 10.0,
                "trade_size_dollars": float(wager) if wager is not None else 10.0
            }
    except Exception:
        pass
    return {"min_confidence": 50.0, "min_edge": 0.0, "max_wager": 10.0, "trade_size_dollars": 10.0}

def _execute_sports_trade(
    event_ticker: str,
    prediction: dict,
    user_id: int,
    trade_size: Optional[float] = None,
    explicit_side: Optional[str] = None,
    combo_id: Optional[str] = None,
    combo_info: Optional[dict] = None
) -> tuple[Optional[dict], Optional[str]]:
    import requests
    import uuid
    import re
    from backend.database.trade_store import TradeStore

    if not event_ticker or not str(event_ticker).strip():
        return None, "Invalid or missing event_ticker"
    if not prediction:
        return None, "Missing prediction data"

    from backend.database.models import get_user_by_id
    user = get_user_by_id(user_id)
    if not user:
        return None, f"User {user_id} not found"

    mode = (user.get("trading_mode") or "PAPER").upper()

    event_ticker = str(event_ticker).strip()
    market_ticker = None
    entry_price = 0.50
    side = (explicit_side or "YES").upper()

    if event_ticker.startswith("KALSHI-") and mode == "LIVE":
        return None, f"Trade execution failed: Cannot place live order on non-Kalshi ticker '{event_ticker}'"

    now_et = datetime.now(ZoneInfo("America/New_York"))
    today_et = now_et.date()
    ev_date, start_epoch = extract_sports_event_date_and_time(
        event_ticker,
        metadata=prediction.get("metadata") if isinstance(prediction, dict) else None
    )
    if mode == "LIVE":
        if ev_date and ev_date < today_et:
            return None, f"Trade execution failed: Event '{event_ticker}' scheduled date ({ev_date}) is in the past"
        if start_epoch and (time.time() - start_epoch > 14400):
            return None, f"Trade execution failed: Event '{event_ticker}' already concluded"

    try:
        headers = {"Accept": "application/json", "User-Agent": "ApexProps-Trader/1.0"}
        from backend.btc.kalshi_trader import kalshi_trader
        if kalshi_trader.is_authenticated():
            try:
                headers = kalshi_trader._sign_headers("GET", f"/trade-api/v2/events/{event_ticker}")
            except Exception:
                pass
        r = requests.get(
            f"https://external-api.kalshi.com/trade-api/v2/events/{event_ticker}",
            params={"with_nested_markets": True},
            headers=headers,
            timeout=5.0
        )
        if r.status_code == 200:
            evt = r.json().get("event", {})
            markets = evt.get("markets", [])
            if not markets:
                logger.warning(f"Event {event_ticker} has no open markets on Kalshi.")
                return None, f"Trade execution failed: Event {event_ticker} has no open markets on Kalshi"

            pred_team_raw = (prediction.get("predicted_team") or prediction.get("team") or "").strip()
            meta = prediction.get("metadata") or {}
            meta_name = (meta.get("name") or meta.get("player_or_team") or meta.get("home_team") or "").strip()

            # Clean off "(Manual YES)" or "(Manual NO)" if present
            pred_team = re.sub(r'\(?\b(?:manual\s+yes|yes\s*\(manual\)|manual\s+no|no\s*\(manual\)|manual|yes|no)\b\)?', '', pred_team_raw, flags=re.IGNORECASE).strip().lower()
            if not pred_team and meta_name:
                pred_team = meta_name.lower().strip()

            generic_words = {'the', 'and', 'city', 'team', 'club', 'fc', 'vs', 'game', 'wins', 'at', 'in'}
            pred_tokens = {w for w in re.findall(r'[a-z0-9]+', pred_team) if len(w) >= 3 and w not in generic_words}
            meta_tokens = {w for w in re.findall(r'[a-z0-9]+', meta_name.lower()) if len(w) >= 3 and w not in generic_words}
            all_target_tokens = pred_tokens | meta_tokens

            matched_m = None
            best_score = 0
            
            if (not pred_team or pred_team in ("yes", "no")) and len(markets) > 0:
                matched_m = markets[0]
                if not explicit_side and pred_team in ("yes", "no"):
                    side = pred_team.upper()
                best_score = 100
            else:
                for m in markets:
                    m_ticker = (m.get("ticker") or "").lower()
                    m_title = (m.get("title") or "").lower()
                    m_sub = (m.get("yes_sub_title") or "").lower()
                    m_text = f"{m_ticker} {m_title} {m_sub}"
                    m_tokens = {w for w in re.findall(r'[a-z0-9]+', m_text) if len(w) >= 3 and w not in generic_words}

                    score = 0
                    if pred_team and (pred_team in m_title or pred_team in m_sub):
                        score += 25
                    if m_sub and len(m_sub) >= 4 and m_sub in pred_team:
                        score += 20
                    if meta_name and (meta_name.lower() in m_title or meta_name.lower() in m_sub):
                        score += 15

                    overlap = len(all_target_tokens & m_tokens)
                    score += overlap * 10

                    for tok in all_target_tokens:
                        if len(tok) >= 3:
                            if any(mt.startswith(tok) or tok.startswith(mt) for mt in m_tokens):
                                score += 6
                            if m_ticker.endswith("-" + tok) or f"-{tok}-" in m_ticker:
                                score += 12

                    if score > best_score:
                        best_score = score
                        matched_m = m

            # If there is only 1 binary market and pred_team didn't match YES, check if it matches opponent (NO side)
            if not matched_m and len(markets) == 1:
                m = markets[0]
                m_sub = (m.get("yes_sub_title") or "").lower()
                m_tokens = {w for w in re.findall(r'[a-z0-9]+', m_sub) if len(w) >= 3 and w not in generic_words}
                evt_title_sub = f"{evt.get('title', '')} {evt.get('sub_title', '')} {m.get('title', '')}".lower()
                if all_target_tokens and any(tok in evt_title_sub for tok in all_target_tokens) and not (all_target_tokens & m_tokens):
                    matched_m = m
                    side = "NO"
                    best_score = 5

            # If still not matched, but explicit_side was passed and we have markets, fall back to markets[0]
            if (not matched_m or best_score <= 0) and explicit_side and len(markets) > 0:
                matched_m = markets[0]
                side = explicit_side
                best_score = 1

            if not matched_m or best_score <= 0:
                logger.warning(f"Could not match predicted team '{pred_team}' to any market in event {event_ticker}")
                return None, f"Trade execution failed: Could not match predicted team '{pred_team}' in event {event_ticker}"

            m_status = str(matched_m.get("status") or "").lower()
            if m_status in ("closed", "settled", "determined"):
                return None, f"Trade execution failed: Market '{matched_m.get('ticker')}' is {m_status} (cannot place order on closed market)"
            if mode == "LIVE" and m_status not in ("active", "open"):
                return None, f"Trade execution failed: Market '{matched_m.get('ticker')}' is {m_status} (cannot place live order on closed market)"

            market_ticker = matched_m.get("ticker")
            
            # Price guard: skip any market where yes_ask + no_ask < 0.9 or either price <= 0.01 (unless longshot with bid)
            m_ya = float(matched_m.get("yes_ask_dollars") or matched_m.get("yes_ask") or 0.0)
            m_na = float(matched_m.get("no_ask_dollars") or matched_m.get("no_ask") or 0.0)
            m_yb = float(matched_m.get("yes_bid_dollars") or matched_m.get("yes_bid") or 0.0)
            m_nb = float(matched_m.get("no_bid_dollars") or matched_m.get("no_bid") or 0.0)
            if m_ya > 1.0: m_ya /= 100.0
            if m_na > 1.0: m_na /= 100.0
            if m_yb > 1.0: m_yb /= 100.0
            if m_nb > 1.0: m_nb /= 100.0

            if m_ya > 0 and m_na > 0 and (m_ya + m_na < 0.90):
                return None, f"Trade execution rejected: Unhealthy market order book (yes_ask={m_ya:.4f}, no_ask={m_na:.4f}) sum < 0.90"
            if (m_ya <= 0.01 and m_yb <= 0.0) or (m_na <= 0.01 and m_nb <= 0.0):
                return None, f"Trade execution rejected: Illiquid zero-bid extreme market price on '{market_ticker}'"

            if side == "YES":
                ask = m_ya if m_ya > 0 else float(matched_m.get("last_price_dollars") or (float(matched_m.get("last_price") or 0)/100.0 if float(matched_m.get("last_price") or 0) > 1.0 else float(matched_m.get("last_price") or 0)) or 0.50)
            else:
                ask = m_na if m_na > 0 else (1.0 - m_ya if m_ya > 0 else 0.50)
            if 0.01 <= ask <= 0.99:
                entry_price = ask
        elif r.status_code == 404:
            if event_ticker.startswith("KALSHI-"):
                market_ticker = event_ticker
                entry_price = float(prediction.get("limit_price") or 0.50)
            else:
                # Check if event_ticker is actually a direct market ticker (e.g. KXNFLGAME-...-DAL)
                headers = {"Accept": "application/json", "User-Agent": "ApexProps-Trader/1.0"}
                from backend.btc.kalshi_trader import kalshi_trader
                if kalshi_trader.is_authenticated():
                    try:
                        headers = kalshi_trader._sign_headers("GET", f"/trade-api/v2/markets/{event_ticker}")
                    except Exception:
                        pass
                r_mkt = requests.get(
                    f"https://external-api.kalshi.com/trade-api/v2/markets/{event_ticker}",
                    headers=headers,
                    timeout=5.0
                )
                if r_mkt.status_code == 200:
                    m_data = r_mkt.json().get("market", {})
                    m_status = str(m_data.get("status") or "").lower()
                    if mode == "LIVE" and m_status and m_status not in ("active", "open"):
                        return None, f"Trade execution failed: Market '{event_ticker}' is {m_status} (cannot place live order on closed market)"
                    market_ticker = event_ticker
                    if explicit_side:
                        side = explicit_side.upper()
                    elif (prediction.get("predicted_team") or "").lower().strip() == "no":
                        side = "NO"
                    else:
                        side = "YES"

                    if side == "YES":
                        ask = float(m_data.get("yes_ask_dollars") or (float(m_data.get("yes_ask", 0)) / 100.0 if m_data.get("yes_ask") else 0) or m_data.get("last_price_dollars") or 0.50)
                    else:
                        ask = float(m_data.get("no_ask_dollars") or (float(m_data.get("no_ask", 0)) / 100.0 if m_data.get("no_ask") else 0) or (1.0 - float(m_data.get("last_price_dollars") or 0.50)) or 0.50)
                    if 0.01 <= ask <= 0.99:
                        entry_price = ask
                elif r_mkt.status_code == 429:
                    logger.warning(f"Kalshi 429 rate limit on market {event_ticker}")
                    return None, f"Kalshi API rate limit (429) while fetching {event_ticker}. Please retry shortly."
                else:
                    logger.warning(f"Event/Market {event_ticker} not found on Kalshi (status {r_mkt.status_code})")
                    return None, f"Trade execution failed: Event {event_ticker} has no active matching markets on Kalshi"
        elif r.status_code == 429:
            logger.warning(f"Kalshi 429 rate limit on {event_ticker}.")
            from backend.database.models import get_user_by_id
            u_chk = get_user_by_id(user_id)
            if u_chk and (u_chk.get("trading_mode") or "PAPER").upper() == "LIVE":
                return None, f"Kalshi API rate limit (429) while fetching {event_ticker}. Please retry shortly."
            if event_ticker.startswith("KX"):
                market_ticker = f"{event_ticker}-MKT"
                entry_price = 0.50
            else:
                return None, f"Kalshi 429 rate limit on {event_ticker}"
        else:
            logger.warning(f"Kalshi returned HTTP {r.status_code} for {event_ticker}")
            return None, f"Kalshi returned HTTP {r.status_code} for {event_ticker}"
    except Exception as e:
        logger.warning(f"Failed to fetch market details for {event_ticker}: {e}")
        from backend.database.models import get_user_by_id
        u_chk = get_user_by_id(user_id)
        if u_chk and (u_chk.get("trading_mode") or "PAPER").upper() == "LIVE":
            return None, f"Failed to fetch market details for live order: {e}"
        if event_ticker.startswith("KX"):
            market_ticker = f"{event_ticker}-MKT"
            entry_price = 0.50
        else:
            return None, f"Failed to fetch market details for {event_ticker}: {e}"

    if not market_ticker:
        return None, f"Trade execution failed: Event {event_ticker} has no active matching markets on Kalshi"

    criteria = _get_user_sports_criteria(user_id)
    wager = float(trade_size) if (trade_size is not None and float(trade_size) > 0) else float(criteria.get("trade_size_dollars") or criteria.get("max_wager") or 10.0)
    count = max(1, int(wager / max(entry_price, 0.01)))
    cost = round(entry_price * count, 2)
    trade_id = f"sports_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    pred_team_name = prediction.get("predicted_team") or prediction.get("team") or "Team"
    conf = float(prediction.get("confidence_pct") or 0.0)
    edge = float(prediction.get("edge_pct") or 5.0)
    sport = prediction.get("sport")
    if not sport:
        m_s = re.search(r'KX(NFL|MLB|NBA|NHL|NCAAF|NCAAB|WNBA|NPB|KBO|SOC|UFC|TEN|MMA)', event_ticker) or re.search(r'KX([A-Z]{3,5}?)(?:GAME|-|$)', event_ticker) or re.search(r'KX([A-Z]{3,5})', event_ticker)
        if m_s:
            sport = m_s.group(1)
        elif event_ticker.startswith("KALSHI-"):
            parts = event_ticker.split("-")
            sport = parts[1] if len(parts) > 1 else "SPORTS"
        else:
            sport = "SPORTS"

    fill_price = entry_price
    fill_count = count
    actual_cost = cost
    order_id = trade_id

    if mode == "LIVE":
        if not market_ticker.startswith("KX") or market_ticker.endswith("-MKT") or market_ticker.startswith("KALSHI-"):
            return None, f"Trade execution failed: Cannot place live order on non-Kalshi ticker '{market_ticker}'"

        from backend.btc.kalshi_trader import get_authenticated_trader_for_user
        kt = get_authenticated_trader_for_user(user, fail_fast=True)
        if not kt or not kt.is_authenticated():
            return None, "User is in LIVE mode but has no valid Kalshi API keys linked in settings"

        bal_res = kt.get_balance(force_refresh=True)
        if not bal_res.get("success"):
            return None, f"Unable to verify Kalshi live balance: {bal_res.get('error', 'Balance check failed')}"
        live_bal = float(bal_res.get("balance_dollars", 0.0))
        if live_bal < cost:
            return None, f"Insufficient Kalshi live balance (${live_bal:.2f}) for order cost (${cost:.2f})"

        # Ensure order count with slippage buffer does not exceed available live balance
        max_price = min(0.99, max(0.01, entry_price + 0.04))
        max_est_cost = max_price * count
        if live_bal < max_est_cost and count > 1:
            clamped = int(live_bal / max_price)
            if clamped >= 1:
                count = clamped
                cost = round(entry_price * count, 2)

        order_res = kt.place_sports_order(
            ticker=market_ticker,
            side=side.lower(),
            count=count,
            limit_price_dollars=entry_price,
            dry_run=False,
            slippage_buffer_dollars=0.04
        )
        if not order_res.get("success"):
            return None, f"Kalshi Order Failed: {order_res.get('error')}"

        order_id = str(order_res.get("order_id") or order_res.get("client_order_id") or trade_id)
        fill_price = float(order_res.get("filled_price") or entry_price)
        fill_count = int(order_res.get("count") or count)
        actual_cost = round(fill_price * fill_count, 2)
    else:
        from backend.database.models import deduct_user_paper_balance
        if not deduct_user_paper_balance(user_id, cost):
            logger.warning(f"User {user_id} has insufficient paper balance for ${cost:.2f} sports trade")
            return None, f"Insufficient paper balance for ${cost:.2f} sports trade"

    evt_obj = evt if ('evt' in locals() and isinstance(evt, dict)) else {}
    mkts_list = [matched_m] if ('matched_m' in locals() and matched_m) else (evt_obj.get("markets", []) if evt_obj else [])
    market_details = parse_sports_market_details(
        ticker=market_ticker or event_ticker,
        title=evt_obj.get("title", ""),
        series=event_ticker,
        markets=mkts_list,
        sub_title=evt_obj.get("sub_title", ""),
        event_obj=evt_obj
    )
    prop_type_val = market_details.get("prop_type", "Moneyline")
    line_val = market_details.get("line", "Moneyline")
    spread_amt_val = market_details.get("spread_amount")
    ou_amt_val = market_details.get("over_under_amount")
    strike_det_val = market_details.get("strike_details", "")
    num_line_val = market_details.get("numeric_line")
    if market_details.get("player_name"):
        pred_team_name = market_details["player_name"]

    trade_dict = {
        "id": order_id,
        "order_id": order_id,
        "client_order_id": order_id,
        "user_id": user_id,
        "ticker": market_ticker,
        "sport": sport,
        "asset": sport,
        "predicted_team": pred_team_name,
        "team": pred_team_name,
        "trade_size_dollars": wager,
        "side": side,
        "direction": side,
        "entry_price": fill_price,
        "count": fill_count,
        "cost": actual_cost,
        "pnl": 0.0,
        "status": "OPEN",
        "mode": mode,
        "combo_id": combo_id,
        "prop_type": f"Combo ({combo_info.get('total_legs', 2)} legs)" if (combo_id and combo_info) else prop_type_val,
        "market_prop_type": prop_type_val,
        "line": line_val,
        "spread_amount": spread_amt_val,
        "over_under_amount": ou_amt_val,
        "strike_details": strike_det_val,
        "numeric_line": num_line_val,
        "reason": (f"[Combo Leg {combo_info.get('leg_num', 1)}/{combo_info.get('total_legs', 2)}] {prop_type_val}: {pred_team_name} ({side})" if (combo_id and combo_info) else (f"[{prop_type_val}] {line_val} | AI Edge: {pred_team_name} (Conf: {conf:.1f}%, Edge: {edge:.1f}%)" if conf < 100 else f"[{prop_type_val}] {line_val} | Manual: {pred_team_name} ({side})")),
        "trading_style": "SPORTS_COMBO" if combo_id else "SPORTS_AI",
        "signal_source": "Sports Combo Slip" if combo_id else ("Native Sports AI Engine" if conf < 100 else "Manual Sports Trade Slip"),
        "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
        "ml_reasoning": json.dumps({
            "event_ticker": event_ticker,
            "market_ticker": market_ticker,
            "sport": sport,
            "combo_id": combo_id,
            "predicted_team": pred_team_name,
            "team": pred_team_name,
            "confidence_pct": conf,
            "edge_pct": edge,
            "prop_type": prop_type_val,
            "line": line_val,
            "spread_amount": spread_amt_val,
            "over_under_amount": ou_amt_val,
            "strike_details": strike_det_val,
            "numeric_line": num_line_val,
            "criteria_met": True
        }),
        "catalysts": [
            f"Combo Parlay: Leg {combo_info.get('leg_num', 1)} of {combo_info.get('total_legs', 2)}" if (combo_id and combo_info) else f"{sport} {prop_type_val}: {line_val}",
            f"{sport} {prop_type_val}: {line_val}" if (combo_id and combo_info) else f"{sport} AI edge: {edge:.1f}%",
            f"Target: {pred_team_name} ({side})" if (combo_id and combo_info) else f"Model win prob: {conf:.1f}%"
        ]
    }
    trade_dict["raw_json"] = json.dumps(trade_dict)
    TradeStore.insert_trade(user_id, trade_dict)
    return trade_dict, None


def _execute_sports_paper_trade(event_ticker: str, prediction: dict, user_id: int, trade_size: Optional[float] = None) -> Optional[dict]:
    trade, err = _execute_sports_trade(event_ticker, prediction, user_id, trade_size=trade_size)
    return trade

import concurrent.futures

_SPORTS_EVENTS_CACHE = {}  # series_ticker -> (timestamp, events)
_SPORTS_EVENTS_CACHE_LOCK = threading.Lock()
_SPORTS_CACHE_TTL = 180.0  # 3 minutes TTL cache to prevent Kalshi 429 rate limits
_SPORTS_AGG_CACHE = {}  # query_filter -> (timestamp, response_dict)
_SPORTS_AGG_CACHE_LOCK = threading.Lock()
_SPORTS_AGG_CACHE_TTL = 600.0  # 10 minutes TTL with background refresh
_ON_DEMAND_PRED_CACHE = {}  # key -> (timestamp, pred_dict)
_ON_DEMAND_PRED_LOCK = threading.Lock()
from zoneinfo import ZoneInfo
from datetime import datetime, date

_MONTHS_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
}

def extract_sports_event_date_and_time(
    ticker: str,
    metadata: Optional[dict] = None,
    event_obj: Optional[dict] = None,
    slate_time_str = None
) -> tuple[Optional[date], Optional[float]]:
    """
    Extracts scheduled game date (date object) and start time (unix epoch float)
    from a sports event ticker, metadata, or Kalshi event object in Eastern Time (ET).
    Returns: (event_date: date | None, start_epoch: float | None)
    """
    metadata = metadata or {}
    event_obj = event_obj or {}

    ev_date = None
    start_epoch = None
    ticker_hhmm = None

    text_corpus = f"{ticker} {event_obj.get('event_ticker', '')} {metadata.get('series_ticker', '')}"
    import re
    m = re.search(r'-(\d{2})([A-Z]{3})(\d{2})(?:(\d{4}))?', text_corpus, flags=re.IGNORECASE)
    if m:
        yy_str, mon_str, dd_str, hhmm_str = m.groups()
        mon = _MONTHS_MAP.get(mon_str.upper())
        if mon:
            try:
                ev_year = 2000 + int(yy_str)
                ev_day = int(dd_str)
                ev_date = date(ev_year, mon, ev_day)
                ticker_hhmm = hhmm_str
            except Exception:
                pass

    # 1. Authoritative schedule from Kalshi milestone start_date
    ms = event_obj.get("milestone")
    if not ms:
        try:
            from backend.engine.kalshi_events_cache import get_milestone_map
            clean_et = ticker.split("-", 2)[0] + "-" + ticker.split("-", 2)[1] if ticker.count("-") >= 2 else ticker
            m_map = get_milestone_map() or {}
            ms = m_map.get(clean_et) or m_map.get(event_obj.get("event_ticker", "")) or (m_map.get(f"SUFFIX:{clean_et.split('-', 1)[1]}") if "-" in clean_et else None)
        except Exception:
            pass
    if ms and ms.get("start_date"):
        try:
            dt = datetime.fromisoformat(ms["start_date"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York"))
            ev_date = dt.date()
            start_epoch = dt.timestamp()
        except Exception:
            pass

    # 2. Authoritative schedule from AI prediction metadata
    if not start_epoch:
        ai_meta = (event_obj.get("ai_prediction") or {}).get("metadata") or metadata or {}
        ai_start = ai_meta.get("start_epoch") or ai_meta.get("start_label")
        if isinstance(ai_start, (int, float)) and ai_start > 0:
            start_epoch = float(ai_start)
            try:
                ev_date = datetime.fromtimestamp(start_epoch, tz=ZoneInfo("America/New_York")).date()
            except Exception:
                pass
        elif ai_start and isinstance(ai_start, str) and ("T" in ai_start or "Z" in ai_start):
            try:
                dt = datetime.fromisoformat(ai_start.replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York"))
                ev_date = dt.date()
                start_epoch = dt.timestamp()
            except Exception:
                pass

    # 3. Kalshi ticker start time (e.g. -26OCT100100 -> 01:00 AM ET, -26OCT102000 -> 8:00 PM ET)
    if not start_epoch and ev_date and ticker_hhmm and len(ticker_hhmm) == 4:
        try:
            hh = int(ticker_hhmm[:2])
            mm = int(ticker_hhmm[2:])
            dt_et = datetime(ev_date.year, ev_date.month, ev_date.day, hh, mm, tzinfo=ZoneInfo("America/New_York"))
            start_epoch = dt_et.timestamp()
        except Exception:
            pass

    # 4. Fallback only: check child markets expected_expiration_time ONLY IF start_epoch is still unknown
    if not start_epoch:
        mkts = event_obj.get("markets") or []
        for m in mkts:
            exp_time = m.get("expected_expiration_time") or m.get("close_time")
            if exp_time and isinstance(exp_time, str):
                try:
                    dt = datetime.fromisoformat(exp_time.replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York"))
                    if not ev_date:
                        ev_date = dt.date()
                        start_epoch = dt.timestamp()
                    elif dt.date() == ev_date:
                        start_epoch = dt.timestamp()
                    break
                except Exception:
                    pass

    if not ev_date:
        date_str = metadata.get("date")
        if date_str and isinstance(date_str, str):
            try:
                clean_d = date_str.split("T")[0].strip()
                parts = [int(p) for p in clean_d.split("-") if p.isdigit()]
                if len(parts) == 3:
                    ev_date = date(parts[0], parts[1], parts[2])
            except Exception:
                pass

    sources = slate_time_str if isinstance(slate_time_str, list) else [slate_time_str]
    sources.append(metadata.get("game_time"))
    now_et = datetime.now(ZoneInfo("America/New_York"))

    best_epoch = None
    best_date = None
    
    for time_str in sources:
        if not time_str or time_str == "TBD":
            continue
        try:
            if "T" in time_str and ("Z" in time_str or "+" in time_str or "-" in time_str[-6:]):
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                dt_et = dt.astimezone(ZoneInfo("America/New_York"))
                best_epoch = dt_et.timestamp()
                best_date = dt_et.date()
                if ev_date and best_date == ev_date:
                    start_epoch = best_epoch
                    break
        except Exception:
            pass
            
        time_m = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)?', time_str, re.IGNORECASE)
        date_m = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})', time_str, re.IGNORECASE)
        
        year = now_et.year
        month = ev_date.month if ev_date else now_et.month
        day = ev_date.day if ev_date else now_et.day
        
        if date_m:
            month_str = date_m.group(1).upper()
            month = _MONTHS_MAP.get(month_str[:3], month)
            day = int(date_m.group(2))
            if month < now_et.month - 3:
                year += 1
                
        if time_m:
            hh = int(time_m.group(1))
            mm = int(time_m.group(2))
            ampm = time_m.group(3)
            if ampm:
                ampm = ampm.upper()
                if ampm == "PM" and hh < 12: hh += 12
                if ampm == "AM" and hh == 12: hh = 0
            
            try:
                dt_et = datetime(year, month, day, hh, mm, tzinfo=ZoneInfo("America/New_York"))
                best_epoch = dt_et.timestamp()
                best_date = dt_et.date()
                if ev_date and best_date == ev_date:
                    start_epoch = best_epoch
                    break
            except Exception:
                pass
                
        if date_m and not time_m:
            try:
                if not ev_date: ev_date = date(year, month, day)
            except Exception:
                pass
                
    if best_epoch and not start_epoch:
        if not ev_date:
            start_epoch = best_epoch
            if best_date: ev_date = best_date

    # if not start_epoch and ev_date and ticker_hhmm and len(ticker_hhmm) == 4:
    # We removed blind ticker fallback for game_time_str because the user explicitly requested "date only" if slate missing.
    return ev_date, start_epoch


_SEGMENT_PATTERNS = (
    (("KXNHL1P",), r"\b(1st|first)\s+period\b", "1st Period"),
    (("KXNHL2P",), r"\b(2nd|second)\s+period\b", "2nd Period"),
    (("KXNHL3P",), r"\b(3rd|third)\s+period\b", "3rd Period"),
    (("KXNHLF10G",), r"\bfirst\s+10\s+min(utes?)?\b", "First 10 Min"),
    (("KXNHLOT",), r"\bovertime\b", "Overtime"),
    (("KXMLBF5",), r"\bfirst\s+(5|five)\s+innings?\b", "First 5 Innings"),
    ((), r"\b(1st|first)\s+half\b", "1st Half"),
    ((), r"\b(2nd|second)\s+half\b", "2nd Half"),
    ((), r"\b(1st|first)\s+quarter\b", "1st Quarter"),
)


def _detect_game_segment(text: str) -> Optional[str]:
    """'1st Period', 'First 5 Innings', ... for part-of-game markets, else None."""
    up = (text or "").upper()
    low = (text or "").lower()
    for series_keys, pattern, label in _SEGMENT_PATTERNS:
        if any(k in up for k in series_keys) or re.search(pattern, low):
            return label
    return None


def parse_sports_market_details(
    ticker: str = '',
    title: str = '',
    series: str = '',
    markets: Optional[list] = None,
    sub_title: str = '',
    event_obj: Optional[dict] = None
) -> dict:
    """
    Parses sport market prop type, line, spread amount, over/under amount,
    and strike details from Kalshi event and market payloads.
    Accurately detects Player Props first, Spreads, Totals (O/U), and Moneylines.
    """
    combined = f"{ticker} {title} {series} {sub_title}".upper()
    markets = markets or []
    m0 = markets[0] if markets and isinstance(markets[0], dict) else {}

    m_title = m0.get('title', '')
    m_sub = m0.get('yes_sub_title', '')
    m_ticker = m0.get('ticker', '')
    m_rules = m0.get('rules_primary', '') or m0.get('rules_secondary', '')
    m_part = str(m0.get('primary_participant_key', '') or '')
    m_custom = m0.get('custom_strike', {}) if isinstance(m0.get('custom_strike'), dict) else {}
    floor_strike = m0.get('floor_strike')
    cap_strike = m0.get('cap_strike')

    # Gather texts to search for player prop patterns
    candidate_texts = [m_title, m_sub, title, sub_title]

    # --- STEP 1: DETECT PLAYER PROPS FIRST ---
    # Kalshi series or tickers that are explicitly player props
    is_prop_series = any(k in combined for k in [
        'KXNHLGOAL', 'KXNHLSHOT', 'KXNHLSOG', 'KXNHLAST', 'KXNHLPTS',
        'KXMLBHRR', 'KXMLBHIT', 'KXMLBHR', 'KXMLBKS', 'KXMLBRBI', 'KXMLBSTEAL', 'KXMLBTB',
        'KXNFLTD', 'KXNFLPASS', 'KXNFLRUSH', 'KXNFLREC', 'KXNFLFG',
        'KXNBAPTS', 'KXNBAREB', 'KXNBAAST', 'KXNBATHREE', 'KXNBA3PT', 'KXNBABLK', 'KXNBASTL',
        'GOALSCORER'
    ]) or any(k in m_ticker.upper() for k in [
        'HRR', 'GOAL', 'SHOT', 'SOG', 'STRIKEOUT', 'TOUCHDOWN', 'PROP'
    ]) or m_part.endswith('_player') or any('player' in k for k in m_custom.keys()) or ('records' in m_rules.lower() and 'game' in m_rules.lower())

    player_name = None
    prop_line_num = None
    prop_stat_raw = None

    for txt in candidate_texts:
        if not txt:
            continue
        m_col = re.match(r'^([^:\n]{2,40}?):\s*(\d+\+?|\d+\.\d+|\d+)\s*(.*)$', txt.strip())
        if m_col:
            cand_name = m_col.group(1).strip()
            # Ensure not a team or game total word, and not a two-team matchup
            if not re.search(r'\b(total|totals|over|under|spread|run line|puck line|moneyline|game|winner|match|vs|at)\b', cand_name, re.IGNORECASE) and not any(sep in cand_name.lower() for sep in (' vs ', ' @ ', ' at ', ' v ')):
                player_name = cand_name
                prop_line_num = m_col.group(2).strip()
                prop_stat_raw = m_col.group(3).strip()
                break

    # If no colon pattern, check Kalshi rules e.g. "If Zachary Bolduc records 1+ goals in the..."
    if not player_name and m_rules:
        m_rule = re.search(r'If\s+([^:\n\d]+?)\s+records?\s+(\d+\+?|\d+\.\d+|\d+)\s*([a-zA-Z\s\+]+?)\s+in\s+the', m_rules, re.IGNORECASE)
        if m_rule:
            player_name = m_rule.group(1).strip()
            prop_line_num = m_rule.group(2).strip()
            prop_stat_raw = m_rule.group(3).strip()

    is_player_prop = bool(player_name or is_prop_series)

    if is_player_prop:
        # Determine stat unit / category
        stat_combined = f"{prop_stat_raw or ''} {combined} {m_rules}".lower()
        if 'hrr' in m_ticker.lower() or 'hrr' in series.lower() or ('hit' in stat_combined and 'run' in stat_combined and 'rbi' in stat_combined) or 'h+r+rbi' in stat_combined or 'hits + runs + rbis' in stat_combined:
            stat_unit = 'H+R+RBI'
        elif 'total bases' in stat_combined or 'tb' in m_ticker.lower() or 'tb' in series.lower():
            stat_unit = 'Total Bases'
        elif 'goal' in stat_combined:
            stat_unit = 'Goals'
        elif 'home run' in stat_combined or 'hr' in m_ticker.lower() or 'hr' in series.lower():
            stat_unit = 'Home Runs'
        elif 'strikeout' in stat_combined or 'ks' in m_ticker.lower() or 'ks' in series.lower():
            stat_unit = 'Strikeouts'
        elif 'hit' in stat_combined or 'hit' in m_ticker.lower():
            stat_unit = 'Hits'
        elif 'rbi' in stat_combined or 'rbi' in m_ticker.lower():
            stat_unit = 'RBIs'
        elif 'shot' in stat_combined or 'sog' in stat_combined:
            stat_unit = 'Shots'
        elif 'touchdown' in stat_combined or 'td' in m_ticker.lower() or 'td' in series.lower():
            stat_unit = 'Touchdowns'
        elif 'pass' in stat_combined:
            stat_unit = 'Pass Yds'
        elif 'rush' in stat_combined:
            stat_unit = 'Rush Yds'
        elif 'reception' in stat_combined or 'rec' in m_ticker.lower():
            stat_unit = 'Receptions'
        elif 'point' in stat_combined or 'pts' in m_ticker.lower() or 'pts' in series.lower():
            stat_unit = 'Points'
        elif 'rebound' in stat_combined or 'reb' in m_ticker.lower():
            stat_unit = 'Rebounds'
        elif 'assist' in stat_combined or 'ast' in m_ticker.lower():
            stat_unit = 'Assists'
        elif prop_stat_raw:
            stat_unit = prop_stat_raw.strip().title()
        else:
            stat_unit = 'Props'

        numeric_line = None
        if prop_line_num:
            try:
                numeric_line = float(prop_line_num.replace('+', ''))
            except Exception:
                pass
        elif floor_strike is not None:
            try:
                numeric_line = float(floor_strike)
                prop_line_num = f"{numeric_line:g}+"
            except Exception:
                pass

        if prop_line_num in ('0.5+', '0.5') and stat_unit in ('Goals', 'Home Runs', 'Strikeouts', 'Shots', 'Touchdowns', 'Receptions', 'Points', 'Rebounds', 'Assists', 'H+R+RBI', 'Hits', 'RBIs'):
            prop_line_num = "1+"
            numeric_line = 1.0

        if not prop_line_num:
            prop_line_num = "1+"

        formatted_line = f"{prop_line_num} {stat_unit}"
        strike_details = f"{player_name}: {formatted_line}" if player_name else (m_title or m_sub or formatted_line)

        return {
            'prop_type': 'Player Prop',
            'line': formatted_line,
            'spread_amount': None,
            'over_under_amount': None,
            'strike_details': strike_details,
            'numeric_line': numeric_line,
            'player_name': player_name
        }

    # --- STEP 2: SPREAD, TOTAL, OR MONEYLINE ---
    # Part-of-game markets (NHL periods, MLB first 5 innings, halves, quarters) and futures were
    # labelled "Moneyline", so the full-game AI pick was shown and traded against them.
    segment = _detect_game_segment(f"{combined} {m_ticker} {m_title} {m_sub}")
    is_futures = any(k in combined for k in ['KXNFLWINS', 'KXWC-', 'KXWC ']) or (len(markets) > 3 and not any(k in combined for k in ['SPREAD', 'TOTAL']))

    if is_futures:
        prop_type = 'Futures'
    elif any(k in combined for k in ['SPREAD', 'RUN LINE', 'PUCK LINE', 'HANDICAP']):
        prop_type = 'Spread'
    elif any(k in combined for k in ['TOTAL', 'POINTS', 'RUNS SCORED', 'O/U', 'OVER/UNDER']):
        prop_type = 'Total (O/U)'
    else:
        prop_type = 'Moneyline'

    if prop_type in ('Moneyline', 'Futures'):
        clean_strike_details = m_title or m_sub or (title if 'vs' not in title.lower() else '') or 'Match Winner'
        if segment:
            prop_type, line_label = 'Period', segment
        elif is_futures or prop_type == 'Futures':
            prop_type, line_label = 'Futures', 'Futures'
            if 'WINS' in m_ticker.upper():
                clean_strike_details = title
        else:
            line_label = 'Moneyline'
        return {
            'prop_type': prop_type,
            'line': line_label,
            'spread_amount': None,
            'over_under_amount': None,
            'strike_details': clean_strike_details,
            'numeric_line': None,
            'player_name': None,
            'segment': segment
        }

    # Extract numeric line/strike
    strike_val = None
    if floor_strike is not None:
        try:
            strike_val = float(floor_strike)
        except Exception:
            pass
    elif cap_strike is not None:
        try:
            strike_val = float(cap_strike)
        except Exception:
            pass

    if strike_val is None:
        text_to_search = f"{m_sub} {m_title} {title}"
        m_num = re.search(r'(?:over|under|by|\+|-)\s*(\d+(?:\.\d+)?)', text_to_search, re.IGNORECASE)
        if m_num:
            try:
                strike_val = float(m_num.group(1))
            except Exception:
                pass
        else:
            m_suf = re.search(r'-([A-Za-z]{0,4})(\d+(?:\.\d+)?)$', m_ticker)
            if m_suf:
                try:
                    strike_val = float(m_suf.group(2))
                except Exception:
                    pass

    spread_amount = None
    over_under_amount = None
    strike_details = m_sub or m_title or title or 'Match Outcome'

    unit = 'pts'
    if any(k in combined for k in ['MLB', 'BASEBALL', 'RUN', 'NPB', 'KBO']):
        unit = 'runs'
    elif any(k in combined for k in ['NHL', 'HOCKEY', 'SOC', 'SOCCER', 'GOAL']):
        unit = 'goals'
    elif any(k in combined for k in ['NBA', 'WNBA', 'BASKETBALL', 'NFL', 'FOOTBALL']):
        unit = 'pts'

    if prop_type == 'Spread':
        if strike_val is not None:
            s_val_str = f"{strike_val:g}"
            spread_amount = f"{s_val_str} {unit}"
            m_team = re.search(r'^([A-Za-z0-9\s\.\'\-]+?)\s+wins?\s+by\s+over', m_sub or m_title, re.IGNORECASE)
            team_prefix = f"{m_team.group(1).strip()} " if m_team else ""
            line_label = f"Spread: {team_prefix}{s_val_str} {unit}"
        else:
            spread_amount = "Spread"
            line_label = "Spread"
    elif prop_type == 'Total (O/U)':
        if strike_val is not None:
            s_val_str = f"{strike_val:g}"
            over_under_amount = f"{s_val_str} {unit}"
            line_label = f"O/U {s_val_str} {unit}"
        else:
            over_under_amount = "O/U"
            line_label = "Total (O/U)"
    else:
        line_label = "Moneyline"
    if segment:
        line_label = f"{segment} {line_label}"

    return {
        'prop_type': prop_type,
        'line': line_label,
        'spread_amount': spread_amount,
        'over_under_amount': over_under_amount,
        'strike_details': strike_details,
        'numeric_line': strike_val,
        'player_name': None,
        'segment': segment
    }


def _fetch_kalshi_series_events(series: str) -> list:
    try:
        from backend.engine.kalshi_market_cache import get_market_cache_instance, USE_MARKET_CACHE
        if USE_MARKET_CACHE:
            cache = get_market_cache_instance()
            if cache.is_cache_healthy():
                cached_evts = cache.get_series_events(series)
                if cached_evts:
                    return cached_evts
    except Exception as e:
        logger.debug(f"[MarketCache] Failed to fetch series events from market cache: {e}")

    now = time.time()
    with _SPORTS_EVENTS_CACHE_LOCK:
        if series in _SPORTS_EVENTS_CACHE:
            ts, cached_events = _SPORTS_EVENTS_CACHE[series]
            if (now - ts < _SPORTS_CACHE_TTL) and cached_events is not None:
                return cached_events

    from backend.btc.kalshi_trader import kalshi_trader
    headers = {'Accept': 'application/json', 'User-Agent': 'ApexProps-Trader/1.0'}
    path = '/trade-api/v2/events'
    if kalshi_trader.is_authenticated():
        try:
            headers = kalshi_trader._sign_headers('GET', path)
        except Exception:
            pass

    import requests
    session = getattr(kalshi_trader, 'session', requests)

    for attempt in range(3):
        try:
            resp = session.get(
                'https://external-api.kalshi.com/trade-api/v2/events',
                params={'series_ticker': series, 'with_nested_markets': True, 'status': 'open', 'limit': 50},
                headers=headers,
                timeout=5.0
            )
            if resp.status_code == 200:
                events = resp.json().get('events', [])
                with _SPORTS_EVENTS_CACHE_LOCK:
                    _SPORTS_EVENTS_CACHE[series] = (now, events)
                
                # --- PRE-SUBSCRIBE TO KALSHI WEBSOCKET ---
                try:
                    from backend.btc.kalshi_ws import subscribe_to_market
                    for ev in events:
                        for m in ev.get('markets', []):
                            tkr = m.get('ticker')
                            if tkr:
                                subscribe_to_market(tkr)
                except Exception as e:
                    pass
                # -----------------------------------------
                return events
            elif resp.status_code == 429:
                logger.warning(f"Kalshi 429 rate limit on series {series}, attempt {attempt+1}")
                with _SPORTS_EVENTS_CACHE_LOCK:
                    if series in _SPORTS_EVENTS_CACHE and _SPORTS_EVENTS_CACHE[series][1] is not None:
                        return _SPORTS_EVENTS_CACHE[series][1]
                break
            else:
                logger.warning(f"Kalshi returned HTTP {resp.status_code} for series {series}")
                break
        except Exception as e:
            logger.error(f"Error fetching Kalshi series {series}: {e}")
            break

    with _SPORTS_EVENTS_CACHE_LOCK:
        if series in _SPORTS_EVENTS_CACHE and _SPORTS_EVENTS_CACHE[series][1] is not None:
            return _SPORTS_EVENTS_CACHE[series][1]
        _SPORTS_EVENTS_CACHE[series] = (now, [])

    return []


_SPORT_TEAM_MAP = {
    "MLB": {
      "ARI": "Arizona Diamondbacks", "ARIZONA": "Arizona Diamondbacks",
      "ATL": "Atlanta Braves", "ATLANTA": "Atlanta Braves",
      "BAL": "Baltimore Orioles", "BALTIMORE": "Baltimore Orioles",
      "BOS": "Boston Red Sox", "BOSTON": "Boston Red Sox",
      "CHC": "Chicago Cubs", "CWS": "Chicago White Sox", "CHICAGO WS": "Chicago White Sox", "CHW": "Chicago White Sox",
      "CIN": "Cincinnati Reds", "CINCINNATI": "Cincinnati Reds",
      "CLE": "Cleveland Guardians", "CLEVELAND": "Cleveland Guardians",
      "COL": "Colorado Rockies", "COLORADO": "Colorado Rockies",
      "DET": "Detroit Tigers", "DETROIT": "Detroit Tigers",
      "HOU": "Houston Astros", "HOUSTON": "Houston Astros",
      "KC": "Kansas City Royals", "KANSAS CITY": "Kansas City Royals",
      "LAA": "Los Angeles Angels", "LAD": "Los Angeles Dodgers", "LOS ANGELES D": "Los Angeles Dodgers",
      "MIA": "Miami Marlins", "MIAMI": "Miami Marlins",
      "MIL": "Milwaukee Brewers", "MILWAUKEE": "Milwaukee Brewers",
      "MIN": "Minnesota Twins", "MINNESOTA": "Minnesota Twins",
      "NYM": "New York Mets", "NYY": "New York Yankees", "NEW YORK M": "New York Mets", "NEW YORK Y": "New York Yankees",
      "OAK": "Oakland Athletics", "OAKLAND": "Oakland Athletics",
      "PHI": "Philadelphia Phillies", "PHILADELPHIA": "Philadelphia Phillies",
      "PIT": "Pittsburgh Pirates", "PITTSBURGH": "Pittsburgh Pirates",
      "SD": "San Diego Padres", "SAN DIEGO": "San Diego Padres", "SDP": "San Diego Padres",
      "SF": "San Francisco Giants", "SAN FRANCISCO": "San Francisco Giants", "SFG": "San Francisco Giants",
      "SEA": "Seattle Mariners", "SEATTLE": "Seattle Mariners",
      "STL": "St. Louis Cardinals", "ST. LOUIS": "St. Louis Cardinals", "ST LOUIS": "St. Louis Cardinals",
      "TB": "Tampa Bay Rays", "TAMPA BAY": "Tampa Bay Rays", "TBR": "Tampa Bay Rays",
      "TEX": "Texas Rangers", "TEXAS": "Texas Rangers",
      "TOR": "Toronto Blue Jays", "TORONTO": "Toronto Blue Jays",
      "WSH": "Washington Nationals", "WASHINGTON": "Washington Nationals", "WAS": "Washington Nationals",
    },
    "NFL": {
      "ARI": "Arizona Cardinals", "ARIZONA": "Arizona Cardinals",
      "ATL": "Atlanta Falcons", "ATLANTA": "Atlanta Falcons",
      "BAL": "Baltimore Ravens", "BALTIMORE": "Baltimore Ravens",
      "BUF": "Buffalo Bills", "BUFFALO": "Buffalo Bills",
      "CAR": "Carolina Panthers", "CAROLINA": "Carolina Panthers",
      "CHI": "Chicago Bears", "CHICAGO": "Chicago Bears",
      "CIN": "Cincinnati Bengals", "CINCINNATI": "Cincinnati Bengals",
      "CLE": "Cleveland Browns", "CLEVELAND": "Cleveland Browns",
      "DAL": "Dallas Cowboys", "DALLAS": "Dallas Cowboys",
      "DEN": "Denver Broncos", "DENVER": "Denver Broncos",
      "DET": "Detroit Lions", "DETROIT": "Detroit Lions",
      "GB": "Green Bay Packers", "GREEN BAY": "Green Bay Packers",
      "HOU": "Houston Texans", "HOUSTON": "Houston Texans",
      "IND": "Indianapolis Colts", "INDIANAPOLIS": "Indianapolis Colts",
      "JAC": "Jacksonville Jaguars", "JAX": "Jacksonville Jaguars", "JACKSONVILLE": "Jacksonville Jaguars",
      "KC": "Kansas City Chiefs", "KANSAS CITY": "Kansas City Chiefs",
      "LV": "Las Vegas Raiders", "LAS VEGAS": "Las Vegas Raiders",
      "LAC": "Los Angeles Chargers", "LOS ANGELES C": "Los Angeles Chargers",
      "LAR": "Los Angeles Rams", "LA RAMS": "Los Angeles Rams", "LOS ANGELES R": "Los Angeles Rams",
      "MIA": "Miami Dolphins", "MIAMI": "Miami Dolphins",
      "MIN": "Minnesota Vikings", "MINNESOTA": "Minnesota Vikings",
      "NE": "New England Patriots", "NEW ENGLAND": "New England Patriots",
      "NO": "New Orleans Saints", "NEW ORLEANS": "New Orleans Saints", "NOLA": "New Orleans Saints",
      "NYG": "New York Giants", "NEW YORK G": "New York Giants",
      "NYJ": "New York Jets", "NEW YORK J": "New York Jets",
      "PHI": "Philadelphia Eagles", "PHILADELPHIA": "Philadelphia Eagles",
      "PIT": "Pittsburgh Steelers", "PITTSBURGH": "Pittsburgh Steelers",
      "SEA": "Seattle Seahawks", "SEATTLE": "Seattle Seahawks",
      "SF": "San Francisco 49ers", "SAN FRANCISCO": "San Francisco 49ers",
      "TB": "Tampa Bay Buccaneers", "TAMPA BAY": "Tampa Bay Buccaneers",
      "TEN": "Tennessee Titans", "TENNESSEE": "Tennessee Titans",
      "WAS": "Washington Commanders", "WASHINGTON": "Washington Commanders",
    },
    "NHL": {
      "ANA": "Anaheim Ducks", "ANAHEIM": "Anaheim Ducks",
      "BOS": "Boston Bruins", "BOSTON": "Boston Bruins",
      "BUF": "Buffalo Sabres", "BUFFALO": "Buffalo Sabres",
      "CGY": "Calgary Flames", "CALGARY": "Calgary Flames",
      "CAR": "Carolina Hurricanes", "CAROLINA": "Carolina Hurricanes",
      "CHI": "Chicago Blackhawks", "CHICAGO": "Chicago Blackhawks",
      "COL": "Colorado Avalanche", "COLORADO": "Colorado Avalanche",
      "CBJ": "Columbus Blue Jackets", "COLUMBUS": "Columbus Blue Jackets",
      "DAL": "Dallas Stars", "DALLAS": "Dallas Stars",
      "DET": "Detroit Red Wings", "DETROIT": "Detroit Red Wings",
      "EDM": "Edmonton Oilers", "EDMONTON": "Edmonton Oilers",
      "FLA": "Florida Panthers", "FLORIDA": "Florida Panthers",
      "LAK": "Los Angeles Kings", "LA KINGS": "Los Angeles Kings", "LOS ANGELES": "Los Angeles Kings", "LOS ANGELES K": "Los Angeles Kings",
      "MIN": "Minnesota Wild", "MINNESOTA": "Minnesota Wild",
      "MTL": "Montreal Canadiens", "MONTREAL": "Montreal Canadiens",
      "NSH": "Nashville Predators", "NASHVILLE": "Nashville Predators",
      "NJD": "New Jersey Devils", "NEW JERSEY": "New Jersey Devils",
      "NYI": "New York Islanders", "NEW YORK I": "New York Islanders",
      "NYR": "New York Rangers", "NEW YORK R": "New York Rangers",
      "OTT": "Ottawa Senators", "OTTAWA": "Ottawa Senators",
      "PHI": "Philadelphia Flyers", "PHILADELPHIA": "Philadelphia Flyers",
      "PIT": "Pittsburgh Penguins", "PITTSBURGH": "Pittsburgh Penguins",
      "SJS": "San Jose Sharks", "SAN JOSE": "San Jose Sharks",
      "SEA": "Seattle Kraken", "SEATTLE": "Seattle Kraken",
      "STL": "St. Louis Blues", "ST. LOUIS": "St. Louis Blues",
      "TBL": "Tampa Bay Lightning", "TAMPA BAY": "Tampa Bay Lightning",
      "TOR": "Toronto Maple Leafs", "TORONTO": "Toronto Maple Leafs",
      "UTA": "Utah Hockey Club", "UTAH": "Utah Hockey Club",
      "VAN": "Vancouver Canucks", "VANCOUVER": "Vancouver Canucks",
      "VGK": "Vegas Golden Knights", "VEGAS": "Vegas Golden Knights",
      "WSH": "Washington Capitals", "WASHINGTON": "Washington Capitals",
      "WPG": "Winnipeg Jets", "WINNIPEG": "Winnipeg Jets",
    },
    "NPB": {
      "HAWKS": "Fukuoka SoftBank Hawks", "FUKUOKA": "Fukuoka SoftBank Hawks", "FUKUOKA HAWKS": "Fukuoka SoftBank Hawks",
      "BAYSTARS": "Yokohama DeNA BayStars", "YOKOHAMA": "Yokohama DeNA BayStars", "YOKOHAMA BAYSTARS": "Yokohama DeNA BayStars",
      "CARP": "Hiroshima Toyo Carp", "HIROSHIMA": "Hiroshima Toyo Carp", "HIROSHIMA CARP": "Hiroshima Toyo Carp",
      "GIANTS": "Yomiuri Giants", "YOMIURI": "Yomiuri Giants", "YOMIURI GIANTS": "Yomiuri Giants",
      "TIGERS": "Hanshin Tigers", "HANSHIN": "Hanshin Tigers", "HANSHIN TIGERS": "Hanshin Tigers",
      "SWALLOWS": "Tokyo Yakult Swallows", "YAKULT": "Tokyo Yakult Swallows", "TOKYO YAKULT SWALLOWS": "Tokyo Yakult Swallows",
      "DRAGONS": "Chunichi Dragons", "CHUNICHI": "Chunichi Dragons", "CHUNICHI DRAGONS": "Chunichi Dragons",
      "LIONS": "Saitama Seibu Lions", "SEIBU": "Saitama Seibu Lions", "SAITAMA SEIBU LIONS": "Saitama Seibu Lions",
      "BUFFALOES": "Orix Buffaloes", "ORIX": "Orix Buffaloes", "ORIX BUFFALOES": "Orix Buffaloes",
      "MARINES": "Chiba Lotte Marines", "LOTTE": "Chiba Lotte Marines", "CHIBA LOTTE MARINES": "Chiba Lotte Marines",
      "FIGHTERS": "Hokkaido Nippon-Ham Fighters", "NIPPON-HAM": "Hokkaido Nippon-Ham Fighters", "HOKKAIDO NIPPON-HAM FIGHTERS": "Hokkaido Nippon-Ham Fighters",
      "GOLDEN EAGLES": "Tohoku Rakuten Golden Eagles", "EAGLES": "Tohoku Rakuten Golden Eagles", "RAKUTEN": "Tohoku Rakuten Golden Eagles", "TOHOKU RAKUTEN GOLDEN EAGLES": "Tohoku Rakuten Golden Eagles"
    },
    "KBO": {
      "BEARS": "Doosan Bears", "DOOSAN": "Doosan Bears", "DOOSAN BEARS": "Doosan Bears",
      "GIANTS": "Lotte Giants", "LOTTE": "Lotte Giants", "LOTTE GIANTS": "Lotte Giants",
      "TWINS": "LG Twins", "LG": "LG Twins", "LG TWINS": "LG Twins",
      "WIZ": "KT Wiz", "KT": "KT Wiz", "KT WIZ": "KT Wiz",
      "LANDERS": "SSG Landers", "SSG": "SSG Landers", "SSG LANDERS": "SSG Landers",
      "DINOS": "NC Dinos", "NC": "NC Dinos", "NC DINOS": "NC Dinos",
      "TIGERS": "Kia Tigers", "KIA": "Kia Tigers", "KIA TIGERS": "Kia Tigers",
      "LIONS": "Samsung Lions", "SAMSUNG": "Samsung Lions", "SAMSUNG LIONS": "Samsung Lions",
      "HEROES": "Kiwoom Heroes", "KIWOOM": "Kiwoom Heroes", "KIWOOM HEROES": "Kiwoom Heroes",
      "EAGLES": "Hanwha Eagles", "HANWHA": "Hanwha Eagles", "HANWHA EAGLES": "Hanwha Eagles"
    },
    "SOC": {
      "MAN CITY": "Manchester City", "MANCHESTER CITY": "Manchester City",
      "MAN UTD": "Manchester United", "MAN UNITED": "Manchester United", "MANCHESTER UTD": "Manchester United", "MANCHESTER UNITED": "Manchester United",
      "SPURS": "Tottenham Hotspur", "TOTTENHAM": "Tottenham Hotspur", "TOTTENHAM HOTSPUR": "Tottenham Hotspur",
      "ARSENAL": "Arsenal", "CHELSEA": "Chelsea", "LIVERPOOL": "Liverpool",
      "NEWCASTLE": "Newcastle United", "NEWCASTLE UTD": "Newcastle United",
      "WOLVES": "Wolverhampton Wanderers", "WOLVERHAMPTON": "Wolverhampton Wanderers",
      "BRIGHTON": "Brighton & Hove Albion", "WEST HAM": "West Ham United",
      "ASTON VILLA": "Aston Villa", "EVERTON": "Everton",
      "DORTMUND": "Borussia Dortmund", "BVB": "Borussia Dortmund",
      "BAYERN": "Bayern Munich", "BAYERN MUNICH": "Bayern Munich",
      "LEVERKUSEN": "Bayer Leverkusen", "LEIPZIG": "RB Leipzig",
      "REAL MADRID": "Real Madrid", "BARCELONA": "Barcelona", "ATLETICO": "Atletico Madrid",
      "PSG": "Paris Saint-Germain", "INTER": "Inter Milan", "MILAN": "AC Milan", "JUVENTUS": "Juventus"
    }
}

def _normalize_team_name(name: str, sport: str = None) -> str:
    n = (name or "").upper().strip()
    if not n: return ""
    if sport and sport in _SPORT_TEAM_MAP:
        return _SPORT_TEAM_MAP[sport].get(n, n)
    # Fallback to the first match if no sport
    for sm in _SPORT_TEAM_MAP.values():
        if n in sm: return sm[n]
    return n

def _normalize_sport(s: str) -> str:
    s = (s or "").upper().strip()
    if s in ("NPB/KBO", "NPB_KBO", "NPB-KBO", "NPB", "KBO"):
        return "NPB/KBO"
    if s in ("TEN", "TENNIS", "ATP", "WTA"):
        return "TEN"
    if s in ("SOC", "SOCCER", "EPL", "MLS", "UEFA", "WC"):
        return "SOC"
    if s in ("UFC", "MMA"):
        return "UFC"
    if s in ("NHL", "HOCKEY"):
        return "NHL"
    if s in ("MLB", "BASEBALL"):
        return "MLB"
    if s in ("NFL", "FOOTBALL"):
        return "NFL"
    return s


_SLATE_CACHE = {}
_SLATE_CACHE_TIME = 0
def _fetch_all_slates_for_times(base_url='http://127.0.0.1:8057'):
    global _SLATE_CACHE_TIME, _SLATE_CACHE
    import time
    if time.time() - _SLATE_CACHE_TIME < 300 and _SLATE_CACHE:
        return _SLATE_CACHE
    import httpx, concurrent.futures
    endpoints = [
        ('NHL', '/api/hockey/slate'), ('MLB', '/api/mlb/games'), ('NBA', '/api/nba/slate'), 
        ('NCAAF', '/api/ncaaf/slate'), ('SOC', '/api/soccer/slate'), ('TEN', '/api/tennis/slate'), 
        ('UFC', '/api/ufc/slate'), ('NPB', '/api/npb_kbo/slate'), ('KBO', '/api/npb_kbo/slate'), ('NFL', '/api/nfl/games')
    ]
    all_games = []
    def fetch_endpoint(args):
        sport, ep = args
        try:
            with httpx.Client(timeout=7.0) as c:
                r = c.get(f"{base_url}{ep}")
                if r.status_code == 200:
                    d = r.json()
                    games = d.get('games') or d.get('matches') or d.get('slate') or d.get('events') or d
                    if isinstance(games, dict) and ('games' in games or 'matches' in games):
                        games = games.get('games') or games.get('matches')
                    if isinstance(games, list):
                        return (sport, games)
        except Exception:
            pass
        return (sport, [])

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for res in executor.map(fetch_endpoint, endpoints):
            sport, games = res
            for g in games:
                all_games.append((sport, g))
            
    slate_map = {}
    for sport, g in all_games:
        if sport not in slate_map:
            slate_map[sport] = {}
        
        ht = g.get('home_team')
        at = g.get('away_team')
        aliases = []
        for team_val in [ht, at]:
            if isinstance(team_val, dict):
                aliases.append(team_val.get('name'))
                aliases.append(team_val.get('abbreviation'))
                aliases.append(team_val.get('abbr'))
            elif isinstance(team_val, str):
                aliases.append(team_val)
        aliases.extend([
            g.get('name'), g.get('predicted_team'), g.get('player_a'), 
            g.get('opponent'), g.get('player_b')
        ])
        
        start_time = g.get('start_time') or g.get('game_datetime') or g.get('commence_time') or g.get('date')
        
        if sport in ('NPB', 'KBO') and start_time and 'ET' in start_time:
            if '18:00' in start_time or '13:00' in start_time or '14:00' in start_time:
                start_time = None
        
        import re
        for t in aliases:
            if t:
                t = re.sub(r'Game\s+\d+:\s*', '', str(t), flags=re.IGNORECASE)
                t_clean = re.sub(r'[^a-zA-Z0-9]', '', t).lower()

                if start_time not in ('TBD', None, ''):
                    if t_clean not in slate_map[sport]:
                        slate_map[sport][t_clean] = []
                    if start_time not in slate_map[sport][t_clean]:
                        slate_map[sport][t_clean].append(start_time)

                parts = t.split()
                if len(parts) > 1:
                    mascot_clean = re.sub(r'[^a-zA-Z0-9]', '', parts[-1]).lower()
                    city_clean = re.sub(r'[^a-zA-Z0-9]', '', "".join(parts[:-1])).lower()
                    if start_time not in ('TBD', None, ''):
                        for c in [mascot_clean, city_clean, re.sub(r'[^a-zA-Z0-9]', '', parts[0]).lower()]:
                            if c:
                                if c not in slate_map[sport]:
                                    slate_map[sport][c] = []
                                if start_time not in slate_map[sport][c]:
                                    slate_map[sport][c].append(start_time)

    _SLATE_CACHE = slate_map
    _SLATE_CACHE_TIME = time.time()
    return slate_map

_UFC_SUFFIXES = {'jr', 'sr', 'ii', 'iii', 'iv', 'v'}

def _get_fighter_surname(name_str: str) -> str:
    if not name_str:
        return ""
    import unicodedata
    clean = ''.join(ch for ch in unicodedata.normalize('NFD', str(name_str)) if unicodedata.category(ch) != 'Mn').lower()
    tokens = [w for w in re.findall(r'[a-z0-9]+', clean) if w]
    while tokens and tokens[-1] in _UFC_SUFFIXES:
        tokens.pop()
    return tokens[-1] if tokens else ""

def _surname_match(s1: str, s2: str) -> bool:
    if not s1 or not s2:
        return False
    if s1 == s2:
        return True
    if len(s1) >= 4 and len(s2) >= 4:
        import difflib
        if difflib.SequenceMatcher(None, s1, s2).ratio() >= 0.85:
            return True
    return False

def normalize_sport_key(sport_or_league: str) -> str:
    s = str(sport_or_league or "").strip().upper()
    if s in ("NPB", "KBO", "NPB/KBO", "NPB_KBO", "NPB-KBO"):
        return "NPB/KBO"
    if s in ("SOCCER", "SOC", "EPL", "MLS", "BUNDESLIGA", "LALIGA", "UEFA"):
        return "SOC"
    if s in ("UFC", "MMA"):
        return "UFC"
    if s in ("TEN", "TENNIS", "ATP", "WTA"):
        return "TEN"
    if s in ("MLB", "BASEBALL"):
        return "MLB"
    if s in ("NFL", "FOOTBALL"):
        return "NFL"
    if s in ("NHL", "HOCKEY"):
        return "NHL"
    if s in ("NBA", "BASKETBALL"):
        return "NBA"
    if s in ("NCAAF", "CFB"):
        return "NCAAF"
    return s

def classify_event_market_and_prop(evt: dict) -> tuple:
    """
    Returns (market_category, prop_subtype).
    market_category in: 'GAME', 'SPREAD', 'TOTAL', 'PROP', 'INNING'
    prop_subtype in:
      NFL: 'ANYTIME_TD', 'FIRST_TD', 'PASSING_YDS', 'RUSHING_YDS', 'RECEIVING_YDS', 'RECEPTIONS', 'OTHER'
      MLB: 'HITS_RUNS_RBIS', 'HOME_RUNS', 'STRIKEOUTS', 'TOTAL_BASES', 'HITS', 'RBIS', 'OTHER'
      NHL: 'GOAL', 'POINTS', 'ASSISTS', 'SAVES', 'FIRST_GOAL', 'OTHER'
      SOC: 'BTTS', 'CORNERS', 'FTTS', 'CORRECT_SCORE', 'OTHER'
      UFC: 'DISTANCE', 'METHOD_OF_FINISH', 'ROUND_PROPS', 'OTHER'
      NBA: 'POINTS', 'REBOUNDS', 'ASSISTS', 'THREES', 'BLOCKS_STEALS', 'OTHER'
    """
    event_ticker = str(evt.get("event_ticker") or evt.get("ticker") or "").upper()
    series_ticker = str(evt.get("series_ticker") or (event_ticker.split('-')[0] if '-' in event_ticker else "")).upper()
    market_type = str(evt.get("market_type") or "").upper()
    prop_type = str(evt.get("prop_type") or "").upper()
    title = str(evt.get("title") or "").upper()
    sub_title = str(evt.get("sub_title") or "").upper()
    strike = str(evt.get("strike_details") or "").upper()

    combined = f"{event_ticker} {series_ticker} {market_type} {prop_type} {title} {sub_title} {strike}"

    # 1. Period / Inning / Derivative / Sets / Halves
    is_period = (
        "PERIOD" in market_type or "PERIOD" in prop_type or
        any(k in series_ticker for k in ("1P", "2P", "3P", "F5", "1H", "2H", "HALF", "INNING", "SETWINNER", "RFI", "QTR", "1Q", "2Q", "3Q", "4Q")) or
        bool(re.search(r'(?:^KX[A-Z0-9]+-(?:1P|2P|3P|F5|F3|1H|2H|HALF|INNING|Q1|Q2|Q3|Q4|SETWINNER|RFI)|-(?:1P|2P|3P|1H|2H|F5)$)', event_ticker)) or
        any(k in title for k in ("1ST PERIOD", "2ND PERIOD", "3RD PERIOD", "FIRST 5", "1ST HALF", "2ND HALF", "1ST INNING", "SET 1", "FIRST INNING"))
    )
    if is_period:
        return "INNING", "OTHER"

    # 2. Spread / Run Line / Puck Line / Handicap
    is_spread = (
        "SPREAD" in market_type or "SPREAD" in prop_type or
        "SPREAD" in event_ticker or "SPREAD" in series_ticker or
        "PUCK LINE" in combined or "RUN LINE" in combined or "HANDICAP" in combined or "WINS BY OVER" in title
    )
    if is_spread:
        return "SPREAD", "OTHER"

    # 3. Totals (Over / Under)
    is_total = (
        ("TOTAL" in market_type and "PLAYER" not in market_type and "TEAM" not in market_type) or
        ("TOTAL" in prop_type and "PLAYER" not in prop_type) or
        "TOTAL" in series_ticker or "ROUNDS" in series_ticker or
        "TOTAL" in event_ticker or "ROUNDS" in event_ticker or
        "OVER/UNDER" in combined or "O/U" in market_type or "O/U" in prop_type or
        "RUNS SCORED" in combined or "GOALS SCORED" in combined or "TOTAL GAMES" in combined
    )
    if is_total:
        return "TOTAL", "OTHER"

    # 4. Player Props & Match Specials
    is_prop = (
        "PLAYER PROP" in market_type or "PLAYER PROP" in prop_type or "PROP" in market_type or
        any(k in event_ticker for k in (
            "HRR", "KXMLBHR", "KXMLBKS", "KXMLBTB", "KXMLBHIT", "KXMLBRBI",
            "KXNFLTD", "KXNFLPASS", "KXNFLRSH", "KXNFLREC", "KXNFLFIRSTTD",
            "KXNHLGOAL", "KXNHLPTS", "KXNHLAST", "KXNHLSAVE", "KXNHLFIRSTGOAL", "KXNHLF10G", "KXNHLOT",
            "KXUFCDISTANCE", "KXUFCMOF", "KXUFCMOV", "KXUFCVICROUND",
            "KXEPLBTTS", "KXEPLCORNERS", "KXEPLFTTS", "KXEPLSCORE", "KXMLSBTTS", "KXMLSCORNERS", "KXMLSFTTS", "KXMLSSCORE",
            "KXNBAPTS", "KXNBAREB", "KXNBAAST", "KXNBATHREE", "KXNBA3PT", "KXNBABLK", "KXNBASTL"
        )) or
        any(k in series_ticker for k in (
            "HRR", "KXMLBHR", "KXMLBKS", "KXMLBTB", "KXMLBHIT", "KXMLBRBI",
            "KXNFLTD", "KXNFLPASS", "KXNFLRSH", "KXNFLREC", "KXNFLFIRSTTD",
            "KXNHLGOAL", "KXNHLPTS", "KXNHLAST", "KXNHLSAVE", "KXNHLFIRSTGOAL", "KXNHLF10G", "KXNHLOT",
            "KXUFCDISTANCE", "KXUFCMOF", "KXUFCMOV", "KXUFCVICROUND",
            "BTTS", "CORNERS", "FTTS", "SCORE",
            "KXNBAPTS", "KXNBAREB", "KXNBAAST", "KXNBATHREE", "KXNBABLK", "KXNBASTL"
        )) or
        "RECORDS" in strike or (":" in strike and any(ch.isdigit() for ch in strike)) or
        any(k in combined for k in ("DISTANCE", "METHOD OF FINISH", "BOTH TEAMS TO SCORE", "FIRST GOALSCORER", "FIRST TOUCHDOWN"))
    )
    if is_prop:
        # MLB
        if "HRR" in combined or "H+R+RBI" in combined:
            return "PROP", "HITS_RUNS_RBIS"
        elif "HOME RUN" in combined or "KXMLBHR" in event_ticker or "KXMLBHR" in series_ticker:
            return "PROP", "HOME_RUNS"
        elif "STRIKEOUT" in combined or "KXMLBKS" in event_ticker or "KXMLBKS" in series_ticker:
            return "PROP", "STRIKEOUTS"
        elif "TOTAL BASES" in combined or "KXMLBTB" in event_ticker or "KXMLBTB" in series_ticker:
            return "PROP", "TOTAL_BASES"
        elif "KXMLBHIT" in event_ticker or "KXMLBHIT" in series_ticker or " 1+ HITS" in combined or " 2+ HITS" in combined:
            return "PROP", "HITS"
        elif "KXMLBRBI" in event_ticker or "KXMLBRBI" in series_ticker or " 1+ RBIS" in combined:
            return "PROP", "RBIS"
        # NFL
        elif "FIRST TD" in combined or "FIRST TOUCHDOWN" in combined or "KXNFLFIRSTTD" in event_ticker:
            return "PROP", "FIRST_TD"
        elif "TOUCHDOWN" in combined or "KXNFLTD" in event_ticker or "ANYTIME TD" in combined:
            return "PROP", "ANYTIME_TD"
        elif "PASS" in combined or "PASSING" in combined or "KXNFLPASS" in event_ticker:
            return "PROP", "PASSING_YDS"
        elif "RUSH" in combined or "RUSHING" in combined or "KXNFLRSH" in event_ticker:
            return "PROP", "RUSHING_YDS"
        elif "RECEPTION" in combined or "KXNFLREC-" in event_ticker or "KXNFLREC" in series_ticker:
            return "PROP", "RECEPTIONS"
        elif "RECEIVING" in combined or "KXNFLRECYDS" in event_ticker or "KXNFLRECYDS" in series_ticker:
            return "PROP", "RECEIVING_YDS"
        # NHL
        elif "FIRST GOAL" in combined or "KXNHLFIRSTGOAL" in event_ticker or "KXNHLFIRSTGOAL" in series_ticker:
            return "PROP", "FIRST_GOAL"
        elif "KXNHLGOAL" in event_ticker or "KXNHLGOAL" in series_ticker or " 1+ GOALS" in combined:
            return "PROP", "GOAL"
        elif "KXNHLPTS" in event_ticker or "KXNHLPTS" in series_ticker or " 1+ POINTS" in combined:
            return "PROP", "POINTS"
        elif "KXNHLAST" in event_ticker or "KXNHLAST" in series_ticker or " 1+ ASSISTS" in combined:
            return "PROP", "ASSISTS"
        elif "SAVE" in combined or "KXNHLSAVE" in event_ticker or "KXNHLSAVE" in series_ticker:
            return "PROP", "SAVES"
        # Soccer specials
        elif "BTTS" in series_ticker or "BOTH TEAMS TO SCORE" in combined:
            return "PROP", "BTTS"
        elif "CORNER" in series_ticker or "CORNERS" in combined:
            return "PROP", "CORNERS"
        elif "FTTS" in series_ticker or "FIRST GOAL OF THE GAME" in combined:
            return "PROP", "FTTS"
        elif "SCORE" in series_ticker or "FINAL SCORE" in combined:
            return "PROP", "CORRECT_SCORE"
        # UFC specials
        elif "DISTANCE" in series_ticker or "DISTANCE" in combined or "KXUFCDISTANCE" in event_ticker:
            return "PROP", "DISTANCE"
        elif "MOF" in series_ticker or "MOV" in series_ticker or "METHOD" in combined or "DECISION" in combined or "SUBMISSION" in combined:
            return "PROP", "METHOD_OF_FINISH"
        elif "VICROUND" in series_ticker or "ROUND 1" in combined or "ROUND 2" in combined or "ROUND 3" in combined:
            return "PROP", "ROUND_PROPS"
        # NBA
        elif "KXNBAPTS" in event_ticker or "POINTS" in combined:
            return "PROP", "POINTS"
        elif "KXNBAREB" in event_ticker or "REBOUND" in combined:
            return "PROP", "REBOUNDS"
        elif "KXNBAAST" in event_ticker or "ASSIST" in combined:
            return "PROP", "ASSISTS"
        elif "THREES" in combined or "3-POINTER" in combined or "KXNBATHREE" in event_ticker or "KXNBA3PT" in event_ticker:
            return "PROP", "THREES"
        elif "BLOCK" in combined or "STEAL" in combined or "KXNBABLK" in event_ticker or "KXNBASTL" in event_ticker:
            return "PROP", "BLOCKS_STEALS"
        else:
            return "PROP", "OTHER"

    # 5. Default is GAME
    return "GAME", "OTHER"

def classify_event_strategy(evt: dict) -> str:
    """
    Classifies an event into one of the curated sports betting strategies:
    - 'FLOOR_TOTALS': Lower alternate lines with high probability (~87% win rate, e.g. NHL O3.5, MLB O5.5, NFL O31.5)
    - 'MILESTONE_PROPS': High-probability contact floor props (~75% win rate, e.g. MLB 1+ Hits/Runs/RBIs line 0.5, NBA 15+ Pts)
    - 'STANDARD': Classic +EV moneyline / game winner or standard spread
    """
    try:
        mkt_cat, prop_sub = classify_event_market_and_prop(evt)
        tk = str(evt.get("event_ticker") or evt.get("ticker") or "").upper()
        title = str(evt.get("title") or "").upper()
        sub = str(evt.get("sub_title") or evt.get("strike_details") or evt.get("yes_sub_title") or "").upper()
        comb = f"{tk} {title} {sub}"

        # 1. Floor Anchor Totals: Soccer Over 0.5/1.5, NHL Over 2.5/3.5, MLB Over 5.5, NFL Over 31.5/27.5
        if mkt_cat == "TOTAL" or "TOTAL" in tk or "OVER" in comb:
            for m in evt.get("markets", []):
                fs = m.get("floor_strike")
                m_tk = str(m.get("ticker") or "").upper()
                if "KXNHL" in tk or "NHL" in tk:
                    if (fs is not None and float(fs) <= 4.5) or any(m_tk.endswith(f"-{k}") for k in ("1", "2", "3", "4")):
                        return "FLOOR_TOTALS"
                elif any(k in tk for k in ("SOC", "MLS", "EPL", "UCL", "UEFA", "LALIGA", "BUNDES", "SERIE", "LIGUE", "EFL", "USL", "CONMEBOL", "ARGPREM", "DIMAYOR", "BRAS", "ERED", "SAUDI", "SCOT", "LIGA", "UEL", "UECL")):
                    if (fs is not None and float(fs) <= 1.5) or m_tk.endswith("-1") or m_tk.endswith("-2"):
                        return "FLOOR_TOTALS"
                elif "KXMLBTOTAL" in tk or "MLB" in tk:
                    if (fs is not None and float(fs) <= 6.5) or any(m_tk.endswith(f"-{k}") for k in ("2", "3", "4", "5", "6")):
                        return "FLOOR_TOTALS"
                elif "KXNFLTOTAL" in tk or "NFL" in tk:
                    if (fs is not None and float(fs) <= 34.5) or any(m_tk.endswith(f"-{k}") for k in ("22", "25", "28", "31", "34")):
                        return "FLOOR_TOTALS"
            if any(term in comb for term in ("OVER 0.5", "OVER 1.5", "OVER 2.5", "OVER 3.5", "OVER 4.5", "OVER 5.5", "OVER 31.5", "OVER 27.5", "OVER 24.5")):
                return "FLOOR_TOTALS"

        # 2. Milestone Contact / Floor Props: MLB 1+ HRR (0.5 line), NBA 15+ pts
        if prop_sub == "HITS_RUNS_RBIS" or "HRR" in tk or "1+ HITS" in comb or "1+ BASES" in comb:
            return "MILESTONE_PROPS"
        if "KXNBAPTS" in tk and any(term in comb for term in ("14.5", "15.5", "10.5", "12.5")):
            return "MILESTONE_PROPS"
    except Exception:
        pass
    return "STANDARD"

def is_event_allowed_for_user(evt: dict, user: Optional[dict], query_filter: str = "", strategy: Optional[str] = None) -> bool:
    """
    Filters events so that only ACTIVE AI predictions matching the user's
    selected sports, strategy, and markets/props in settings are returned.
    If the user explicitly selected a sport tab (query_filter is not empty or 'ALL'),
    allow that sport so the user can browse active picks for that tab.
    """
    # 1. Must have an active AI prediction
    if not evt.get("has_ai_prediction"):
        return False
    ai_pick = evt.get("ai_pick")
    if not ai_pick or str(ai_pick).strip() in ("", "None", "null"):
        return False
    try:
        conf = float(evt.get("confidence_pct", 0.0) or 0.0)
    except (ValueError, TypeError):
        conf = 0.0
    if conf <= 0.0:
        return False

    clean_qf = str(query_filter or "").strip().upper()
    clean_strat = str(strategy or "").strip().upper()

    # Explicit strategy query filter check (only when query_filter itself is a strategy name)
    if clean_qf in ("FLOOR_TOTALS", "MILESTONE_PROPS", "POWER_COMBO", "ULTRA_COMBO", "MEGA_PARLAY", "STANDARD"):
        evt_strat = evt.get("strategy_tag") or classify_event_strategy(evt)
        if clean_qf in ("POWER_COMBO", "ULTRA_COMBO", "MEGA_PARLAY"):
            return evt_strat in ("FLOOR_TOTALS", "MILESTONE_PROPS") or conf >= 65.0
        return evt_strat == clean_qf

    if not user:
        return True

    # User configured sports strategy check
    user_strat = clean_strat or str(user.get("sports_strategy") or "STANDARD").strip().upper()
    evt_strat = evt.get("strategy_tag") or classify_event_strategy(evt)

    # If the user explicitly clicked a specific sport tab (e.g. NHL, NFL, MLB, SOC, UFC, etc.),
    # allow events for that sport to display even if auto-trading was toggled off for it in the settings drawer.
    if clean_qf and clean_qf not in ("ALL", ""):
        return True

    # For FLOOR_TOTALS,POWER_COMBO,ULTRA_COMBO,MEGA_PARLAY: always allow FLOOR_TOTALS and MILESTONE_PROPS
    # regardless of per-sport 'on' or 'markets' checkboxes so floor lines and mega parlays never show an empty slate.
    if user_strat in ("FLOOR_TOTALS", "POWER_COMBO", "ULTRA_COMBO", "MEGA_PARLAY") and evt_strat == "FLOOR_TOTALS":
        return True
    if user_strat in ("MILESTONE_PROPS", "POWER_COMBO", "ULTRA_COMBO", "MEGA_PARLAY") and evt_strat == "MILESTONE_PROPS":
        return True

    # 2. Check sports settings (memoized on user dict for O(1) across 1,000+ events)
    if "_parsed_sport_cfg_tuple" in user:
        sport_config, fallback_leagues, fallback_markets, fallback_props = user["_parsed_sport_cfg_tuple"]
    else:
        raw_sport_config = user.get("sports_sport_config")
        sport_config = {}
        if raw_sport_config:
            try:
                if isinstance(raw_sport_config, str):
                    sport_config = json.loads(raw_sport_config)
                elif isinstance(raw_sport_config, dict):
                    sport_config = raw_sport_config
            except Exception:
                sport_config = {}

        def _parse_list(val):
            if not val:
                return []
            if isinstance(val, list):
                return [str(x).strip().upper() for x in val if x]
            return [str(x).strip().upper() for x in str(val).split(",") if x.strip()]

        fallback_leagues = _parse_list(user.get("sports_active_leagues"))
        fallback_markets = _parse_list(user.get("sports_market_types"))
        fallback_props = _parse_list(user.get("sports_active_props"))
        user["_parsed_sport_cfg_tuple"] = (sport_config, fallback_leagues, fallback_markets, fallback_props)

    raw_sport = evt.get("sport") or evt.get("league") or ""
    sport_key = normalize_sport_key(raw_sport)
    alt_keys = [sport_key]
    if "/" in sport_key:
        alt_keys.extend(sport_key.split("/"))
    elif sport_key in ("NPB", "KBO"):
        alt_keys.append("NPB/KBO")

    sport_enabled = False
    sport_entry = None
    for k in alt_keys:
        if k in sport_config:
            sport_entry = sport_config[k]
            break

    if sport_entry is not None and isinstance(sport_entry, dict):
        sport_enabled = bool(sport_entry.get("on", True))
    elif fallback_leagues:
        sport_enabled = any(k in fallback_leagues for k in alt_keys)
    else:
        sport_enabled = True

    if not sport_enabled:
        return False

    # Always permit Floor Totals (e.g. Soccer Over 0.5 goals & NHL Over 2.5 goals) when the sport is enabled
    if evt_strat == "FLOOR_TOTALS":
        return True

    # 3. Classify market and prop (memoized on evt dict)
    if "_cached_mkt_prop" in evt:
        mkt_cat, prop_sub = evt["_cached_mkt_prop"]
    else:
        mkt_cat, prop_sub = classify_event_market_and_prop(evt)
        evt["_cached_mkt_prop"] = (mkt_cat, prop_sub)

    allowed_markets = None
    if sport_entry is not None and isinstance(sport_entry, dict) and "markets" in sport_entry:
        allowed_markets = [str(m).strip().upper() for m in (sport_entry.get("markets") or [])]
    elif fallback_markets:
        allowed_markets = fallback_markets

    # If the user or filter has active strategy (e.g. FLOOR_TOTALS, POWER_COMBO, ULTRA_COMBO), permit TOTAL and PROP markets
    active_strat = clean_qf if clean_qf in ("FLOOR_TOTALS", "MILESTONE_PROPS", "POWER_COMBO", "ULTRA_COMBO", "MEGA_PARLAY") else user_strat
    if active_strat in ("FLOOR_TOTALS", "POWER_COMBO", "ULTRA_COMBO", "MEGA_PARLAY") and (evt_strat == "FLOOR_TOTALS" or mkt_cat == "TOTAL"):
        pass
    elif active_strat in ("MILESTONE_PROPS", "POWER_COMBO", "ULTRA_COMBO", "MEGA_PARLAY") and (evt_strat == "MILESTONE_PROPS" or mkt_cat == "PROP"):
        pass
    elif allowed_markets is not None:
        if mkt_cat not in allowed_markets:
            return False

    # 4. If PROP, check allowed props
    if mkt_cat == "PROP":
        if active_strat in ("MILESTONE_PROPS", "POWER_COMBO", "ULTRA_COMBO", "MEGA_PARLAY") and evt_strat == "MILESTONE_PROPS":
            pass
        else:
            allowed_props = None
            if sport_entry is not None and isinstance(sport_entry, dict) and "props" in sport_entry:
                allowed_props = [str(p).strip().upper() for p in (sport_entry.get("props") or [])]
            elif fallback_props:
                allowed_props = fallback_props

            if allowed_props is not None:
                if prop_sub not in allowed_props:
                    return False

    return True

_SPORTS_AGG_REFRESHING = set()

def fetch_sports_events_data(query_filter: str = "", user: Optional[dict] = None, strategy: Optional[str] = None, _force_sync: bool = False) -> list:
    try:
        from backend.engine.kalshi_events_cache import get_series_events, get_milestone_map
        from backend.engine.market_matcher import find_best_market_for_pick
        
        query_filter = str(query_filter or "").strip().upper()
        now = time.time()
        active_strat_target = (strategy or (query_filter if query_filter in ("FLOOR_TOTALS", "MILESTONE_PROPS", "POWER_COMBO", "ULTRA_COMBO", "MEGA_PARLAY") else (user.get("sports_strategy") if user else None))) or "STANDARD"
        active_strat_target = str(active_strat_target).upper().strip()
        cache_key = f"{query_filter}:{active_strat_target}"
        
        if not _force_sync:
            with _SPORTS_AGG_CACHE_LOCK:
                if cache_key in _SPORTS_AGG_CACHE:
                    ts, cached_raw = _SPORTS_AGG_CACHE[cache_key]
                    if now - ts >= _SPORTS_AGG_CACHE_TTL and cached_raw and cache_key not in _SPORTS_AGG_REFRESHING:
                        _SPORTS_AGG_REFRESHING.add(cache_key)
                        def _bg_refresh_agg(qf=query_filter, st=active_strat_target, ck=cache_key):
                            try:
                                fetch_sports_events_data(query_filter=qf, user=None, strategy=st, _force_sync=True)
                            finally:
                                with _SPORTS_AGG_CACHE_LOCK:
                                    _SPORTS_AGG_REFRESHING.discard(ck)
                        threading.Thread(target=_bg_refresh_agg, daemon=True, name="SportsAggRefresh").start()
                    if (now - ts < _SPORTS_AGG_CACHE_TTL) or cached_raw:
                        filtered_events = [e for e in cached_raw if is_event_allowed_for_user(e, user, query_filter, strategy=active_strat_target)] if user else list(cached_raw)
                        if not filtered_events and cached_raw and query_filter in ("", "ALL"):
                            filtered_events = [e for e in cached_raw if e.get("has_ai_prediction") and e.get("ai_pick")]
                        filtered_events.sort(key=lambda x: float(x.get("start_epoch") or 9999999999.0))
                        return filtered_events

                # Fallback: if a specific sport filter or strategy is requested and a global cache is already warm, filter from it immediately while warming cache_key in background!
                global_ck = f"ALL:{active_strat_target}"
                fallback_cks = [f"ALL:{active_strat_target}", f":{active_strat_target}", "ALL:STANDARD", ":STANDARD"]
                for f_ck in fallback_cks:
                    if f_ck in _SPORTS_AGG_CACHE and _SPORTS_AGG_CACHE[f_ck][1]:
                        _, global_raw = _SPORTS_AGG_CACHE[f_ck]
                        sport_norm = normalize_sport_key(query_filter) if query_filter else ""
                        sub_raw = [e for e in global_raw if not sport_norm or normalize_sport_key(e.get("sport") or e.get("league") or "") == sport_norm] if sport_norm not in ("", "ALL") else list(global_raw)
                        if sub_raw or sport_norm in ("", "ALL"):
                            if cache_key not in _SPORTS_AGG_CACHE and cache_key not in _SPORTS_AGG_REFRESHING:
                                _SPORTS_AGG_REFRESHING.add(cache_key)
                                def _bg_warm_strat(qf=query_filter, st=active_strat_target, ck=cache_key):
                                    try:
                                        fetch_sports_events_data(query_filter=qf, user=None, strategy=st, _force_sync=True)
                                    finally:
                                        with _SPORTS_AGG_CACHE_LOCK:
                                            _SPORTS_AGG_REFRESHING.discard(ck)
                                threading.Thread(target=_bg_warm_strat, daemon=True, name="SportsAggWarmStrat").start()
                            filtered_events = [e for e in sub_raw if is_event_allowed_for_user(e, user, query_filter, strategy=active_strat_target)] if user else list(sub_raw)
                            filtered_events.sort(key=lambda x: float(x.get("start_epoch") or 9999999999.0))
                            return filtered_events

                # If cache is completely cold and already refreshing in background, check if any warm cache exists to serve immediately
                if cache_key in _SPORTS_AGG_REFRESHING or global_ck in _SPORTS_AGG_REFRESHING:
                    # Serve ANY existing populated key from _SPORTS_AGG_CACHE rather than returning []
                    for ck, (ts, cached_raw) in _SPORTS_AGG_CACHE.items():
                        if cached_raw:
                            sport_norm = normalize_sport_key(query_filter) if query_filter else ""
                            sub_raw = [e for e in cached_raw if not sport_norm or normalize_sport_key(e.get("sport") or e.get("league") or "") == sport_norm] if sport_norm not in ("", "ALL") else list(cached_raw)
                            if sub_raw:
                                filtered_events = [e for e in sub_raw if is_event_allowed_for_user(e, user, query_filter, strategy=active_strat_target)] if user else list(sub_raw)
                                filtered_events.sort(key=lambda x: float(x.get("start_epoch") or 9999999999.0))
                                return filtered_events
                    # If truly no data has ever been cached yet, give it up to 6.0s to finish initial cold start
                    for _ in range(60):
                        time.sleep(0.1)
                        if cache_key in _SPORTS_AGG_CACHE and _SPORTS_AGG_CACHE[cache_key][1]:
                            _, cached_raw = _SPORTS_AGG_CACHE[cache_key]
                            filtered_events = [e for e in cached_raw if is_event_allowed_for_user(e, user, query_filter, strategy=active_strat_target)] if user else list(cached_raw)
                            filtered_events.sort(key=lambda x: float(x.get("start_epoch") or 9999999999.0))
                            return filtered_events
                    return []
                _SPORTS_AGG_REFRESHING.add(cache_key)
                def _bg_cold_start(qf=query_filter, st=active_strat_target, ck=cache_key):
                    try:
                        fetch_sports_events_data(query_filter=qf, user=None, strategy=st, _force_sync=True)
                    finally:
                        with _SPORTS_AGG_CACHE_LOCK:
                            _SPORTS_AGG_REFRESHING.discard(ck)
                threading.Thread(target=_bg_cold_start, daemon=True, name="SportsAggColdStart").start()
            # Wait up to 6.0s for cold start to finish if fast, otherwise serve stale or partial
            for _ in range(60):
                time.sleep(0.1)
                with _SPORTS_AGG_CACHE_LOCK:
                    if cache_key in _SPORTS_AGG_CACHE and _SPORTS_AGG_CACHE[cache_key][1]:
                        _, cached_raw = _SPORTS_AGG_CACHE[cache_key]
                        filtered_events = [e for e in cached_raw if is_event_allowed_for_user(e, user, query_filter, strategy=active_strat_target)] if user else list(cached_raw)
                        filtered_events.sort(key=lambda x: float(x.get("start_epoch") or 9999999999.0))
                        return filtered_events
            return []
    
        norm_qf = normalize_sport_key(query_filter)
        if norm_qf == "NPB/KBO":
            target_sports = [("NPB", "NPB/KBO", "NPB"), ("KBO", "NPB/KBO", "KBO")]
        elif norm_qf == "SOC":
            target_sports = [("SOC", "SOC", "SOC")]
        elif norm_qf == "TEN":
            target_sports = [("TEN", "TEN", "TEN")]
        elif norm_qf == "UFC":
            target_sports = [("UFC", "UFC", "UFC")]
        elif norm_qf in ("NBA", "NCAAF", "MLB", "NFL", "NHL"):
            target_sports = [(norm_qf, norm_qf, norm_qf)]
        elif query_filter in _SPORTS_SERIES_MAP:
            target_sports = [(query_filter, query_filter, query_filter)]
        else:
            target_sports = [
                ("NPB", "NPB/KBO", "NPB"),
                ("KBO", "NPB/KBO", "KBO"),
                ("NFL", "NFL", "NFL"),
                ("MLB", "MLB", "MLB"),
                ("NHL", "NHL", "NHL"),
                ("NBA", "NBA", "NBA"),
                ("NCAAF", "NCAAF", "NCAAF"),
                ("SOC", "SOC", "SOC"),
                ("UFC", "UFC", "UFC"),
                ("TEN", "TEN", "TEN"),
            ]
            
        import difflib
        import unicodedata
        from datetime import timezone
        from backend.engine.market_matcher import SOCCER_ALIASES, SOCCER_STOP_WORDS

        def _sa(s):
            return ''.join(ch for ch in unicodedata.normalize('NFD', str(s or '')) if unicodedata.category(ch) != 'Mn').lower()

        _UFC_SUFFIXES = {'jr', 'sr', 'ii', 'iii', 'iv', 'v'}
        def _get_fighter_surname(name_str):
            if not name_str:
                return ""
            tokens = [w for w in re.findall(r'[a-z0-9]+', _sa(name_str)) if w]
            while tokens and tokens[-1] in _UFC_SUFFIXES:
                tokens.pop()
            return tokens[-1] if tokens else ""

        def _surname_match(s1, s2):
            if not s1 or not s2:
                return False
            if s1 == s2:
                return True
            if len(s1) >= 4 and len(s2) >= 4:
                if difflib.SequenceMatcher(None, s1, s2).ratio() >= 0.85:
                    return True
            return False

        client = SportsPredictionClient(use_kalshi_bridge=USE_KALSHI_BRIDGE)
        latest_picks = []
        try:
            latest_picks = client.fetch_latest_picks()
        except Exception:
            pass

        # Pre-index latest_picks ONCE by market ticker (O(1)) and by sport bucket with pre-parsed tokens/dates
        picks_by_mkt_ticker = {}
        picks_by_sport = {}
        for p in latest_picks:
            kt = p.get("kalshi_market_ticker")
            if kt and kt not in picks_by_mkt_ticker:
                picks_by_mkt_ticker[kt] = p

            p_sport_raw = (p.get("sport") or "").upper()
            if p_sport_raw == "SOCCER":
                p_sport_raw = "SOC"
            elif p_sport_raw == "TENNIS":
                p_sport_raw = "TEN"
            elif p_sport_raw == "MMA":
                p_sport_raw = "UFC"

            p_meta = p.get("metadata") or {}
            p_mtype = str(p.get("market_type") or p_meta.get("type") or "").upper()
            p_team = _sa(p.get("predicted_team") or "")
            p_matchup = _sa(p_meta.get("matchup") or "")
            p_m_tokens = {w for w in re.findall(r'[a-z0-9]+', p_matchup) if len(w) >= 3} if p_matchup else set()
            p_tokens = {w for w in re.findall(r'[a-z0-9]+', p_team) if len(w) >= 3} if p_team else set()

            p_dt = None
            p_date_str = p_meta.get("date")
            if p_date_str:
                try:
                    p_dt = datetime.fromisoformat(str(p_date_str).replace("Z", "+00:00")).date()
                except Exception:
                    pass

            p_team_sur = _get_fighter_surname(p_team) if p_sport_raw == "UFC" else ""
            p_m_surnames = [_get_fighter_surname(pt) for pt in re.split(r'\s+(?:vs\.?|at|@)\s+', p_matchup) if pt] if (p_sport_raw == "UFC" and p_matchup) else []
            p_toks_f = {w for w in p_tokens if w not in SOCCER_STOP_WORDS} if p_sport_raw == "SOC" else set()
            p_m_toks_f = {w for w in p_m_tokens if w not in SOCCER_STOP_WORDS} if p_sport_raw == "SOC" else set()
            p_ten_m = (p_matchup if p_matchup else p_team) if p_sport_raw == "TEN" else ""
            p_ten_parts = re.split(r'\s+(?:vs\.?|at|@)\s+', p_ten_m) if p_ten_m else []

            entry = (
                p, p_mtype, p_team, p_matchup, p_m_tokens, p_tokens, p_dt,
                p_team_sur, p_m_surnames, p_toks_f, p_m_toks_f, p_ten_m, p_ten_parts
            )
            picks_by_sport.setdefault(p_sport_raw, []).append(entry)
            if p_sport_raw in ("NPB", "KBO"):
                picks_by_sport.setdefault("NPB/KBO", []).append(entry)

        milestone_map = get_milestone_map()
        kalshi_events = []
        seen_tickers = set()
        now_et = datetime.now(ZoneInfo("America/New_York"))
        today_et = now_et.date()
        now_ts = time.time()
        now_utc = datetime.now(timezone.utc)
        
        for series_key, sport_tag, league_tag in target_sports:
            sport_pick_bucket = picks_by_sport.get(series_key) or picks_by_sport.get(sport_tag) or picks_by_sport.get(league_tag) or []
            series_tickers = _SPORTS_SERIES_MAP.get(series_key, [])
            for series in series_tickers:
                raw_events_data = get_series_events(series)
                events_data = []
                if "TEAMTOTAL" in series:
                    for raw_e in raw_events_data:
                        team_groups = {}
                        for m in raw_e.get("markets", []):
                            yst = (m.get("yes_sub_title") or "").strip()
                            t_pref = yst.split(":", 1)[0].strip() if ":" in yst else "TEAM"
                            team_groups.setdefault(t_pref, []).append(m)
                        if len(team_groups) > 1:
                            for t_pref, t_mkts in team_groups.items():
                                sub_e = dict(raw_e)
                                sub_e["markets"] = t_mkts
                                sub_e["_dedup_key"] = f"{raw_e.get('event_ticker')}:{t_pref}"
                                events_data.append(sub_e)
                        else:
                            events_data.append(raw_e)
                else:
                    events_data = raw_events_data
                
                for e in events_data:
                    event_ticker = e.get('event_ticker') or ''
                    dedup_key = e.get('_dedup_key') or event_ticker
                    if not event_ticker or dedup_key in seen_tickers:
                        continue
                        
                    title = e.get('title') or 'Event'
                    sub = e.get('sub_title') or 'Match'
                    
                    milestone = milestone_map.get(event_ticker) or (milestone_map.get(f"SUFFIX:{event_ticker.split('-', 1)[1]}") if '-' in event_ticker else None)
                    start_epoch = None
                    ev_date = None
                    if milestone and milestone.get('start_date'):
                        try:
                            dt = datetime.fromisoformat(milestone['start_date'].replace('Z', '+00:00')).astimezone(ZoneInfo('America/New_York'))
                            ev_date = dt.date()
                            start_epoch = dt.timestamp()
                        except Exception:
                            pass
                    if not ev_date or not start_epoch:
                        ev_date, start_epoch = extract_sports_event_date_and_time(event_ticker, event_obj=e)
                        
                    max_game_dur = 7800 if sport_tag == "SOC" else 14400
                    if start_epoch and (now_ts - start_epoch > max_game_dur):
                        continue
                    is_live = bool(start_epoch and (start_epoch <= now_ts) and (now_ts - start_epoch <= max_game_dur))
                    if ev_date and ev_date < today_et and not is_live:
                        continue
                        
                    seen_tickers.add(dedup_key)
                    is_today = (ev_date == today_et)
                    
                    event_participants = []
                    for mkt in e.get("markets", []):
                        yst = (mkt.get("yes_sub_title") or "").strip()
                        m_title = (mkt.get("title") or "").strip()
                        cand = yst
                        if not cand or cand.lower() in ("yes", "no"):
                            cand = re.sub(r'\s+wins\??$', '', m_title, flags=re.IGNORECASE).strip()
                        if cand and re.search(r'(?:^over\s|^under\s|goals?\s+scored|runs?\s+scored|points?\s+scored|total\s+|wins?\s+by|reg\s+time:|1st\s+half|2nd\s+half|1st\s+period|2nd\s+period|3rd\s+period)', cand, flags=re.IGNORECASE):
                            continue
                        if cand and cand.lower() not in ("tie", "draw", "tie is the result", "draw is the result") and cand not in event_participants:
                            event_participants.append(cand)

                    clean_matchup = title
                    if ':' in clean_matchup:
                        left_p, right_p = clean_matchup.split(':', 1)
                        if re.search(r'\s+(?:vs\.?|at|@)\s+', left_p, flags=re.IGNORECASE):
                            clean_matchup = left_p.strip()
                        else:
                            clean_matchup = right_p.strip()
                    clean_matchup = re.sub(r'\s+(?:at|@)\s+', ' vs ', clean_matchup, flags=re.IGNORECASE)

                    # Check for standard Kalshi sports ticker team codes (e.g. -26OCT09NYRWSH, -26OCT11CHIGB, -26OCT11SFSEA)
                    ticker_matchup = None
                    ticker_part = event_ticker.split('-')[1] if '-' in event_ticker else event_ticker
                    s_map = _SPORT_TEAM_MAP.get(sport_tag, {})
                    if s_map:
                        code_suffix = re.sub(r'^\d{2}[A-Z]{3}\d{2}(?:\d{4})?', '', ticker_part)
                        for l1 in (2, 3):
                            for l2 in (2, 3):
                                if len(code_suffix) == l1 + l2:
                                    c1, c2 = code_suffix[:l1], code_suffix[l1:]
                                    n1_full = s_map.get(c1)
                                    n2_full = s_map.get(c2)
                                    if n1_full and n2_full:
                                        ticker_matchup = f"{n1_full} vs {n2_full}"
                                        break
                            if ticker_matchup:
                                break

                    if ticker_matchup:
                        clean_matchup = ticker_matchup
                    elif len(event_participants) >= 2 and (clean_matchup.lower().startswith("tie") or " wins" in clean_matchup.lower() or "vs" not in clean_matchup.lower()):
                        clean_matchup = f"{event_participants[0]} vs {event_participants[1]}"
                    elif len(event_participants) == 1 and (clean_matchup.lower().startswith("tie") or " wins" in clean_matchup.lower()):
                        clean_matchup = event_participants[0]

                    if not event_participants and " vs " in clean_matchup:
                        event_participants = [p.strip() for p in clean_matchup.split(" vs ") if p.strip()]

                    clean_matchup_norm = _sa(clean_matchup)
                    team_tokens = {w for w in re.findall(r'[a-z0-9]+', clean_matchup_norm) if len(w) >= 3 and w not in ('the', 'team', 'club', 'fc', 'wins', 'result')}
                    for p_name in event_participants:
                        for tok in re.findall(r'[a-z0-9]+', _sa(p_name)):
                            if len(tok) >= 3 and tok not in ('the', 'team', 'club', 'fc', 'wins', 'result'):
                                team_tokens.add(tok)
                    
                    best_pick = None
                    has_valid_pick = False
                    
                    if USE_KALSHI_BRIDGE and picks_by_mkt_ticker:
                        for m in e.get("markets", []):
                            m_tk = m.get("ticker")
                            if m_tk and m_tk in picks_by_mkt_ticker:
                                has_valid_pick = True
                                best_pick = picks_by_mkt_ticker[m_tk]
                                break

                    ev_type_info = parse_sports_market_details(ticker=event_ticker, title=title, series=series_key, markets=e.get('markets', []))
                    ev_prop_type = ev_type_info.get("prop_type", "")
                    
                    if not best_pick and sport_pick_bucket:
                        best_score = 0
                        ev_tk_upper = str(event_ticker).upper()
                        is_ufc = (sport_tag in ("UFC", "MMA") or series_key in ("UFC", "MMA") or "UFC" in ev_tk_upper)

                        # Event-level disqualifiers that apply across all picks
                        is_deriv_or_future = (
                            any(k in ev_tk_upper for k in ("TEAMTOTAL", "1PTOTAL", "2PTOTAL", "3PTOTAL", "F5TOTAL", "HALFTOTAL", "Q1TOTAL", "Q2TOTAL", "Q3TOTAL", "Q4TOTAL"))
                            or ev_prop_type in ("Period", "PERIOD")
                            or any(k in ev_tk_upper for k in ("KXNHLF10G", "KXNHLOT", "KXNHL1P", "KXNHL2P", "KXNHL3P"))
                            or ev_prop_type in ("Futures", "FUTURES")
                            or any(k in ev_tk_upper for k in ("-27AO", "-27FO", "-27WIM", "-27USO", "CHAMPION", "TOURNAMENT", "SERIESWINNER"))
                        )

                        if not is_deriv_or_future:
                            ev_ufc_surnames = []
                            if is_ufc:
                                for p_name in event_participants:
                                    sur = _get_fighter_surname(p_name)
                                    if sur and sur not in ev_ufc_surnames:
                                        ev_ufc_surnames.append(sur)
                                if not ev_ufc_surnames and clean_matchup:
                                    for part in re.split(r'\s+(?:vs\.?|at|@)\s+', clean_matchup):
                                        sur = _get_fighter_surname(part)
                                        if sur and sur not in ev_ufc_surnames:
                                            ev_ufc_surnames.append(sur)

                            c_ten_parts = re.split(r'\s+(?:vs\.?|at|@)\s+', clean_matchup_norm) if sport_tag == "TEN" else []
                            ms_h = milestone.get('home_team_name', '').lower() if milestone else ''
                            ms_a = milestone.get('away_team_name', '').lower() if milestone else ''

                            # Pre-parse soccer participant tokens once per event
                            soc_part_data = []
                            if sport_tag == "SOC" or series_key == "SOC":
                                for ep in event_participants[:2]:
                                    c_clean = _sa(ep).strip()
                                    c_norm = SOCCER_ALIASES.get(c_clean, c_clean)
                                    c_toks = {w for w in re.findall(r'[a-z0-9]+', c_clean) if len(w) >= 3 and w not in SOCCER_STOP_WORDS}
                                    soc_part_data.append((c_norm, c_toks))

                            for (
                                p, p_mtype, p_team, p_matchup, p_m_tokens, p_tokens, p_dt,
                                p_team_sur, p_m_surnames, p_toks_f, p_m_toks_f, p_ten_m, p_ten_parts
                            ) in sport_pick_bucket:
                                # Type matching
                                is_mismatch = False
                                if ev_prop_type in ("Player Prop", "PLAYER PROP") and not any(k in p_mtype for k in ("PROP", "PLAYER")):
                                    is_mismatch = True
                                elif ev_prop_type == "Spread" and not any(k in p_mtype for k in ("SPREAD", "PUCK LINE", "RUN LINE")):
                                    is_mismatch = True
                                elif ev_prop_type == "Total (O/U)" and not any(k in p_mtype for k in ("TOTAL", "OVER", "UNDER", "O/U")):
                                    is_mismatch = True
                                elif ev_prop_type == "Moneyline" and (any(k in p_mtype for k in ("TOTAL", "SPREAD", "PROP", "OVER", "UNDER", "PUCK LINE", "RUN LINE", "PLAYER")) or p_team.startswith(("over", "under", "total", "inside distance"))):
                                    is_mismatch = True

                                if is_mismatch:
                                    continue

                                cand_score = 0

                                if is_ufc:
                                    team_match = any(_surname_match(p_team_sur, es) for es in ev_ufc_surnames if es)
                                    m_overlap = sum(1 for pm_s in p_m_surnames if pm_s and any(_surname_match(pm_s, es) for es in ev_ufc_surnames if es))

                                    if m_overlap >= 2 and team_match:
                                        cand_score = 300
                                    elif m_overlap >= 2:
                                        cand_score = 250
                                    elif team_match and len(p_m_surnames) <= 1:
                                        cand_score = 150
                                    elif team_match and m_overlap >= 1:
                                        cand_score = 120
                                else:
                                    if p_matchup:
                                        p_dt_days_diff = abs((p_dt - ev_date).days) if (p_dt and ev_date) else None

                                        if team_tokens and (team_tokens == p_m_tokens or team_tokens.issubset(p_m_tokens) or p_m_tokens.issubset(team_tokens)):
                                            cand_score = max(cand_score, 200)
                                        elif team_tokens and len(p_m_tokens & team_tokens) >= 2:
                                            cand_score = max(cand_score, 100 + len(p_m_tokens & team_tokens) * 10)
                                        elif team_tokens and (p_m_tokens & team_tokens) and ev_prop_type not in ("Total (O/U)", "Spread"):
                                            if p_dt_days_diff is not None and p_dt_days_diff <= 1:
                                                cand_score = max(cand_score, 50 + len(p_m_tokens & team_tokens) * 10)

                                    if ev_prop_type not in ("Total (O/U)", "Spread"):
                                        if team_tokens and (p_tokens & team_tokens):
                                            cand_score = max(cand_score, 80 + len(p_tokens & team_tokens) * 10)
                                        elif p_team and len(p_team) >= 3 and re.search(rf"\b{re.escape(p_team)}\b", clean_matchup.lower()):
                                            cand_score = max(cand_score, 85)

                                    if milestone:
                                        if (ms_h and ms_h in p_team) or (ms_a and ms_a in p_team) or (ms_h and ms_h in p_matchup and ms_a and ms_a in p_matchup):
                                            cand_score = max(cand_score, 90)
                                        if p_mtype in ("TOTAL", "OVER/UNDER", "SPREAD", "PUCK LINE"):
                                            if (ms_h and ms_h in p_matchup) or (ms_a and ms_a in p_matchup):
                                                cand_score = max(cand_score, 90)

                                    if soc_part_data:
                                        def _match_soc_part(c_norm, c_toks, p_tok_set, p_str):
                                            if c_norm and (c_norm in p_str or p_str in c_norm):
                                                return True
                                            for part in re.split(r'\s+(?:vs\.?|at|@)\s+', p_str):
                                                p_clean = part.strip()
                                                p_norm = SOCCER_ALIASES.get(p_clean, p_clean)
                                                if p_norm and (c_norm == p_norm or c_norm in p_norm or p_norm in c_norm):
                                                    return True
                                            if not c_toks:
                                                return False
                                            if (c_toks & p_tok_set) or c_toks.issubset(p_tok_set) or p_tok_set.issubset(c_toks):
                                                return True
                                            return any(difflib.SequenceMatcher(None, t1, t2).ratio() >= 0.75 for t1 in c_toks for t2 in p_tok_set)

                                        if len(soc_part_data) >= 2:
                                            p1_ok = _match_soc_part(soc_part_data[0][0], soc_part_data[0][1], p_m_toks_f, p_matchup)
                                            p2_ok = _match_soc_part(soc_part_data[1][0], soc_part_data[1][1], p_m_toks_f, p_matchup)
                                            if p1_ok and p2_ok:
                                                cand_score = max(cand_score, 250)
                                            elif not p_matchup and (_match_soc_part(soc_part_data[0][0], soc_part_data[0][1], p_toks_f, p_team) or _match_soc_part(soc_part_data[1][0], soc_part_data[1][1], p_toks_f, p_team)):
                                                cand_score = max(cand_score, 120)
                                        elif soc_part_data:
                                            if _match_soc_part(soc_part_data[0][0], soc_part_data[0][1], p_m_toks_f, p_matchup) or (not p_matchup and _match_soc_part(soc_part_data[0][0], soc_part_data[0][1], p_toks_f, p_team)):
                                                cand_score = max(cand_score, 120)

                                    if sport_tag == "TEN" and len(c_ten_parts) == 2 and len(p_ten_parts) == 2 and c_ten_parts[0] and c_ten_parts[1] and p_ten_parts[0] and p_ten_parts[1]:
                                        c1, c2 = c_ten_parts[0].split()[-1], c_ten_parts[1].split()[-1]
                                        p1, p2 = p_ten_parts[0].split()[-1], p_ten_parts[1].split()[-1]
                                        if (c1 in p_ten_m and c2 in p_ten_m) or (p1 in clean_matchup_norm and p2 in clean_matchup_norm):
                                            date_match = (abs((p_dt - ev_date).days) <= 2) if (p_dt and ev_date) else True
                                            if date_match:
                                                cand_score = max(cand_score, 250)

                                if cand_score > best_score:
                                    best_score = cand_score
                                    best_pick = p

                            if best_pick and best_score > 0:
                                has_valid_pick = True
                            
                    all_markets = e.get("markets", [])
                    markets = []
                    for m in all_markets:
                        m_stat = str(m.get("status") or "").lower()
                        if m_stat in ("closed", "settled", "determined") or m.get("paused"):
                            continue
                        ct_str = m.get("close_time")
                        if ct_str:
                            try:
                                ct_dt = datetime.fromisoformat(ct_str.replace("Z", "+00:00"))
                                if ct_dt < now_utc:
                                    continue
                            except:
                                pass
                        markets.append(m)
                    if not markets:
                        continue

                    def parse_price(mkt, field):
                        if not mkt: return 0.0
                        val_dollars = mkt.get(field + '_dollars')
                        if val_dollars is not None:
                            try: return float(val_dollars)
                            except: pass
                        val_cents = mkt.get(field)
                        if val_cents is not None:
                            try:
                                fv = float(val_cents)
                                return round(fv / 100.0, 4) if fv > 1.0 else round(fv, 4)
                            except: pass
                        return 0.0

                    # Filter out already-decided / finished games awaiting Kalshi settlement (1c / 99c-100c across all moneyline markets)
                    if ("MATCH" in series or "GAME" in series or "FIGHT" in series) and markets:
                        all_decided = True
                        for m_chk in markets:
                            ya_chk = parse_price(m_chk, 'yes_ask')
                            yb_chk = parse_price(m_chk, 'yes_bid')
                            nb_chk = parse_price(m_chk, 'no_bid')
                            eff_p = ya_chk if ya_chk > 0 else (round(1.0 - nb_chk, 4) if nb_chk > 0 else yb_chk)
                            if 0.02 < eff_p < 0.98 and yb_chk < 0.98 and nb_chk < 0.98:
                                all_decided = False
                                break
                        if all_decided:
                            continue
                        
                    pred_pick_name = best_pick.get("predicted_team") or best_pick.get("team_or_player") if best_pick else None
                    conf = float(best_pick.get("confidence_pct", 0.0)) if best_pick else 0.0
                    if 0 < conf <= 1.0:
                        conf *= 100.0
                    edge = float(best_pick.get("edge_pct", 0.0)) if best_pick else 0.0
                    
                    best_mkt = None
                    is_alt_line = False
                    is_yes_side = True
                    
                    active_strat_target = (strategy or (query_filter if query_filter in ("FLOOR_TOTALS", "MILESTONE_PROPS", "POWER_COMBO", "ULTRA_COMBO", "MEGA_PARLAY") else (user.get("sports_strategy") if user else None))) or "STANDARD"
                    active_strat_target = active_strat_target.upper().strip()

                    # Direct Floor-Total synthesis & locking for Soccer Over 0.5 Goals and Hockey Over 2.5 Goals
                    floor_locked = False
                    if sport_tag in ("SOC", "NHL") and "TOTAL" in series:
                        target_floor_strike = 0.5 if sport_tag == "SOC" else 2.5
                        floor_mkt = next(
                            (m for m in markets if m.get("floor_strike") is not None and abs(float(m.get("floor_strike")) - target_floor_strike) < 0.01),
                            None
                        )
                        if floor_mkt:
                            best_mkt = floor_mkt
                            is_yes_side = True
                            is_alt_line = True
                            floor_locked = True
                            markets = [best_mkt] + [m for m in markets if m != best_mkt]
                            f_ya = parse_price(best_mkt, 'yes_ask')
                            f_nb = parse_price(best_mkt, 'no_bid')
                            f_lp = parse_price(best_mkt, 'last_price')
                            if f_ya <= 0.0 and f_nb > 0.0:
                                f_ya = round(1.0 - f_nb, 4)
                            if f_ya <= 0.0 and f_lp > 0.0:
                                f_ya = f_lp
                            if f_ya <= 0.0:
                                f_ya = 0.88 if sport_tag == "SOC" else 0.92
                            is_deriv_total = any(k in series for k in ("1H", "2H", "1P", "2P", "3P", "TEAMTOTAL"))
                            if not is_deriv_total:
                                poisson_base = 93.6 if sport_tag == "SOC" else 94.3
                                mkt_prob = min(97.5, max(82.0, f_ya * 100.0 + 2.4))
                                conf = round(poisson_base * 0.35 + mkt_prob * 0.65, 1)
                                conf = max(90.0, min(97.5, conf))
                            else:
                                seg_base = 76.5 if "1H" in series else (82.0 if "2H" in series else (74.0 if "TEAMTOTAL" in series else 65.0))
                                mkt_prob = min(95.0, max(54.0, f_ya * 100.0 + 2.6))
                                conf = round(seg_base * 0.30 + mkt_prob * 0.70, 1)
                                conf = max(55.0, min(95.5, conf))
                            edge = round(conf - (f_ya * 100.0), 1)
                            raw_sub = (best_mkt.get("yes_sub_title") or best_mkt.get("title") or f"Over {target_floor_strike:g} goals scored").replace("Full Game: ", "").replace("Reg Time: ", "").strip()
                            if "1H" in series and "1st half" not in raw_sub.lower():
                                pred_pick_name = f"1st Half: {raw_sub}"
                            elif "2H" in series and "2nd half" not in raw_sub.lower():
                                pred_pick_name = f"2nd Half: {raw_sub}"
                            elif "1P" in series and "1st period" not in raw_sub.lower():
                                pred_pick_name = f"1st Period: {raw_sub}"
                            elif "2P" in series and "2nd period" not in raw_sub.lower():
                                pred_pick_name = f"2nd Period: {raw_sub}"
                            elif "3P" in series and "3rd period" not in raw_sub.lower():
                                pred_pick_name = f"3rd Period: {raw_sub}"
                            else:
                                pred_pick_name = raw_sub
                            if not best_pick:
                                best_pick = {
                                    "sport": sport_tag,
                                    "market_type": "TOTAL",
                                    "predicted_team": pred_pick_name,
                                    "confidence_pct": conf,
                                    "edge_pct": edge,
                                    "pick_side": "YES",
                                    "ai_source": "Sports AI",
                                    "metadata": {
                                        "matchup": clean_matchup,
                                        "line": target_floor_strike,
                                        "type": "TOTAL"
                                    }
                                }
                            has_valid_pick = True

                    if not floor_locked and conf > 0 and has_valid_pick and best_pick:
                        is_floor_mode = (active_strat_target in ("FLOOR_TOTALS", "POWER_COMBO", "ULTRA_COMBO", "MEGA_PARLAY"))
                        is_total_market = ("TOTAL" in str(ev_prop_type or "").upper() or "TOTAL" in event_ticker)

                        # If user is in floor strategy and event is a total, scan alternate floor lines instead of locking onto mainline
                        if is_floor_mode and is_total_market:
                            best_mkt, is_yes_side, calc_edge, calc_conf, is_alt_line = find_best_market_for_pick(markets, best_pick, milestone, strategy=active_strat_target, sport=sport_tag)
                            if calc_conf and calc_conf > 0:
                                conf = calc_conf
                            if calc_edge is not None:
                                edge = calc_edge
                            if is_alt_line and best_mkt:
                                alt_title = best_mkt.get("yes_sub_title") or best_mkt.get("title") or ""
                                if alt_title and any(k in alt_title.upper() for k in ("OVER", "UNDER", "+")):
                                    pred_pick_name = alt_title.replace("Full Game: ", "").strip()
                        elif USE_KALSHI_BRIDGE and best_pick.get("kalshi_market_ticker"):
                            best_mkt = next((m for m in markets if m["ticker"] == best_pick.get("kalshi_market_ticker")), None)
                            if best_mkt:
                                is_yes_side = (best_pick.get("side", "yes") == "yes")
                                if best_pick.get("model_prob") is not None:
                                    conf = float(best_pick.get("model_prob")) * 100.0
                                is_alt_line = False
                                m_yes = parse_price(best_mkt, 'yes_ask')
                                edge = (conf - m_yes * 100.0) if m_yes > 0 else edge
                                if best_pick.get("team_or_player"):
                                    pred_pick_name = best_pick.get("team_or_player")

                        if not best_mkt:
                            best_mkt, is_yes_side, calc_edge, calc_conf, is_alt_line = find_best_market_for_pick(markets, best_pick, milestone, strategy=active_strat_target, sport=sport_tag)
                            if calc_conf and calc_conf > 0:
                                conf = calc_conf
                            if calc_edge is not None:
                                edge = calc_edge
                            if is_alt_line and best_mkt:
                                # Update pick name to describe the selected alternate floor line
                                alt_title = best_mkt.get("yes_sub_title") or best_mkt.get("title") or ""
                                if alt_title and any(k in alt_title.upper() for k in ("OVER", "UNDER", "+")):
                                    pred_pick_name = alt_title.replace("Full Game: ", "").strip()
                        if best_mkt:
                            markets = [best_mkt] + [m for m in markets if m != best_mkt]
                            
                    if not best_mkt and markets:
                        best_mkt = markets[0]

                    # Strict pick validity check: Never report phantom predictions or 0/50 confidence
                    is_soc = (sport_tag in ("SOC", "SOCCER") or series_key in ("SOC", "SOCCER"))
                    is_ufc = (sport_tag in ("UFC", "MMA") or series_key in ("UFC", "MMA") or "UFC" in str(event_ticker).upper())
                    has_prediction_ready = bool(
                        has_valid_pick and 
                        pred_pick_name and 
                        ((conf >= 50.0 and conf > 0.0) if is_ufc else ((conf > 50.0 and conf != 50.0) if not is_soc else (conf > 0.0 and conf != 50.0))) and
                        best_pick is not None
                    )

                    # Strict participant validation: The pick MUST match the Acceptance Test criteria for the event
                    is_team_valid = True
                    if has_prediction_ready and pred_pick_name and not floor_locked:
                        t_lower = str(pred_pick_name).lower().strip()
                        clean_m = (clean_matchup or title).lower().replace(" @ ", " vs ")
                        parts = [p.strip() for p in clean_m.split(" vs ") if p.strip()]
                        if len(parts) >= 2:
                            is_total_market = (
                                ev_prop_type in ("Total (O/U)", "TOTAL") or
                                (best_pick and best_pick.get("market_type") in ("TOTAL", "OVER/UNDER")) or
                                t_lower.startswith(("over ", "under ")) or
                                ": over " in t_lower or ": under " in t_lower
                            )
                            if is_total_market:
                                # For totals, pick is e.g. 'Under 45.5'. Match against event participants or matchup.
                                p_match = (best_pick.get("matchup") or best_pick.get("opponent") or "").lower() if best_pick else ""
                                p1_toks = {w for w in re.findall(r'[a-z0-9]+', parts[0]) if len(w) >= 3}
                                p2_toks = {w for w in re.findall(r'[a-z0-9]+', parts[1]) if len(w) >= 3}
                                if p_match:
                                    pm_toks = {w for w in re.findall(r'[a-z0-9]+', p_match) if len(w) >= 3}
                                    if not ((p1_toks & pm_toks) or (p2_toks & pm_toks) or parts[0] in p_match or parts[1] in p_match):
                                        is_team_valid = False
                                        logger.info(f"[EventsFeed] Discarding total pick {pred_pick_name} because matchup '{p_match}' does not match event {event_ticker} ({clean_matchup})")
                                else:
                                    is_team_valid = True
                            elif " @ " in t_lower or " vs " in t_lower or " vs. " in t_lower:
                                # Never allow a full matchup string ("Team A @ Team B") as a predicted_team
                                is_team_valid = False
                                logger.info(f"[EventsFeed] Discarding unsplit matchup string '{pred_pick_name}' on {event_ticker}")
                            else:
                                # For spreads (e.g. 'CAR +1.5'), extract the team name/code
                                cand_team = re.sub(r'[\+\-]?\d+(\.\d+)?', '', t_lower).strip()
                                cand_team = cand_team if cand_team else t_lower
                                if len(cand_team) <= 3:
                                    m1 = bool(re.search(rf"\b{re.escape(cand_team)}\b", parts[0]))
                                    m2 = bool(re.search(rf"\b{re.escape(cand_team)}\b", parts[1]))
                                else:
                                    m1 = cand_team in parts[0] or parts[0] in cand_team
                                    m2 = cand_team in parts[1] or parts[1] in cand_team
                                tokens = {w for w in cand_team.split() if len(w) >= 3 and w not in ('the', 'team', 'club', 'fc')}
                                p1_tokens = {w for w in parts[0].split() if len(w) >= 3}
                                p2_tokens = {w for w in parts[1].split() if len(w) >= 3}
                                if tokens and p1_tokens and (tokens <= p1_tokens or p1_tokens <= tokens or bool(tokens & p1_tokens)):
                                    m1 = True
                                if tokens and p2_tokens and (tokens <= p2_tokens or p2_tokens <= tokens or bool(tokens & p2_tokens)):
                                    m2 = True

                                if not (m1 or m2) and t_lower in ("draw", "tie") and is_soc:
                                    m1 = any("tie" in (m_i.get("yes_sub_title") or m_i.get("title") or "").lower() or str(m_i.get("ticker") or "").endswith("-TIE") for m_i in markets)
                                if not (m1 or m2):
                                    is_team_valid = False
                                    logger.debug(f"[EventsFeed] Discarding pick {pred_pick_name} because it is not a participant of {event_ticker} ({clean_matchup})")
                        else:
                            is_team_valid = False

                    if not is_team_valid:
                        has_prediction_ready = False
                        has_valid_pick = False
                        best_pick = None

                    if not has_prediction_ready or round(conf, 1) in (0.0, 50.0) or not pred_pick_name:
                        # Fallback synthesis: select the mainline favored market (0.48 <= yes_ask <= 0.88) instead of tail alt lines
                        def _mkt_prob(m_item):
                            ya_i = parse_price(m_item, 'yes_ask')
                            nb_i = parse_price(m_item, 'no_bid')
                            lp_i = parse_price(m_item, 'last_price')
                            return ya_i if ya_i > 0 else (round(1.0 - nb_i, 4) if nb_i > 0 else (lp_i if lp_i > 0 else 0.50))

                        fav_mkts = [m_i for m_i in markets if 0.48 <= _mkt_prob(m_i) <= 0.88]
                        if fav_mkts:
                            m_cand = min(fav_mkts, key=lambda m_i: abs(_mkt_prob(m_i) - 0.58))
                        else:
                            tradable_mkts = [m_i for m_i in markets if 0.04 <= _mkt_prob(m_i) <= 0.96]
                            m_cand = min(tradable_mkts, key=lambda m_i: abs(_mkt_prob(m_i) - 0.55)) if tradable_mkts else (best_mkt or (markets[0] if markets else None))

                        if m_cand:
                            best_mkt = m_cand
                            markets = [m_cand] + [m_i for m_i in markets if m_i != m_cand]
                            c_prob = _mkt_prob(m_cand)
                            is_yes_side = (c_prob >= 0.50)
                            c_pick = (m_cand.get("yes_sub_title") or m_cand.get("title") or clean_matchup).replace("Full Game: ", "").replace("Reg Time: ", "").strip()
                            if " wins" in c_pick.lower() and " wins by " not in c_pick.lower():
                                c_pick = re.sub(r'\s+wins\??$', '', c_pick, flags=re.IGNORECASE).strip()
                            if not is_yes_side:
                                no_sub = (m_cand.get("no_sub_title") or "").strip()
                                if no_sub and no_sub.lower() not in ("no", "yes") and no_sub != c_pick:
                                    c_pick = no_sub
                                elif re.match(r'^over\s+', c_pick, flags=re.IGNORECASE):
                                    c_pick = re.sub(r'^over\s+', 'Under ', c_pick, count=1, flags=re.IGNORECASE)
                                elif " wins by over " in c_pick.lower():
                                    # e.g. "Washington wins by over 3.5 points" -> NO means opponent +3.5 or "NO: Washington wins by over 3.5 points"
                                    c_pick = f"NO ({c_pick})"
                            
                            pred_pick_name = c_pick
                            conf = round(max(52.0, min(88.0, c_prob * 100.0 if c_prob >= 0.50 else (1.0 - c_prob) * 100.0)), 1)
                            edge = 0.0
                            has_prediction_ready = True
                            has_valid_pick = True
                            best_pick = {
                                "sport": sport_tag,
                                "market_type": ev_prop_type or "Moneyline",
                                "predicted_team": pred_pick_name,
                                "confidence_pct": conf,
                                "edge_pct": 0.0,
                                "pick_side": "YES" if is_yes_side else "NO",
                                "ai_source": "Market Consensus",
                                "metadata": {
                                    "matchup": clean_matchup,
                                    "source": "Market Consensus"
                                }
                            }
                        else:
                            has_prediction_ready = False
                            has_valid_pick = False
                            best_pick = None
                            pred_pick_name = None
                            conf = 0.0
                            edge = 0.0

                    m_yes = parse_price(best_mkt, 'yes_ask')
                    m_no = parse_price(best_mkt, 'no_ask')
                    m_last = parse_price(best_mkt, 'last_price')
                    m_yes_bid = parse_price(best_mkt, 'yes_bid')
                    m_no_bid = parse_price(best_mkt, 'no_bid')
                    if m_yes <= 0.0 and m_no_bid > 0.0:
                        m_yes = round(1.0 - m_no_bid, 4)
                    if m_no <= 0.0 and m_yes_bid > 0.0:
                        m_no = round(1.0 - m_yes_bid, 4)
                    if m_yes > 0.0 and m_no <= 0.0:
                        m_no = round(1.0 - m_yes, 4)
                    elif m_no > 0.0 and m_yes <= 0.0:
                        m_yes = round(1.0 - m_no, 4)
                    if m_yes <= 0.0 and m_last > 0.0:
                        m_yes = m_last
                    if m_no <= 0.0 and m_yes > 0.0:
                        m_no = round(1.0 - m_yes, 4)
                    elif m_yes <= 0.0 and m_no > 0.0:
                        m_yes = round(1.0 - m_no, 4)
                    if m_yes <= 0.0 and m_no <= 0.0:
                        m_yes = 0.50
                        m_no = 0.50
                    if m_yes > 0.0 and m_no > 0.0:
                        book_sum = m_yes + m_no
                        if book_sum > 1.05 or book_sum < 0.98:
                            m_no = round(max(0.01, min(0.99, 1.0 - m_yes)), 4)

                    ai_source_label = "Sports AI"
                    if best_pick and best_pick.get("ai_source") == "Market Consensus":
                        ai_source_label = "Market Consensus"
                    elif best_pick and (best_pick.get("ai_source") == "Simulation" or best_pick.get("metadata", {}).get("simulation")):
                        ai_source_label = "Simulation"
                    elif sport_tag == "TEN" and edge == 0.0:
                        ai_source_label = "Sportsbook consensus"

                    capper_eval = None
                    if best_pick:
                        best_pick = dict(best_pick)
                        best_pick["predicted_team"] = pred_pick_name
                        best_pick["confidence_pct"] = round(conf, 1)
                        best_pick["edge_pct"] = round(edge, 1)
                        best_pick["pick_side"] = "YES" if is_yes_side else "NO"
                        best_pick["ai_source"] = ai_source_label

                        # Evaluate Master Sports Capper conviction grading & Net EV
                        capper_eval = best_pick.get("metadata", {}).get("capper") or best_pick.get("capper")
                        if not capper_eval:
                            try:
                                from backend.sports_engine.master_capper import MasterSportsCapper
                                price_val = m_yes if is_yes_side else m_no
                                sit_factors = best_pick.get("metadata", {}).get("factor_impacts", {}) or {}
                                capper_eval = MasterSportsCapper.evaluate_capper_edge(
                                    sport=sport_tag,
                                    matchup=clean_matchup,
                                    pick_name=pred_pick_name,
                                    market_type=ev_prop_type or "Moneyline",
                                    model_win_prob=float(conf),
                                    kalshi_price_dollars=float(price_val),
                                    situational_factors=sit_factors
                                )
                            except Exception as _ce:
                                logger.debug(f"[MasterCapper] Fast eval error for {clean_matchup}: {_ce}")
                                capper_eval = None

                        if capper_eval:
                            best_pick["capper"] = capper_eval
                            best_pick["capper_grade"] = capper_eval.get("grade")
                            best_pick["capper_stars"] = capper_eval.get("stars")
                            best_pick["capper_tier"] = capper_eval.get("tier_label")
                            best_pick["net_ev_pct"] = capper_eval.get("net_ev_pct")
                            best_pick["kelly_bankroll_pct"] = capper_eval.get("kelly_bankroll_pct")
                            if "metadata" not in best_pick or not isinstance(best_pick["metadata"], dict):
                                best_pick["metadata"] = {}
                            best_pick["metadata"]["capper"] = capper_eval
                            best_pick["metadata"]["capper_grade"] = capper_eval.get("grade")
                            best_pick["metadata"]["capper_stars"] = capper_eval.get("stars")
                            best_pick["metadata"]["capper_tier"] = capper_eval.get("tier_label")
                            best_pick["metadata"]["net_ev_pct"] = capper_eval.get("net_ev_pct")
                            best_pick["metadata"]["kelly_bankroll_pct"] = capper_eval.get("kelly_bankroll_pct")
                            if capper_eval.get("capper_thesis") and not best_pick.get("metadata", {}).get("narrative"):
                                best_pick["metadata"]["narrative"] = capper_eval.get("capper_thesis")

                    has_real_ai = bool(has_prediction_ready and best_mkt is not None and round(conf, 1) not in (0.0, 50.0))

                    best_mkt_details = parse_sports_market_details(
                        ticker=best_mkt.get("ticker") if best_mkt else event_ticker,
                        title=title,
                        series=series,
                        markets=[best_mkt] if best_mkt else markets
                    )
                    card_ticker = best_mkt.get("ticker") if ("TEAMTOTAL" in series and best_mkt) else event_ticker
                    formatted_game_time = None
                    if start_epoch:
                        try:
                            formatted_game_time = datetime.fromtimestamp(start_epoch, ZoneInfo("America/New_York")).strftime("%b %d · %I:%M %p ET")
                        except Exception:
                            pass

                    kalshi_events.append({
                        "ai_source": ai_source_label,
                        "ticker": card_ticker,
                        "title": clean_matchup if clean_matchup and ("vs" in clean_matchup or "@" in clean_matchup) else title,
                        "sport": sport_tag,
                        "league": league_tag,
                        "matchup": clean_matchup,
                        "predicted_team": pred_pick_name if has_real_ai else None,
                        "has_ai_prediction": has_real_ai,
                        "ai_pick": pred_pick_name if has_real_ai else None,
                        "ai_prediction": best_pick if has_real_ai else None,
                        "tactical_intel": (best_pick.get("metadata", {}).get("tactical_intel") or best_pick.get("tactical_intel") or best_pick.get("metadata", {}).get("lwos_prediction")) if has_real_ai and best_pick else None,
                        "editorial_consensus": (best_pick.get("metadata", {}).get("editorial_consensus") or best_pick.get("editorial_consensus") or best_pick.get("metadata", {}).get("narrative_alignment")) if has_real_ai and best_pick else None,
                        "editorial_source": (best_pick.get("metadata", {}).get("editorial_source") or best_pick.get("editorial_source") or ("Last Word On Sports" if best_pick.get("metadata", {}).get("lwos_prediction") else None)) if has_real_ai and best_pick else None,
                        "confirmed_starter": (best_pick.get("metadata", {}).get("confirmed_goalie") or best_pick.get("metadata", {}).get("starter")) if has_real_ai and best_pick else None,
                        "capper": capper_eval if has_real_ai else None,
                        "capper_grade": capper_eval.get("grade") if (has_real_ai and capper_eval) else None,
                        "capper_stars": capper_eval.get("stars") if (has_real_ai and capper_eval) else None,
                        "capper_tier": capper_eval.get("tier_label") if (has_real_ai and capper_eval) else None,
                        "net_ev_pct": capper_eval.get("net_ev_pct") if (has_real_ai and capper_eval) else None,
                        "kelly_bankroll_pct": capper_eval.get("kelly_bankroll_pct") if (has_real_ai and capper_eval) else None,
                        "pick_side": "YES" if is_yes_side else "NO",
                        "is_alt_line": is_alt_line,
                        "strategy_tag": (
                            "FLOOR_TOTALS" if (
                                floor_locked or (
                                    ("TOTAL" in str(ev_prop_type or "").upper() or "TOTAL" in event_ticker) and
                                    (is_alt_line or classify_event_strategy(e) == "FLOOR_TOTALS" or (best_mkt and (best_mkt.get("floor_strike") or 99) <= (4.5 if sport_tag == "NHL" else (1.5 if sport_tag == "SOC" else (6.5 if sport_tag == "MLB" else 34.5)))))
                                )
                            )
                            else ("MILESTONE_PROPS" if (classify_event_strategy(e) == "MILESTONE_PROPS" or "HRR" in event_ticker or "1+" in str(best_mkt.get("title", "") if best_mkt else "")) else classify_event_strategy(e))
                        ),
                        "market_type": best_mkt_details.get("prop_type") or ev_prop_type or "Game/Match",
                        "segment": best_mkt_details.get("segment") or "Main",
                        "prop_type": best_mkt_details.get("prop_type") or (best_mkt.get("prop_type") if best_mkt else None) or ev_prop_type,
                        "line": best_mkt_details.get("line"),
                        "spread_amount": best_mkt_details.get("spread_amount"),
                        "over_under_amount": best_mkt_details.get("over_under_amount"),
                        "game_time": formatted_game_time,
                        "sub_title": (best_mkt.get("yes_sub_title") or best_mkt.get("sub_title") or sub) if best_mkt else sub,
                        "strike_details": (best_mkt.get("yes_sub_title") or best_mkt.get("title") or "") if best_mkt else "",
                        "confidence_pct": round(conf, 1) if has_real_ai else 0.0,
                        "edge_pct": round(edge, 1) if has_real_ai else 0.0,
                        "event_ticker": event_ticker,
                        "series_ticker": series,
                        "start_epoch": start_epoch,
                        "is_today": is_today,
                        "is_live": is_live,
                        "event_date": str(ev_date) if ev_date else None,
                        "yes_ask": m_yes,
                        "no_ask": m_no,
                        "last_price": m_last,
                        "markets": markets,
                        "metadata": {
                            "is_live": is_live,
                            "name": pred_pick_name,
                            "matchup": clean_matchup,
                            "game_time": formatted_game_time,
                            "market_type_label": best_mkt_details.get("prop_type") or (best_mkt.get("market_type_label", "Game/Match") if best_mkt else "Game/Match"),
                            "prop_type": best_mkt_details.get("prop_type") or (best_mkt.get("prop_type") if best_mkt else None),
                            "line": best_mkt_details.get("line"),
                            "spread_amount": best_mkt_details.get("spread_amount"),
                            "over_under_amount": best_mkt_details.get("over_under_amount"),
                            "tactical_intel": (best_pick.get("metadata", {}).get("tactical_intel") or best_pick.get("tactical_intel") or best_pick.get("metadata", {}).get("lwos_prediction")) if has_real_ai and best_pick else None,
                            "editorial_consensus": (best_pick.get("metadata", {}).get("editorial_consensus") or best_pick.get("editorial_consensus") or best_pick.get("metadata", {}).get("narrative_alignment")) if has_real_ai and best_pick else None,
                            "editorial_source": (best_pick.get("metadata", {}).get("editorial_source") or best_pick.get("editorial_source") or ("Last Word On Sports" if best_pick.get("metadata", {}).get("lwos_prediction") else None)) if has_real_ai and best_pick else None,
                            "capper": capper_eval if has_real_ai else None,
                            "capper_grade": capper_eval.get("grade") if (has_real_ai and capper_eval) else None,
                            "capper_stars": capper_eval.get("stars") if (has_real_ai and capper_eval) else None,
                            "capper_tier": capper_eval.get("tier_label") if (has_real_ai and capper_eval) else None,
                            "net_ev_pct": capper_eval.get("net_ev_pct") if (has_real_ai and capper_eval) else None,
                            "kelly_bankroll_pct": capper_eval.get("kelly_bankroll_pct") if (has_real_ai and capper_eval) else None,
                        }
                    })

        kalshi_events = [e for e in kalshi_events if e.get("is_today") or not (e.get("event_date") and datetime.strptime(e.get("event_date"), "%Y-%m-%d").date() < today_et and not e.get("is_live"))]

        with _SPORTS_AGG_CACHE_LOCK:
            _SPORTS_AGG_CACHE[cache_key] = (now, kalshi_events)
            if query_filter in ("", "ALL"):
                _SPORTS_AGG_CACHE[f"ALL:{active_strat_target}"] = (now, kalshi_events)
                _SPORTS_AGG_CACHE[f":{active_strat_target}"] = (now, kalshi_events)

        filtered_events = [e for e in kalshi_events if is_event_allowed_for_user(e, user, query_filter, strategy=active_strat_target)] if user else list(kalshi_events)
        if not filtered_events and kalshi_events and query_filter in ("", "ALL"):
            filtered_events = [e for e in kalshi_events if e.get("has_ai_prediction") and e.get("ai_pick")]
        filtered_events.sort(key=lambda x: float(x.get("start_epoch") or 9999999999.0))
        return filtered_events
    except Exception as e:
        logger.error(f"Error in fetch_sports_events_data: {e}")
        import traceback
        traceback.print_exc()
        return []

_API_EVENTS_JSON_CACHE = {}
_API_EVENTS_JSON_LOCK = threading.Lock()
_API_EVENTS_JSON_REFRESHING = set()
_PREWARM_LOOP_STARTED = False


def _build_and_cache_events_json(query_filter: str, clean_strategy: Optional[str], user: Optional[dict], resp_key: tuple) -> tuple:
    import gzip
    import hashlib
    filtered_events = fetch_sports_events_data(query_filter=query_filter, user=user, strategy=clean_strategy)
    payload_bytes = json.dumps({"status": "ok", "count": len(filtered_events), "events": filtered_events}).encode("utf-8")
    gzip_bytes = gzip.compress(payload_bytes, compresslevel=5)
    etag_str = f'W/"{hashlib.md5(payload_bytes).hexdigest()}"'
    now_ts = time.time()
    if filtered_events:
        entry = (now_ts, gzip_bytes, etag_str)
        with _API_EVENTS_JSON_LOCK:
            if len(_API_EVENTS_JSON_CACHE) >= 16 and resp_key not in _API_EVENTS_JSON_CACHE:
                oldest_k = min(_API_EVENTS_JSON_CACHE, key=lambda k: _API_EVENTS_JSON_CACHE[k][0])
                _API_EVENTS_JSON_CACHE.pop(oldest_k, None)
            _API_EVENTS_JSON_CACHE[resp_key] = entry
            if query_filter in ("", "ALL"):
                alt_qf = "ALL" if query_filter == "" else ""
                _API_EVENTS_JSON_CACHE[(alt_qf, clean_strategy, resp_key[2])] = entry
    return payload_bytes, gzip_bytes, etag_str


def _make_user_sig(user_id: Optional[int], user: Optional[dict]) -> tuple:
    return (
        user_id,
        user.get("sports_strategy") if user else None,
        user.get("sports_sport_config") if user else None,
        user.get("sports_active_leagues") if user else None,
        user.get("sports_market_types") if user else None,
        user.get("sports_active_props") if user else None,
    )


def prewarm_sports_events_cache():
    """Proactively warms and continuously refreshes the sports aggregate & JSON caches with compact GZip storage (~1.2 MB total RAM)."""
    global _PREWARM_LOOP_STARTED
    def _warm_all_profiles():
        all_evts = fetch_sports_events_data(query_filter="", user=None, strategy="STANDARD", _force_sync=True)
        if not all_evts:
            return
        profiles = [(None, None)]
        for uid in (7, 1):
            try:
                u = get_user_by_id(uid)
                if u:
                    profiles.append((uid, u))
            except Exception:
                pass
        for uid, u in profiles:
            usig = _make_user_sig(uid, u)
            rk = ("", None, usig)
            _build_and_cache_events_json("", None, u, rk)

    try:
        _warm_all_profiles()
    except Exception as e:
        logger.debug(f"[SportsPrewarm] Initial warm error: {e}")

    if not _PREWARM_LOOP_STARTED:
        _PREWARM_LOOP_STARTED = True
        def _continuous_swr_loop():
            while True:
                time.sleep(16.0)
                try:
                    _warm_all_profiles()
                except Exception:
                    pass
        threading.Thread(target=_continuous_swr_loop, daemon=True, name="SportsEventsSWRDaemon").start()


@sports_router.get("/api/engine/sports/events", dependencies=[Depends(require_auth)])
def api_sports_events(
    sport: Optional[str] = None,
    league: Optional[str] = None,
    filter: Optional[str] = None,
    strategy: Optional[str] = None,
    request: Request = None
):
    try:
        import gzip
        from fastapi.responses import Response
        raw_filter = sport or league or filter or ""
        if hasattr(raw_filter, "default"):
            raw_filter = ""
        query_filter = str(raw_filter or "").strip().upper()
        raw_strategy = strategy or ""
        if hasattr(raw_strategy, "default"):
            raw_strategy = ""
        clean_strategy = str(raw_strategy or "").strip().upper() or None
        user_id = _resolve_user_id(None, request)
        user = get_user_by_id(user_id) if user_id else None

        user_sig = _make_user_sig(user_id, user)
        resp_key = (query_filter, clean_strategy, user_sig)
        now_ts = time.time()
        inm = request.headers.get("if-none-match") if (request and hasattr(request, "headers")) else None
        accept_enc = (request.headers.get("accept-encoding") or "").lower() if (request and hasattr(request, "headers")) else ""
        wants_gzip = "gzip" in accept_enc

        with _API_EVENTS_JSON_LOCK:
            cached_resp = _API_EVENTS_JSON_CACHE.get(resp_key)

        if cached_resp:
            c_ts, gzip_bytes, etag_str = cached_resp
            if now_ts - c_ts >= 18.0 and resp_key not in _API_EVENTS_JSON_REFRESHING:
                with _API_EVENTS_JSON_LOCK:
                    _API_EVENTS_JSON_REFRESHING.add(resp_key)
                def _bg_refresh_json(qf=query_filter, cs=clean_strategy, u=user, rk=resp_key):
                    try:
                        _build_and_cache_events_json(qf, cs, u, rk)
                    finally:
                        with _API_EVENTS_JSON_LOCK:
                            _API_EVENTS_JSON_REFRESHING.discard(rk)
                threading.Thread(target=_bg_refresh_json, daemon=True, name="SportsJsonSWR").start()

            headers = {
                "ETag": etag_str,
                "Cache-Control": "private, max-age=5, stale-while-revalidate=25",
                "Vary": "Accept-Encoding",
            }
            if inm and inm.strip() == etag_str:
                return Response(status_code=304, headers=headers)
            if wants_gzip:
                headers["Content-Encoding"] = "gzip"
                return Response(content=gzip_bytes, media_type="application/json", headers=headers)
            return Response(content=gzip.decompress(gzip_bytes), media_type="application/json", headers=headers)

        payload_bytes, gzip_bytes, etag_str = _build_and_cache_events_json(query_filter, clean_strategy, user, resp_key)
        headers = {
            "ETag": etag_str,
            "Cache-Control": "private, max-age=5, stale-while-revalidate=25",
            "Vary": "Accept-Encoding",
        }
        if inm and inm.strip() == etag_str:
            return Response(status_code=304, headers=headers)
        if wants_gzip:
            headers["Content-Encoding"] = "gzip"
            return Response(content=gzip_bytes, media_type="application/json", headers=headers)
        return Response(content=payload_bytes, media_type="application/json", headers=headers)
    except Exception as e:
        logger.error(f"Error in api_sports_events: {e}")
        return {"status": "error", "message": str(e), "events": []}

@sports_router.get("/api/engine/sports/predict", dependencies=[Depends(require_auth)])
@sports_router.post("/api/engine/sports/predict", dependencies=[Depends(require_auth)])
def api_sports_predict(
    event_ticker: str = Query(...),
    execute: bool = Query(True),
    min_confidence: Optional[float] = Query(None),
    min_edge: Optional[float] = Query(None),
    user_id: Optional[int] = Query(None),
    title: Optional[str] = Query(None),
    sport: Optional[str] = Query(None),
    trade_size: Optional[float] = Query(None),
    side: Optional[str] = Query(None),
    request: Request = None
):
    if not event_ticker or not str(event_ticker).strip():
        return {
            "status": "error",
            "error": "Invalid or missing event_ticker",
            "prediction": None,
            "criteria_met": False,
            "executed": False,
            "trade_id": None,
            "trade": None
        }

    event_ticker = str(event_ticker).strip()
    event_title = (title or "").strip()
    event_sport = (sport or "").strip()

    # 0. Check _SPORTS_AGG_CACHE to ensure 100% parity with the events feed
    cached_feed_event = None
    with _SPORTS_AGG_CACHE_LOCK:
        for qf, (ts, evts) in _SPORTS_AGG_CACHE.items():
            for ev in evts:
                if ev.get("event_ticker") == event_ticker or ev.get("ticker") == event_ticker:
                    cached_feed_event = ev
                    break
            if cached_feed_event:
                break

    if cached_feed_event:
        if not event_title and cached_feed_event.get("title"):
            event_title = cached_feed_event.get("title")
        if not event_sport and cached_feed_event.get("sport"):
            event_sport = cached_feed_event.get("sport")

        if cached_feed_event.get("has_ai_prediction") and cached_feed_event.get("predicted_team"):
            pred = dict(cached_feed_event.get("ai_prediction") or {})
            pred["predicted_team"] = cached_feed_event.get("predicted_team")
            pred["confidence_pct"] = cached_feed_event.get("confidence_pct")
            pred["edge_pct"] = cached_feed_event.get("edge_pct")
            pred["pick_side"] = cached_feed_event.get("pick_side")
            pred["ai_source"] = cached_feed_event.get("ai_source")
            if not execute:
                md_existing = dict(pred.get("metadata") or {})
                if "explain" not in md_existing:
                    try:
                        client = SportsPredictionClient(use_kalshi_bridge=USE_KALSHI_BRIDGE)
                        enriched = client.predict_for_event(event_ticker, title=event_title, sport=event_sport)
                        if isinstance(enriched, dict):
                            enr_md = enriched.get("metadata") or {}
                            if enr_md.get("explain"):
                                md_existing["explain"] = enr_md["explain"]
                            if enr_md.get("tactical_intel") and "tactical_intel" not in md_existing:
                                md_existing["tactical_intel"] = enr_md["tactical_intel"]
                            pred["metadata"] = md_existing
                    except Exception:
                        pass
            prediction = pred
        else:
            prediction = None
    else:
        # 1. Check local _SPORTS_EVENTS_CACHE first to avoid Kalshi 429 rate limits
        if not event_title or (" vs " not in event_title.lower() and " @ " not in event_title.lower()):
            with _SPORTS_EVENTS_CACHE_LOCK:
                for series_key, (ts, evts) in _SPORTS_EVENTS_CACHE.items():
                    for e in evts:
                        if e.get("event_ticker") == event_ticker:
                            cached_t = e.get("title") or ""
                            if cached_t:
                                event_title = cached_t
                            if not event_sport:
                                s = e.get("series_ticker") or ""
                                if "NPB" in s or "KBO" in s:
                                    event_sport = "NPB/KBO"
                                elif "NFL" in s:
                                    event_sport = "NFL"
                                elif "MLB" in s:
                                    event_sport = "MLB"
                                elif "NHL" in s:
                                    event_sport = "NHL"
                                elif "SOC" in s or "EPL" in s:
                                    event_sport = "SOC"
                                elif "UFC" in s:
                                    event_sport = "UFC"
                                elif "ATP" in s or "WTA" in s:
                                    event_sport = "TEN"
                            break
                    if event_title and (" vs " in event_title.lower() or " @ " in event_title.lower()):
                        break

        # 2. If still missing full matchup, query Kalshi event API
        if not event_title or (" vs " not in event_title.lower() and " @ " not in event_title.lower()):
            import requests
            try:
                headers = {"Accept": "application/json", "User-Agent": "ApexProps-Trader/1.0"}
                from backend.btc.kalshi_trader import kalshi_trader
                if kalshi_trader.is_authenticated():
                    try:
                        headers = kalshi_trader._sign_headers("GET", f"/trade-api/v2/events/{event_ticker}")
                    except Exception:
                        pass
                r = requests.get(f"https://external-api.kalshi.com/trade-api/v2/events/{event_ticker}", headers=headers, timeout=5.0)
                if r.status_code == 200:
                    evt = r.json().get("event", {})
                    real_title = evt.get("title") or ""
                    if real_title:
                        event_title = real_title
                    series = evt.get("series_ticker") or ""
                    if not event_sport:
                        if "NPB" in series or "KBO" in series:
                            event_sport = "NPB/KBO"
                        elif "NFL" in series:
                            event_sport = "NFL"
                        elif "MLB" in series:
                            event_sport = "MLB"
                        elif "NHL" in series:
                            event_sport = "NHL"
                        elif "SOC" in series or "EPL" in series:
                            event_sport = "SOC"
                        elif "UFC" in series:
                            event_sport = "UFC"
                        elif "ATP" in series or "WTA" in series:
                            event_sport = "TEN"
            except Exception:
                pass

        client = SportsPredictionClient(use_kalshi_bridge=USE_KALSHI_BRIDGE)
        prediction = client.predict_for_event(event_ticker, title=event_title, sport=event_sport)
        if prediction and isinstance(prediction, dict):
            p_team = prediction.get("predicted_team")
            if p_team and event_title and (" vs " in event_title.lower() or " @ " in event_title.lower()):
                clean_t = event_title.lower().replace(" @ ", " vs ")
                parts = [p.strip() for p in clean_t.split(" vs ") if p.strip()]
                if len(parts) >= 2:
                    p1_tokens = {w for w in re.findall(r'[a-z0-9]+', parts[0]) if len(w) >= 3 and w not in ('the', 'team', 'club', 'fc')}
                    p2_tokens = {w for w in re.findall(r'[a-z0-9]+', parts[1]) if len(w) >= 3 and w not in ('the', 'team', 'club', 'fc')}
                    team_tokens = {w for w in re.findall(r'[a-z0-9]+', p_team.lower()) if len(w) >= 3 and w not in ('the', 'team', 'club', 'fc')}
                    m1 = p_team.lower() in parts[0] or (team_tokens and p1_tokens and team_tokens <= p1_tokens)
                    m2 = p_team.lower() in parts[1] or (team_tokens and p2_tokens and team_tokens <= p2_tokens)
                    if not (m1 or m2):
                        prediction = None
            if prediction:
                p_conf = float(prediction.get("confidence_pct") or 0.0)
                if p_conf <= 0 or round(p_conf, 1) in (0.0, 50.0):
                    prediction = None

    market_details = parse_sports_market_details(
        ticker=event_ticker,
        title=event_title,
        series=event_sport or event_ticker,
        markets=cached_feed_event.get("markets", []) if cached_feed_event else []
    )

    if prediction and isinstance(prediction, dict):
        m_prop_type = market_details.get("prop_type", "")
        pred_mtype = str(prediction.get("market_type") or prediction.get("metadata", {}).get("type") or "").upper()
        
        is_mismatch = False
        if m_prop_type in ("Player Prop", "PLAYER PROP") and not any(k in pred_mtype for k in ("PROP", "PLAYER")):
            is_mismatch = True
        elif m_prop_type == "Spread" and not any(k in pred_mtype for k in ("SPREAD", "PUCK LINE", "RUN LINE")):
            is_mismatch = True
        elif m_prop_type == "Total (O/U)" and not any(k in pred_mtype for k in ("TOTAL", "OVER", "UNDER", "O/U")):
            is_mismatch = True
        elif m_prop_type == "Moneyline" and any(k in pred_mtype for k in ("TOTAL", "SPREAD", "PROP", "OVER", "UNDER", "PUCK LINE", "RUN LINE", "PLAYER")):
            is_mismatch = True
            
        if is_mismatch:
            prediction = None

    uid = _require_user_id(user_id, request) if execute else _resolve_user_id(user_id, request)
    criteria = _get_user_sports_criteria(uid)
    req_min_conf = min_confidence if min_confidence is not None else criteria["min_confidence"]
    req_min_edge = min_edge if min_edge is not None else criteria["min_edge"]

    conf = float(prediction.get("confidence_pct", 0.0) if prediction else 0.0)
    edge = float(prediction.get("edge_pct", 0.0) if prediction else 0.0)
    criteria_met = bool(prediction and conf >= req_min_conf and edge >= req_min_edge)

    trade = None
    executed = False
    error_msg = None
    if criteria_met and execute:
        trade, error_msg = _execute_sports_trade(event_ticker, prediction, uid, trade_size=trade_size, explicit_side=side.upper() if side else None)
        executed = bool(trade)

    if execute and not executed and not error_msg:
        error_msg = f"Trade execution failed: Event {event_ticker} has no active matching markets on Kalshi"

    if prediction and isinstance(prediction, dict):
        prediction["prop_type"] = market_details.get("prop_type")
        prediction["line"] = market_details.get("line")
        prediction["spread_amount"] = market_details.get("spread_amount")
        prediction["over_under_amount"] = market_details.get("over_under_amount")
        prediction["strike_details"] = market_details.get("strike_details")

        # Ensure Master Sports Capper grading is attached
        c_eval = prediction.get("metadata", {}).get("capper") or prediction.get("capper")
        if not c_eval:
            try:
                from backend.sports_engine.master_capper import MasterSportsCapper
                p_team = prediction.get("predicted_team") or ""
                p_conf = float(prediction.get("confidence_pct") or 50.0)
                p_edge = float(prediction.get("edge_pct") or 0.0)
                p_price = round(max(0.10, min(0.90, (p_conf - p_edge) / 100.0)), 2)
                sit_f = prediction.get("metadata", {}).get("factor_impacts", {}) or {}
                c_eval = MasterSportsCapper.evaluate_capper_edge(
                    sport=event_sport or prediction.get("sport") or "SPORTS",
                    matchup=event_title or prediction.get("opponent") or "",
                    pick_name=p_team,
                    market_type=market_details.get("prop_type", "Moneyline"),
                    model_win_prob=p_conf,
                    kalshi_price_dollars=p_price,
                    situational_factors=sit_f
                )
            except Exception as _ce:
                logger.debug(f"[api_sports_predict] capper attach error: {_ce}")
                c_eval = None

        if c_eval:
            prediction["capper"] = c_eval
            prediction["capper_grade"] = c_eval.get("grade")
            prediction["capper_stars"] = c_eval.get("stars")
            prediction["capper_tier"] = c_eval.get("tier_label")
            prediction["net_ev_pct"] = c_eval.get("net_ev_pct")
            prediction["kelly_bankroll_pct"] = c_eval.get("kelly_bankroll_pct")
            if "metadata" not in prediction or not isinstance(prediction["metadata"], dict):
                prediction["metadata"] = {}
            prediction["metadata"]["capper"] = c_eval
            prediction["metadata"]["capper_grade"] = c_eval.get("grade")
            prediction["metadata"]["capper_stars"] = c_eval.get("stars")
            prediction["metadata"]["capper_tier"] = c_eval.get("tier_label")
            prediction["metadata"]["net_ev_pct"] = c_eval.get("net_ev_pct")
            prediction["metadata"]["kelly_bankroll_pct"] = c_eval.get("kelly_bankroll_pct")
            if c_eval.get("capper_thesis") and not prediction["metadata"].get("narrative"):
                prediction["metadata"]["narrative"] = c_eval.get("capper_thesis")

        # Forward editorial and tactical intelligence to root of prediction
        if "metadata" in prediction and isinstance(prediction["metadata"], dict):
            if "tactical_intel" in prediction["metadata"] and "tactical_intel" not in prediction:
                prediction["tactical_intel"] = prediction["metadata"]["tactical_intel"]
            if "editorial_consensus" in prediction["metadata"] and "editorial_consensus" not in prediction:
                prediction["editorial_consensus"] = prediction["metadata"]["editorial_consensus"]
            if "editorial_source" in prediction["metadata"] and "editorial_source" not in prediction:
                prediction["editorial_source"] = prediction["metadata"]["editorial_source"]

    return {
        "status": "ok",
        "event_ticker": event_ticker,
        "prediction": prediction,
        "event_details": market_details,
        "criteria_met": criteria_met,
        "criteria_info": {"conf": conf, "req_conf": req_min_conf, "edge": edge, "req_edge": req_min_edge},
        "executed": executed,
        "trade_id": trade.get("id") if trade else None,
        "trade": trade,
        "error": error_msg
    }

@sports_router.post("/api/engine/sports/execute", dependencies=[Depends(require_auth)])
@sports_router.get("/api/engine/sports/execute", dependencies=[Depends(require_auth)])
def api_sports_execute(
    event_ticker: str = Query(...),
    min_confidence: Optional[float] = Query(None),
    min_edge: Optional[float] = Query(None),
    user_id: Optional[int] = Query(None),
    title: Optional[str] = Query(None),
    sport: Optional[str] = Query(None),
    manual_team: Optional[str] = Query(None),
    trade_size: Optional[float] = Query(None),
    side: Optional[str] = Query(None),
    request: Request = None
):
    explicit_side = side.upper() if side else None
    if manual_team:
        uid = _require_user_id(user_id, request)
        clean_team = manual_team.strip()
        if "MANUAL" in clean_team.upper() and "YES" in clean_team.upper():
            base_team = re.sub(r'\(?\b(?:manual\s+yes|yes\s*\(manual\)|manual|yes)\b\)?', '', clean_team, flags=re.IGNORECASE).strip()
            pred = {"predicted_team": base_team or "YES", "confidence_pct": 100, "edge_pct": 100}
            if not explicit_side:
                explicit_side = "YES"
        elif "MANUAL" in clean_team.upper() and "NO" in clean_team.upper():
            base_team = re.sub(r'\(?\b(?:manual\s+no|no\s*\(manual\)|manual|no)\b\)?', '', clean_team, flags=re.IGNORECASE).strip()
            pred = {"predicted_team": base_team or "NO", "confidence_pct": 100, "edge_pct": 100}
            if not explicit_side:
                explicit_side = "NO"
        else:
            pred = {"predicted_team": clean_team, "confidence_pct": 100, "edge_pct": 100}
        if sport:
            pred["sport"] = sport
        elif not pred.get("sport"):
            m_s = re.search(r'KX(NFL|MLB|NBA|NHL|NCAAF|NCAAB|WNBA|NPB|KBO|SOC|UFC|TEN|MMA)', event_ticker) or re.search(r'KX([A-Z]{3,5}?)(?:GAME|-|$)', event_ticker) or re.search(r'KX([A-Z]{3,5})', event_ticker)
            if m_s:
                pred["sport"] = m_s.group(1)
            
        trade, err = _execute_sports_trade(event_ticker, pred, uid, trade_size=trade_size, explicit_side=explicit_side)
        return {
            "status": "ok" if trade else "error",
            "event_ticker": event_ticker,
            "prediction": pred,
            "criteria_met": True,
            "executed": bool(trade),
            "trade": trade,
            "trade_id": trade.get("id") if trade else None,
            "error": err if not trade else None
        }

    return api_sports_predict(
        event_ticker=event_ticker,
        execute=True,
        min_confidence=min_confidence if min_confidence is not None else 0.0,
        min_edge=min_edge if min_edge is not None else 0.0,
        user_id=user_id,
        title=title,
        sport=sport,
        trade_size=trade_size,
        side=side,
        request=request
    )

@sports_router.post("/api/engine/sports/combo", dependencies=[Depends(require_auth)])
@sports_router.get("/api/engine/sports/combo", dependencies=[Depends(require_auth)])
@sports_router.post("/api/engine/sports/combo/execute", dependencies=[Depends(require_auth)])
@sports_router.get("/api/engine/sports/combo/execute", dependencies=[Depends(require_auth)])
def api_sports_combo_execute(
    event_tickers: str = Query(...),
    teams: Optional[str] = Query(None),
    sides: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    trade_size: Optional[float] = Query(None),
    request: Request = None
):
    """
    Executes a multi-leg parlay/combo trade.
    - If user is in LIVE mode with authenticated Kalshi credentials:
      Materializes an official Kalshi Multivariate Event Combo Market (via POST /multivariate_event_collections)
      and places a SINGLE unified order on Kalshi for the combined ticket, settling as a single trade.
    - If user is in PAPER mode (or if Kalshi MVE creation is unavailable):
      Tracks the slip under a single unified combo ID with individual leg tracking.
    """
    uid = _require_user_id(user_id, request)
    tickers = [t.strip() for t in event_tickers.split(",") if t.strip()]
    team_list = [t.strip() for t in teams.split(",")] if teams else []
    side_list = [s.strip().upper() for s in sides.split(",")] if sides else []
    total_legs = len(tickers)
    
    if total_legs < 2:
        return {"status": "error", "error": "At least 2 legs are required for a combo trade.", "total_requested": total_legs, "total_executed": 0}

    from backend.database.models import get_user_by_id
    user = get_user_by_id(uid)
    mode = (user.get("trading_mode") or "PAPER").upper() if user else "PAPER"
    wager = float(trade_size) if trade_size is not None and trade_size > 0 else 10.0

    combo_id = f"combo_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    # Resolve constituent markets for each leg
    resolved_legs = []
    headers = {"Accept": "application/json", "User-Agent": "ApexProps-Trader/1.0"}
    from backend.btc.kalshi_trader import kalshi_trader, get_authenticated_trader_for_user
    if kalshi_trader.is_authenticated():
        try:
            headers = kalshi_trader._sign_headers("GET", f"/trade-api/v2/events/{tickers[0]}")
        except Exception:
            pass

    for i, ticker in enumerate(tickers):
        manual_team = team_list[i] if i < len(team_list) else "YES"
        clean_team = manual_team.strip()
        
        explicit_side = "YES"
        if i < len(side_list) and side_list[i] in ("YES", "NO"):
            explicit_side = side_list[i]
        elif "(NO)" in clean_team.upper() or "MANUAL NO" in clean_team.upper():
            explicit_side = "NO"

        base_team = re.sub(r'\(?\b(?:manual\s+yes|yes\s*\(manual\)|manual\s+no|no\s*\(manual\)|manual|yes|no)\b\)?', '', clean_team, flags=re.IGNORECASE).strip()

        # If ticker is already a direct market ticker (e.g. KXNHLTOTAL-26OCT13CGYANA-3)
        ev_ticker = ticker
        mkt_ticker = ticker
        
        # Check if ticker is a market ticker or an event ticker
        try:
            mr = requests.get(
                f"https://external-api.kalshi.com/trade-api/v2/markets/{ticker}",
                headers=headers,
                timeout=4.0
            )
            if mr.status_code == 200:
                m_obj = mr.json().get("market", {})
                mkt_ticker = m_obj.get("ticker") or ticker
                ev_ticker = m_obj.get("event_ticker") or ticker
            else:
                # Ticker is likely an event ticker, lookup nested markets
                er = requests.get(
                    f"https://external-api.kalshi.com/trade-api/v2/events/{ticker}",
                    params={"with_nested_markets": True},
                    headers=headers,
                    timeout=4.0
                )
                if er.status_code == 200:
                    evt_data = er.json().get("event", {})
                    mkts = evt_data.get("markets", [])
                    if mkts:
                        ev_ticker = evt_data.get("ticker") or ticker
                        matched = None
                        if base_team:
                            bt_lower = base_team.lower()
                            for m in mkts:
                                if bt_lower in (m.get("yes_sub_title") or "").lower() or bt_lower in (m.get("title") or "").lower():
                                    matched = m
                                    break
                        if not matched:
                            matched = mkts[0]
                        mkt_ticker = matched.get("ticker") or ticker
        except Exception as e:
            logger.debug(f"[ComboExecute] Ticker resolution error for {ticker}: {e}")

        resolved_legs.append({
            "event_ticker": ev_ticker,
            "market_ticker": mkt_ticker,
            "side": explicit_side.lower(),
            "clean_team": base_team or clean_team,
            "leg_num": i + 1
        })

    # LIVE Execution: Attempt Kalshi Multivariate Combo Creation (Strict Unified Combo — Never fall back to individual legs in LIVE mode)
    kt = get_authenticated_trader_for_user(uid) if mode == "LIVE" else None
    if mode == "LIVE":
        if not kt:
            return {"status": "error", "error": "Kalshi authentication required for LIVE combo execution.", "combo_executed": False}
        mve_legs = [
            {"event_ticker": l["event_ticker"], "market_ticker": l["market_ticker"], "side": l["side"]}
            for l in resolved_legs
        ]
        mve_res = kt.create_or_get_multivariate_market(mve_legs)
        if mve_res.get("success"):
            combo_mkt_ticker = mve_res.get("market_ticker")
            combo_evt_ticker = mve_res.get("event_ticker")
            logger.info(f"[ComboExecute] Successfully created official Kalshi Multivariate Combo: {combo_mkt_ticker}")

            # Compute combined implied probability across legs to size contracts accurately for `wager`
            combined_prob = 1.0
            for l in resolved_legs:
                leg_p = 0.87
                try:
                    q_leg = kt.get_market_quote(l["market_ticker"])
                    if q_leg.get("success"):
                        qm = q_leg.get("market", {})
                        if l["side"] == "yes":
                            ask_d = qm.get("yes_ask_dollars") or (float(qm.get("yes_ask", 0)) / 100.0 if qm.get("yes_ask") else None)
                        else:
                            ask_d = qm.get("no_ask_dollars") or (float(qm.get("no_ask", 0)) / 100.0 if qm.get("no_ask") else None)
                        if ask_d is not None and 0.01 <= float(ask_d) <= 0.99:
                            leg_p = float(ask_d)
                except Exception:
                    pass
                combined_prob *= leg_p

            combo_limit_price = max(0.01, min(0.95, round(combined_prob, 2)))
            combo_count = max(1, int(math.floor(wager / combo_limit_price)))

            # 1. Execute SINGLE unified combo order via Kalshi's RFQ + Market Maker Quote Acceptance engine
            order_res = kt.execute_mve_combo_rfq(
                combo_market_ticker=combo_mkt_ticker,
                target_cost_dollars=wager,
                target_ex=1
            )
            if not order_res.get("success"):
                order_res = kt.place_sports_order(
                    ticker=combo_mkt_ticker,
                    side="yes",
                    count=combo_count,
                    limit_price_dollars=combo_limit_price,
                    dry_run=False,
                    slippage_buffer_dollars=0.0,
                    time_in_force="good_till_canceled"
                )
            
            if order_res.get("success"):
                trade_id = str(order_res.get("order_id") or order_res.get("client_order_id") or combo_id)
                fill_price = float(order_res.get("filled_price") or combo_limit_price)
                fill_count = float(order_res.get("count") or combo_count)
                
                trade_record = {
                    "id": trade_id,
                    "order_id": trade_id,
                    "client_order_id": trade_id,
                    "user_id": uid,
                    "ticker": combo_mkt_ticker,
                    "event_ticker": combo_evt_ticker,
                    "sport": "MULTIVARIATE_COMBO",
                    "asset": "SPORTS",
                    "predicted_team": f"{total_legs}-Leg Mega Parlay ({combo_mkt_ticker})",
                    "team": f"{total_legs}-Leg Combo",
                    "trade_size_dollars": round(fill_price * fill_count, 2),
                    "side": "YES",
                    "direction": "YES",
                    "entry_price": fill_price,
                    "count": fill_count,
                    "cost": round(fill_price * fill_count, 2),
                    "pnl": 0.0,
                    "status": "OPEN",
                    "mode": "LIVE",
                    "combo_id": combo_id,
                    "prop_type": f"Mega Parlay ({total_legs} legs)",
                    "market_prop_type": "Kalshi Multivariate Combo",
                    "line": f"{total_legs} Legs All-Hit",
                    "reason": f"[Kalshi Unified Combo] Official Multivariate Contract: {combo_mkt_ticker}",
                    "trading_style": "SPORTS_COMBO",
                    "signal_source": "Kalshi Multivariate Event (MVE) Engine",
                    "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                    "ml_reasoning": json.dumps({
                        "combo_market_ticker": combo_mkt_ticker,
                        "combo_event_ticker": combo_evt_ticker,
                        "total_legs": total_legs,
                        "legs": resolved_legs
                    }),
                    "catalysts": [f"Leg {l['leg_num']}: {l['market_ticker']} ({l['side'].upper()})" for l in resolved_legs[:10]]
                }
                trade_record["raw_json"] = json.dumps(trade_record)
                from backend.database.trade_store import TradeStore
                TradeStore.insert_trade(uid, trade_record)
                
                return {
                    "status": "ok",
                    "combo_id": combo_id,
                    "combo_executed": True,
                    "is_single_kalshi_combo": True,
                    "kalshi_market_ticker": combo_mkt_ticker,
                    "trades": [trade_record],
                    "total_requested": total_legs,
                    "total_executed": 1,
                    "message": f"Successfully executed unified Kalshi {total_legs}-leg combo trade ({fill_count} contracts @ ${fill_price:.2f}) as a single order!"
                }
            else:
                logger.error(f"[ComboExecute] Kalshi unified combo order placement failed: {order_res.get('error')}")
                return {
                    "status": "error",
                    "combo_id": combo_id,
                    "combo_executed": False,
                    "is_single_kalshi_combo": False,
                    "kalshi_market_ticker": combo_mkt_ticker,
                    "error": order_res.get("error") or "Kalshi unified combo order rejected.",
                    "total_requested": total_legs,
                    "total_executed": 0
                }
        else:
            logger.error(f"[ComboExecute] Kalshi MVE creation failed: {mve_res.get('error')}")
            return {
                "status": "error",
                "combo_id": combo_id,
                "combo_executed": False,
                "is_single_kalshi_combo": False,
                "error": mve_res.get("error") or "Kalshi MVE combo creation rejected.",
                "total_requested": total_legs,
                "total_executed": 0
            }

    # Fallback execution (Paper mode, or when MVE collection cannot bundle certain foreign leagues)
    trades = []
    errors = []
    for l in resolved_legs:
        combo_info = {
            "combo_id": combo_id,
            "leg_num": l["leg_num"],
            "total_legs": total_legs
        }
        pred = {"predicted_team": l["clean_team"], "confidence_pct": 100, "edge_pct": 100}
        trade, err = _execute_sports_trade(
            l["market_ticker"],
            pred,
            uid,
            trade_size=round(wager / max(1, total_legs), 2),
            explicit_side=l["side"].upper(),
            combo_id=combo_id,
            combo_info=combo_info
        )
        if trade:
            trades.append(trade)
        else:
            errors.append({"ticker": l["market_ticker"], "error": err or f"Execution failed for {l['market_ticker']}"})

    return {
        "status": "ok" if len(trades) > 0 else "error",
        "combo_id": combo_id,
        "combo_executed": len(trades) > 0,
        "is_single_kalshi_combo": False,
        "trades": trades,
        "errors": errors,
        "total_requested": total_legs,
        "total_executed": len(trades)
    }

@sports_router.get("/api/engine/sports/combo/recommend", dependencies=[Depends(require_auth)])
def api_sports_combo_recommend(
    count: Optional[int] = Query(None),
    trade_size: Optional[float] = Query(None),
    min_prob: Optional[float] = Query(None),
    max_price: Optional[float] = Query(0.98),
    strategy: Optional[str] = Query("POWER_COMBO"),
    days_ahead: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    request: Request = None
):
    """
    Returns curated high-probability floor anchor legs (e.g. SOC Over 0.5, NHL Over 2.5/3.5, MLB Over 4.5/5.5,
    NFL Over 28.5/31.5, NBA Over 200.5, or milestone contact props) suitable
    for building a high-win-rate custom-leg Power Combo or Ultra-Floor Mega Parlay.
    Prioritizes the current day's events first and computes exact payout & profit for the user's trade size.
    """
    try:
        uid = _resolve_user_id(user_id, request)
        user = get_user_by_id(uid) if uid else None
        user_wager = float(
            trade_size
            if (trade_size is not None and float(trade_size) > 0)
            else ((user.get("sports_max_wager") if user else None) or 10.0)
        )
        include_live = bool(user.get("sports_include_live")) if user else False

        strat_clean = str(strategy or "POWER_COMBO").strip().upper()
        if strat_clean == "POWER_PARLAY":
            strat_clean = "POWER_COMBO"
        elif strat_clean in ("ULTRA_PARLAY", "MEGA_COMBO"):
            strat_clean = "ULTRA_COMBO"
        is_ultra = (strat_clean in ("ULTRA_COMBO", "MEGA_PARLAY") or (count is not None and int(count) >= 10))
        default_count = 15 if is_ultra else 3
        
        count = max(2, min(30, int(count if count is not None else default_count)))
        # For Mega Parlays and Combos, strictly minimize going below 75% confidence
        default_prob_floor = 75.0 if is_ultra else 65.0
        effective_min_prob = float(min_prob) if min_prob is not None else default_prob_floor
        effective_max_price = min(0.98, float(max_price) if max_price is not None else 0.98)
        
        # Calculate date offsets for prioritizing current day's events
        now_et = datetime.now(ZoneInfo("America/New_York"))
        today_date = now_et.date()
        
        # Fetch full slate across all sports (pass user=None so restrictive sport toggles don't starve parlay legs)
        all_events = fetch_sports_events_data("ALL", None, strategy=strat_clean)
        candidates = []
        seen_tickers = set()
        seen_matchup_types = set()
        
        for ev in all_events:
            if not ev.get("has_ai_prediction"):
                continue
            if ev.get("is_live") and not include_live:
                continue
            strat = ev.get("strategy_tag") or classify_event_strategy(ev)
            conf = float(ev.get("confidence_pct") or 0.0)
            pick = ev.get("ai_pick") or ev.get("predicted_team")
            # If user explicitly provided min_prob, filter strictly. Otherwise allow down to 55% as backfill pool if needed
            if not pick or conf < (effective_min_prob if min_prob is not None else 55.0):
                continue
                
            # Filter by days_ahead if explicitly requested
            ev_date_str = ev.get("event_date")
            ev_d = None
            if ev_date_str:
                try:
                    ev_d = datetime.strptime(str(ev_date_str)[:10], "%Y-%m-%d").date()
                except:
                    pass
            days_diff = (ev_d - today_date).days if ev_d else 0
            if days_ahead is not None and ev_d and days_diff > int(days_ahead):
                continue
                
            markets = ev.get("markets") or []
            best_m = markets[0] if markets else None
            if not best_m:
                continue
                
            m_ticker = best_m.get("ticker") or ev.get("ticker")
            if not m_ticker or m_ticker in seen_tickers:
                continue
                
            side_str = str(ev.get("pick_side") or "YES").upper()
            raw_price = (
                (best_m.get("no_ask_dollars") or best_m.get("no_ask") or ev.get("no_ask"))
                if side_str == "NO"
                else (best_m.get("yes_ask_dollars") or best_m.get("yes_ask") or ev.get("yes_ask"))
            )
            yes_price = float(raw_price or 0.5)
            if yes_price > 1.0:
                yes_price /= 100.0
                
            if not (0.10 <= yes_price <= effective_max_price):
                continue
                
            matchup = ev.get("matchup") or ev.get("title") or m_ticker
            norm_m = "".join(re.findall(r'[a-zA-Z0-9]+', matchup.lower()))
            m_type_key = f"{norm_m}:{strat}:{ev.get('segment') or 'Main'}"
            if m_type_key in seen_matchup_types:
                continue
                
            candidates.append({
                "ticker": m_ticker,
                "event_ticker": ev.get("ticker") or ev.get("event_ticker"),
                "sport": ev.get("sport") or ev.get("league"),
                "team": pick,
                "side": side_str,
                "price": round(yes_price, 2),
                "price_cents": int(round(yes_price * 100)),
                "confidence": round(conf, 1),
                "edge": round(float(ev.get("edge_pct") or 0.0), 1),
                "prop_type": ev.get("prop_type") or ev.get("market_type") or "Total",
                "line": ev.get("line") or ev.get("strike_details") or ("Floor Line" if strat == "FLOOR_TOTALS" else "Moneyline"),
                "matchup": matchup,
                "strategy": strat,
                "norm_matchup": norm_m,
                "is_today": bool(ev.get("is_today") or days_diff == 0),
                "days_diff": max(0, days_diff),
                "event_date": str(ev_date_str) if ev_date_str else str(today_date)
            })
            seen_tickers.add(m_ticker)
            seen_matchup_types.add(m_type_key)
            
        # Score candidates: Prioritize confidence >= 75% tier FIRST (+1000 bonus), then today's events (+300), then strategy bonus
        def _score(c):
            conf = c["confidence"]
            if conf >= 75.0:
                conf_tier = 1000.0
            elif conf >= 70.0:
                conf_tier = 400.0
            elif conf >= 65.0:
                conf_tier = 100.0
            else:
                conf_tier = 0.0
                
            if c["is_today"] or c["days_diff"] == 0:
                day_bonus = 300.0
            else:
                day_bonus = max(0.0, 150.0 - (c["days_diff"] * 40.0))
                
            strat_bonus = 35.0 if c["strategy"] == "FLOOR_TOTALS" else (20.0 if c["strategy"] == "MILESTONE_PROPS" else 0.0)
            edge_bonus = max(-25.0, min(60.0, float(c.get("edge") or 0.0) * 8.0))
            price_sweet_spot = 25.0 if (0.65 <= c["price"] <= 0.94) else (-20.0 if c["price"] >= 0.97 else 0.0)
            return conf_tier + day_bonus + strat_bonus + edge_bonus + price_sweet_spot + (conf * 1.5)
            
        candidates.sort(key=_score, reverse=True)
        
        # Pass 1: unique matchups first, strictly prioritizing >= 75% confidence and today's events
        selected_legs = []
        used_matchups = set()
        overflow_legs = []
        for c in candidates:
            nm = c.pop("norm_matchup", "")
            if nm not in used_matchups:
                selected_legs.append(c)
                used_matchups.add(nm)
                if len(selected_legs) >= count:
                    break
            else:
                overflow_legs.append(c)
                
        # Pass 2: if still under requested count, fill from remaining distinct markets
        if len(selected_legs) < count and overflow_legs:
            for c in overflow_legs:
                selected_legs.append(c)
                if len(selected_legs) >= count:
                    break
        
        if len(selected_legs) >= 2:
            joint_prob = 1.0
            payout_multiplier = 1.0
            for leg in selected_legs:
                joint_prob *= (leg["confidence"] / 100.0)
                payout_multiplier *= (1.0 / max(0.05, leg["price"]))
            projected_roi = max(0.0, round((payout_multiplier - 1.0) * 100.0, 1))
            joint_win_pct = round(joint_prob * 100.0, 1)
            projected_payout = round(user_wager * payout_multiplier, 2)
            projected_profit = round(max(0.0, projected_payout - user_wager), 2)
        else:
            payout_multiplier = 1.0
            joint_win_pct = 0.0
            projected_roi = 0.0
            projected_payout = round(user_wager, 2)
            projected_profit = 0.0
            
        strat_label = f"ULTRA_{len(selected_legs)}_COMBO" if is_ultra else f"POWER_{len(selected_legs)}_COMBO"
        return {
            "status": "ok",
            "recommended_strategy": strat_label,
            "requested_legs": count,
            "legs_found": len(selected_legs),
            "wager_dollars": round(user_wager, 2),
            "payout_multiplier": round(payout_multiplier, 3),
            "projected_payout_dollars": projected_payout,
            "projected_profit_dollars": projected_profit,
            "joint_win_prob_pct": joint_win_pct,
            "projected_roi_pct": projected_roi,
            "legs": selected_legs
        }
    except Exception as e:
        logger.error(f"[SportsComboRecommend] Error: {e}")
        return {"status": "error", "error": str(e), "legs": []}

@sports_router.post("/api/engine/sports/trade/manual", dependencies=[Depends(require_auth)])
@sports_router.get("/api/engine/sports/trade/manual", dependencies=[Depends(require_auth)])
async def api_sports_trade_manual(
    event_ticker: Optional[str] = Query(None),
    ticker: Optional[str] = Query(None),
    market_ticker: Optional[str] = Query(None),
    side: Optional[str] = Query("YES"),
    direction: Optional[str] = Query(None),
    manual_team: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    sport: Optional[str] = Query(None),
    trade_size: Optional[float] = Query(None),
    amount_dollars: Optional[float] = Query(None),
    user_id: Optional[int] = Query(None),
    request: Request = None
):
    body = {}
    if request:
        try:
            body = await request.json()
        except Exception:
            body = {}

    tk = event_ticker or ticker or market_ticker or body.get("event_ticker") or body.get("ticker") or body.get("market_ticker")
    if not tk or not str(tk).strip():
        return JSONResponse({"status": "error", "error": "Missing event or market ticker", "executed": False, "trade": None}, status_code=400)

    target_ticker = str(tk).strip()
    target_side = (direction or side or body.get("direction") or body.get("side") or "YES").upper()
    team_name = manual_team or team or body.get("manual_team") or body.get("team") or body.get("predicted_team") or (body.get("prediction") if isinstance(body.get("prediction"), dict) else {}).get("predicted_team") or ("YES" if target_side == "YES" else "NO")
    size_val = trade_size if trade_size is not None else (amount_dollars if amount_dollars is not None else (body.get("trade_size") or body.get("amount_dollars")))
    size_flt = float(size_val) if size_val is not None else None
    sport_name = sport or body.get("sport")
    uid = _require_user_id(user_id or body.get("user_id"), request)

    pred = {"predicted_team": team_name, "confidence_pct": 100.0, "edge_pct": 100.0}
    if sport_name:
        pred["sport"] = sport_name

    trade, err = _execute_sports_trade(target_ticker, pred, uid, trade_size=size_flt, explicit_side=target_side)
    if not trade:
        return JSONResponse({
            "status": "error",
            "executed": False,
            "error": err or f"Trade execution failed for {target_ticker}",
            "trade": None
        }, status_code=400)

    return {
        "status": "ok",
        "executed": True,
        "trade": trade,
        "trade_id": trade.get("id"),
        "mode": trade.get("mode")
    }

@sports_router.post("/api/engine/sports/slip/submit", dependencies=[Depends(require_auth)])
async def api_sports_slip_submit(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}

    items = data.get("items") or data.get("trades") or data.get("slip")
    if not items and isinstance(data, list):
        items = data
    elif not items and (data.get("ticker") or data.get("event_ticker")):
        items = [data]

    if not items:
        return JSONResponse({"status": "error", "error": "No items provided in trade slip", "executed_count": 0, "trades": []}, status_code=400)

    uid = _require_user_id(data.get("user_id"), request)
    global_trade_size = data.get("trade_size") or data.get("amount_dollars")

    executed_trades = []
    errors = []

    for item in items:
        tk = item.get("ticker") or item.get("event_ticker")
        if not tk:
            continue
        team = item.get("team") or item.get("manual_team") or item.get("predicted_team") or "YES"
        item_side = (item.get("side") or item.get("direction") or "YES").upper()
        size_val = item.get("trade_size") or item.get("amount_dollars") or global_trade_size
        size_flt = float(size_val) if size_val is not None else None
        sport_val = item.get("sport")

        pred = {"predicted_team": team, "confidence_pct": 100.0, "edge_pct": 100.0}
        if sport_val:
            pred["sport"] = sport_val

        trade, err = _execute_sports_trade(str(tk).strip(), pred, uid, trade_size=size_flt, explicit_side=item_side)
        if trade:
            executed_trades.append(trade)
        else:
            errors.append({"ticker": tk, "error": err or "Execution failed"})

    return {
        "status": "ok" if executed_trades else "error",
        "executed_count": len(executed_trades),
        "total_items": len(items),
        "trades": executed_trades,
        "errors": errors
    }


@sports_router.get("/api/engine/status")
def api_engine_status(request: Request = None):
    return JSONResponse({"status": "ok"})



@sports_router.get("/api/engine/sports/narrative_stats")
def api_narrative_stats():
    from backend.sports_bridge.prediction_client import _NARRATIVE_CACHE
    return {"total_cached": len(_NARRATIVE_CACHE), "keys": list(_NARRATIVE_CACHE.keys())}


