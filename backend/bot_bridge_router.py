from fastapi import APIRouter
import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

import httpx

from backend.data.distributed_cache import cache_response

logger = logging.getLogger(__name__)

try:
    from backend.nfl_api import api_top_picks_feed as get_nfl_picks
except ImportError:
    get_nfl_picks = lambda week=None: {"top_picks": []}

try:
    from backend.main import get_top5_picks as get_mlb_picks
except ImportError:
    get_mlb_picks = lambda: {"top_6": []}

bridge_router = APIRouter(prefix="/api/bot-bridge")

SELF_BASE = "http://127.0.0.1:8057"
MAX_PER_SPORT = 15

# sport code -> local endpoint that returns {"top_picks": [...]}
HTTP_SOURCES = {
    "NHL": "/api/hockey/top_picks",
    "SOCCER": "/api/soccer/top_picks",
    "TENNIS": "/api/tennis/top_picks",
    "UFC": "/api/ufc/top_picks",
    "NBA": "/api/nba/top_picks",
    "NCAAF": "/api/ncaaf/top_picks",
    "NPB": "/api/npb_kbo/top_picks",
    "NBA": "/api/nba/top_picks",
    "NCAAF": "/api/ncaaf/top_picks",
}


def _num(v, default=0.0):
    """Parse numbers like 63.6, '+27.6%', '0.636' into float."""
    if v is None:
        return default
    try:
        return float(str(v).replace("+", "").replace("%", "").strip())
    except (ValueError, TypeError):
        return default


def _normalize(sport: str, p: dict) -> dict:
    conf = _num(p.get("prob", p.get("cover_prob", p.get("win_prob", p.get("confidence")))), 50.0)
    if 0 < conf <= 1.0:
        conf *= 100.0
    edge = _num(p.get("edge", p.get("edge_percent", 0.0)))

    matchup = p.get("matchup") or ""
    name = p.get("name") or p.get("player_or_team") or ""
    # Game-level picks (UFC "Fight Duration", totals) -> show the matchup as the headline
    if not name or name in (p.get("type"), p.get("stat_name")):
        name = matchup or name

    meta = dict(p)
    meta.setdefault("line", p.get("line") or p.get("book_line") or p.get("target_desc") or p.get("stat_name") or "")
    meta.setdefault("matchup", matchup)
    if sport == "NPB":
        meta["league_label"] = p.get("league_code") or "NPB/KBO"

    return {
        "sport": sport,
        "market_type": p.get("type") or p.get("stat_name") or "MONEYLINE",
        "predicted_team": name,
        "opponent": p.get("opponent") or matchup,
        "confidence_pct": round(conf, 1),
        "edge_pct": round(edge, 1),
        "metadata": meta,
    }


def _fetch_http(sport: str, path: str) -> list:
    try:
        r = httpx.get(SELF_BASE + path, timeout=45.0)
        r.raise_for_status()
        picks = r.json().get("top_picks", []) or []
        return [_normalize(sport, p) for p in picks if isinstance(p, dict)]
    except Exception as e:
        logger.warning(f"[BotBridge] {sport} fetch failed: {e}")
        return []


def _fetch_nfl() -> list:
    try:
        return [_normalize("NFL", p) for p in get_nfl_picks().get("top_picks", [])]
    except Exception as e:
        logger.warning(f"[BotBridge] NFL failed: {e}")
        return []


def _fetch_mlb() -> list:
    try:
        from backend.main import get_top5_picks  # lazy: avoids circular import at startup
        return [_normalize("MLB", p) for p in get_top5_picks().get("top_6", [])]
    except Exception as e:
        logger.warning(f"[BotBridge] MLB failed: {e}")
        return []


# ─────────────────────────── "Today & not started" filter ───────────────────────────
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:  # tzdata missing on Windows -> fixed EDT offset
    ET = datetime.timezone(datetime.timedelta(hours=-4))

# sport -> (slate endpoint, list key, id keys)
SLATES = {
    "NFL": ("/api/nfl/games", "games", ("matchup", "game_id", "id")),
    "MLB": ("/api/slate", "games", ("game_id",)),
    "NHL": ("/api/hockey/slate", "matches", ("id",)),
    "SOCCER": ("/api/soccer/slate", "matches", ("id", "match_id")),
    "UFC": ("/api/ufc/slate", "fights", ("id",)),
    "NBA": ("/api/nba/slate", "games", ("game_id",)),
    "NCAAF": ("/api/ncaaf/slate", "games", ("game_id",)),
    "NPB": ("/api/npb_kbo/slate", "games", ("game_id",)),
    "NBA": ("/api/nba/slate", "games", ("game_id",)),
    "NCAAF": ("/api/ncaaf/slate", "games", ("game_id",)),
}
STARTED_WORDS = ("final", "full time", "progress", "half", "live", "post", "end", "ft", "aet", "delay", "postponed", "cancel")


def _parse_iso(v):
    if not isinstance(v, str) or len(v) < 16 or v[4] != "-" or "T" not in v:
        return None
    try:
        dt = datetime.datetime.fromisoformat(v.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def _classify(g: dict, slate_is_today=None):
    """Return (is_today, not_started, start_label) for a slate game / pick dict."""
    now = datetime.datetime.now(ET)
    today = now.date()
    status = str(g.get("status") or g.get("status_detail") or "").strip().lower()

    started = bool(g.get("is_live")) or bool(g.get("is_final")) or bool(g.get("is_postponed"))
    if status in ("in", "post") or any(w in status for w in STARTED_WORDS):
        started = True

    dt = None
    for k in ("commence_time", "date", "game_time", "start_utc"):
        dt = _parse_iso(g.get(k))
        if dt:
            break

    is_today = None
    label = g.get("start_time") or g.get("game_time") or ""
    if dt:
        local = dt.astimezone(ET)
        is_today = local.date() == today
        if dt <= now:
            started = True
        label = local.strftime("%I:%M %p ET").lstrip("0")
    if is_today is None and "is_today" in g:
        is_today = bool(g.get("is_today"))
    if is_today is None:
        gd = str(g.get("game_date") or "")
        dl = str(g.get("date_label") or "")
        ymd = today.strftime("%Y%m%d")
        md1, md2 = today.strftime("%b %d"), f"{today.strftime('%b')} {today.day}"
        if gd.lower().startswith("today") or gd == ymd or "today" in dl.lower() or md1 in dl or md2 in dl:
            is_today = True
        elif ymd in str(g.get("id") or g.get("game_id") or ""):
            is_today = True
        elif slate_is_today is not None:
            is_today = bool(slate_is_today)
        else:
            is_today = False
    return is_today, (not started), label


def _fetch_slate_index(sport: str) -> dict:
    path, list_key, id_keys = SLATES[sport]
    try:
        d = httpx.get(SELF_BASE + path, timeout=45.0).json()
        idx = {}
        for g in d.get(list_key, []) or []:
            info = _classify(g, d.get("is_today"))
            for k in id_keys:
                if g.get(k):
                    idx[str(g[k])] = info
        return idx
    except Exception as e:
        logger.warning(f"[BotBridge] {sport} slate failed: {e}")
        return {}


def _upcoming_today(sport: str, pick: dict, idx: dict):
    md = pick["metadata"]
    if sport == "TENNIS":  # tennis picks carry their own time/status fields
        return _classify(md)
    for k in ("game_id", "match_id", "matchup"):
        v = md.get(k)
        if v and str(v) in idx:
            return idx[str(v)]
    return (False, False, "")  # unknown game -> hide (safer than showing a stale pick)


@bridge_router.get("/predictions")
@cache_response(ttl_seconds=120)
def get_bot_predictions(include_live: bool = False):
    with ThreadPoolExecutor(max_workers=14) as pool:
        pick_futs = {"NFL": pool.submit(_fetch_nfl), "MLB": pool.submit(_fetch_mlb)}
        pick_futs.update({s: pool.submit(_fetch_http, s, p) for s, p in HTTP_SOURCES.items()})
        slate_futs = {s: pool.submit(_fetch_slate_index, s) for s in SLATES}
        indexes = {s: f.result() for s, f in slate_futs.items()}
        by_sport = {s: f.result() for s, f in pick_futs.items()}

    bot_picks = []
    for sport, picks in by_sport.items():
        idx = indexes.get(sport, {})
        kept = []
        for p in picks:
            is_today, not_started, label = _upcoming_today(sport, p, idx)
            if sport not in ("TENNIS", "TEN") and (not is_today or not (not_started or include_live)):
                continue
            p["metadata"]["start_label"] = label
            p["metadata"]["is_upcoming"] = not_started
            kept.append(p)
        kept.sort(key=lambda x: (x["edge_pct"], x["confidence_pct"]), reverse=True)
        bot_picks.extend(kept[:MAX_PER_SPORT])

    from backend.engine.gemini_veto import process_predictions_for_veto
    process_predictions_for_veto(bot_picks)

    return {
        "success": True,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "filter": "today_live" if include_live else "today_upcoming",
        "predictions": sorted(bot_picks, key=lambda x: x["confidence_pct"], reverse=True),
    }

from pydantic import BaseModel
import os
import uuid

import time
from httpx import RequestError, HTTPStatusError

import threading

class CircuitBreaker:
    def __init__(self, threshold=3, recovery_time=60):
        self.threshold = threshold
        self.recovery_time = recovery_time
        self.failures = 0
        self.last_failure = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.lock = threading.Lock()

    def record_failure(self):
        with self.lock:
            self.failures += 1
            self.last_failure = time.time()
            if self.failures >= self.threshold:
                self.state = "OPEN"

    def record_success(self):
        with self.lock:
            self.failures = 0
            self.state = "CLOSED"

    def acquire(self):
        with self.lock:
            if self.state == "CLOSED":
                return True
            if self.state == "OPEN":
                if time.time() - self.last_failure > self.recovery_time:
                    self.state = "HALF_OPEN"
                    return True
                return False
            if self.state == "HALF_OPEN":
                # Only let one request through to probe
                return False
        return False

kalshi_cb = CircuitBreaker()

def robust_kalshi_post(url: str, json: dict = None, headers: dict = None, max_retries: int = 3, timeout: float = 10.0):
    if not kalshi_cb.acquire():
        raise Exception("Kalshi API circuit breaker is open due to recent failures.")
    
    last_err = None
    for attempt in range(max_retries):
        try:
            resp = httpx.post(url, json=json, headers=headers, timeout=timeout)
            resp.raise_for_status()
            kalshi_cb.record_success()
            return resp
        except (RequestError, HTTPStatusError) as e:
            last_err = e
            if isinstance(e, HTTPStatusError) and e.response.status_code < 500 and e.response.status_code != 429:
                # Do not retry client errors (except 429 Too Many Requests).
                # Client errors (4xx) mean Kalshi is up and responding properly, so this is a success for the breaker.
                kalshi_cb.record_success()
                raise e
            # For 5xx, timeouts, or network drops, sleep and retry
            time.sleep(2 ** attempt)
        except Exception as e:
            last_err = e
            time.sleep(2 ** attempt)
            
    kalshi_cb.record_failure()
    raise last_err

class OrderRequest(BaseModel):
    ticker: str
    action: str  # 'buy' or 'sell'
    type: str = "market"
    yes_price: int = None
    no_price: int = None
    count: int

@bridge_router.post("/execute")
def execute_order(req: OrderRequest):
    """Executes an order on Kalshi."""
    from backend.engine.gemini_veto import check_veto_for_ticker
    veto_info = check_veto_for_ticker(req.ticker)
    if veto_info.get("vetoed"):
        return {"success": False, "error": "Vetoed by Gemini", "reason": veto_info.get("reason")}

    kalshi_email = os.getenv("KALSHI_EMAIL")
    kalshi_password = os.getenv("KALSHI_PASSWORD")
    if not kalshi_email or not kalshi_password:
        return {"success": False, "error": "KALSHI_EMAIL or KALSHI_PASSWORD not set"}
    
    # 1. Login
    login_url = "https://trading-api.kalshi.com/trade-api/v2/login"
    try:
        login_resp = robust_kalshi_post(login_url, json={"email": kalshi_email, "password": kalshi_password}, timeout=10.0)
        token = login_resp.json().get("token")
    except Exception as e:
        return {"success": False, "error": f"Login failed: {e}"}

    # 2. Place Order
    order_url = "https://trading-api.kalshi.com/trade-api/v2/portfolio/orders"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "action": req.action,
        "client_order_id": str(uuid.uuid4()),
        "count": req.count,
        "side": "yes" if req.yes_price else "no",
        "ticker": req.ticker,
        "type": req.type,
    }
    if req.yes_price:
        payload["yes_price"] = req.yes_price
    elif req.no_price:
        payload["no_price"] = req.no_price

    try:
        order_resp = robust_kalshi_post(order_url, headers=headers, json=payload, timeout=10.0)
        return {"success": True, "order": order_resp.json().get("order")}
    except Exception as e:
        err_msg = order_resp.text if 'order_resp' in locals() else str(e)
        return {"success": False, "error": f"Order placement failed: {e}", "details": err_msg}
