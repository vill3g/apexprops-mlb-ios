import logging
import asyncio
import json
import sqlite3
import sys
from contextlib import asynccontextmanager

import requests.exceptions

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        logging.getLogger(__name__).warning(f"Failed to set Windows event loop policy: {e}")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
"""
FastAPI Application for ApexProps MLB & International Baseball Engine.
Serves REST API and hosts the graphical user interface.
"""

from enum import Enum
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
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
import hmac
import os
import time

from backend.btc.indicators import add_all_indicators


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
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        logger.warning(f"[Startup] Could not set loop exception handler: {e}")

def _start_liquidation_feed():
    """Safe startup hook — won't crash the server if the stream fails."""
    try:
        from backend.btc.liquidation_stream import \
            start_stream as start_liquidation_stream
        start_liquidation_stream()
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        logger.warning(f"[Startup] Liquidation stream failed to start: {e}. Trading will continue without live liquidation data.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Windows socket drop handler
    _setup_socket_exception_handler()
    # 2. Liquidation websocket feed
    _start_liquidation_feed()
    # 3. Self-healing position reconciler for expired open contracts
    try:
        from backend.database.trade_repository import \
            reconcile_expired_open_trades
        reconciled = reconcile_expired_open_trades()
        if reconciled > 0:
            logger.info(f"[Startup] Self-healed {reconciled} expired open trades.")
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        logger.warning(f"[Startup] Startup position reconciliation skipped: {e}")
    # 4. Background autotrader & watchdog
    start_background_tasks()
    yield

# Interactive API docs (/docs, /redoc, /openapi.json) are off by default so the public
# tunnel doesn't advertise every endpoint. Set ENABLE_API_DOCS=1 in .env to turn them on.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except ImportError:
    pass
_API_DOCS = os.environ.get("ENABLE_API_DOCS", "").strip().lower() in ("1", "true", "yes")

app = FastAPI(
    title="BTC 15M Pattern & Confluence Engine",
    version="4.0.0",
    description="Real-time Bitcoin 15-Minute Pattern & Confluence Analyzer.",
    lifespan=lifespan,
    docs_url="/docs" if _API_DOCS else None,
    redoc_url="/redoc" if _API_DOCS else None,
    openapi_url="/openapi.json" if _API_DOCS else None,
)
from collections import defaultdict
import time
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app_to_wrap):
        super().__init__(app_to_wrap)
        self.rate_limit_records = defaultdict(list)
        self.lock = asyncio.Lock()

    async def dispatch(self, request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Only rate-limit API calls, not static assets
        if request.url.path.startswith("/api/"):
            is_polling = request.method == "GET" and (
                "/dashboard_stats" in request.url.path or
                "/chart" in request.url.path or
                "/kalshi" in request.url.path or
                "/live/poll" in request.url.path
            )
            if not is_polling:
                async with self.lock:
                    # Clean up old records (60s window)
                    self.rate_limit_records[client_ip] = [t for t in self.rate_limit_records[client_ip] if now - t < 60.0]
                    
                    # 5000 requests per minute limit for API endpoints
                    if len(self.rate_limit_records[client_ip]) >= 5000:
                        return JSONResponse(status_code=429, content={"detail": "Rate Limit Exceeded. Please slow down."})
                        
                    self.rate_limit_records[client_ip].append(now)

        response = await call_next(request)
        
        # Add Security Headers
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "font-src 'self' https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https: wss:;"
        )
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response

app.add_middleware(SecurityMiddleware)

from backend.database.models import init_db

init_db()
from backend.auth.routes import router as auth_router

app.include_router(auth_router)
from backend.auth.admin_routes import router as auth_admin_router

app.include_router(auth_admin_router)
from backend.routes.trading import router as trading_router

app.include_router(trading_router)
from backend.routes.engine import router as engine_router, _engine_root_router as engine_root_router

app.include_router(engine_root_router)
app.include_router(engine_router)
from backend.routes.sports import router as sports_router

app.include_router(sports_router)
from backend.routes.admin import router as guest_admin_router

app.include_router(guest_admin_router)
from backend.routes.scalp import router as scalp_router

app.include_router(scalp_router)
from backend.routes.ui import router as ui_router

app.include_router(ui_router)



# Allowed CORS origins
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "").strip()
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
if not allowed_origins:
    allowed_origins = [
        "http://localhost:8058",
        "http://127.0.0.1:8058",
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
    expose_headers=["X-Refreshed-Token"],
)

# Shared-Secret API Authentication for Sensitive Trading & Scalp Endpoints
# If APP_API_TOKEN is set in the environment, requests must provide a matching X-API-Token header.
# If APP_API_TOKEN is empty/unset, authentication is bypassed for seamless local desktop/LAN use.
API_TOKEN = os.environ.get("APP_API_TOKEN", "").strip()

def require_auth(
    request: Request,
    x_api_token: Optional[str] = Header(None, alias="X-API-Token")
):
    """Shared-secret, LAN, or JWT authentication dependency."""
    # 1. Try SaaS JWT first (from Authorization header or saas_token cookie)
    #    This ensures request.state.user_id is always populated even on localhost/LAN.
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    elif request.cookies.get("saas_token"):
        token = request.cookies.get("saas_token")

    if token:
        try:
            from backend.auth.security import decode_jwt_token
            payload = decode_jwt_token(token)
            if payload:
                request.state.user_id = payload.get("user_id")
                return
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
            logger.warning(f"Failed to decode SaaS JWT: {e}")

    # 2. Allow loopback and private LAN clients (same Wi-Fi network)
    client_host = getattr(request.client, "host", "") if request.client else ""
    if client_host in ("127.0.0.1", "localhost", "::1", "testclient") or client_host.startswith("192.168.") or client_host.startswith("10.") or client_host.startswith("fe80:"):
        return

    # 3. Try Master API Token
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
        qs = parse_qs(request.url.query)
        guest_id = (qs.get("guest") or [None])[0]
        if guest_id:
            # If guest_id is numeric, treat it as targeting that registered user rather than a guest token
            if not guest_id.isdigit():
                if not is_valid_guest(guest_id):
                    return JSONResponse({"error": "Invalid guest token"}, status_code=401)
                request.state.guest_id = guest_id
            else:
                request.state.guest_id = None
                request.state.target_user_id = int(guest_id)
        else:
            request.state.guest_id = None
        response = await call_next(request)
        return response

app.add_middleware(GuestMiddleware)


# ── Cross-site request protection (CSRF) ─────────────────────────────
# The login cookie is sent with cross-site requests, and callers on this PC/LAN are
# trusted as the owner, so a random website could otherwise make the browser POST
# to this app (delete users, place trades...). Browsers always label such requests
# with an Origin (or Referer) header, so any state-changing request from a foreign
# page is refused. Requests without those headers (scripts, the phone app's native
# layer) are unaffected.
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_TRUSTED_ORIGINS = {o.lower().rstrip("/") for o in allowed_origins} | {
    "capacitor://localhost", "ionic://localhost", "https://localhost", "http://localhost",
}


@app.middleware("http")
async def block_cross_site_writes(request: Request, call_next):
    if request.method not in _SAFE_METHODS:
        source = request.headers.get("origin")
        if not source:
            ref = request.headers.get("referer")
            if ref:
                parts = urlsplit(ref)
                source = f"{parts.scheme}://{parts.netloc}" if parts.netloc else "null"
        if source:
            source = source.strip().lower().rstrip("/")
            source_host = urlsplit(source).netloc
            request_host = (request.headers.get("host") or "").lower()
            if source not in _TRUSTED_ORIGINS and not (source_host and source_host == request_host):
                logger.warning(f"[Security] Blocked cross-site {request.method} {request.url.path} from {source}")
                return JSONResponse({"detail": "Cross-site request blocked."}, status_code=403)
    return await call_next(request)


# ── Seamless JWT secret migration ─────────────────────────────────────
# Sessions signed with the old default secret keep working during the
# migration window; each response hands the browser a replacement token
# signed with the new secret (X-Refreshed-Token header + saas_token cookie).
@app.middleware("http")
async def refresh_legacy_session_token(request: Request, call_next):
    response = await call_next(request)
    try:
        auth_header = request.headers.get("Authorization") or ""
        token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
        if not token or token in ("null", "undefined", "None"):
            token = request.cookies.get("saas_token") or ""
        if token:
            from backend.auth.security import (create_jwt_token,
                                               decode_jwt_token)
            payload = decode_jwt_token(token)
            if payload and payload.get("_legacy") and payload.get("user_id") is not None:
                new_token = create_jwt_token(payload["user_id"], payload.get("username", ""))
                response.headers["X-Refreshed-Token"] = new_token
                response.set_cookie(
                    key="saas_token", value=new_token, max_age=60 * 60 * 24 * 90,
                    path="/", samesite="none", secure=True, httponly=False,
                )
    except Exception as e:
        logger.warning(f"[Auth] Legacy token refresh skipped: {e}")
    return response

def _get_guest_id(request: Request) -> Optional[str]:
    """Helper to extract guest_id from request.state (set by GuestMiddleware)."""
    return getattr(request.state, "guest_id", None)

def require_owner(request: Request):
    """Dependency that blocks guest users from owner-only operations."""
    guest_id = _get_guest_id(request)
    if guest_id:
        raise HTTPException(status_code=403, detail="This operation is not available in guest mode.")


# Sports model singletons now live in backend/routes/sports.py (the routes that use them).

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")






























# =====================================================================
# AUTONOMOUS KALSHI TRADING REST ENDPOINTS
# =====================================================================











def _retrain_ml_engines(data: dict):
    data.get("tradingStyle", "SNIPER")
    # Update settings for all active engine styles
    for st in ["SNIPER", "MOMENTUM_SURFER", "AMBUSH", "CHOP"]:
        eng = get_ml_engine(trading_style=st)
        eng.apply_settings(data)
        
        # Force retraining using historical candles in the background
        try:
            from backend.btc.data_fetcher import fetch_15m_candles_history
            hist_df = fetch_15m_candles_history(days=60)
            if hist_df is not None and not hist_df.empty:
                df_ind = add_all_indicators(hist_df)
                eng.self_train_on_historical_market(df_ind)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
            logger.warning(f"Failed to self-train: {e}")












# ── Scalp Engine Endpoints ────────────────────────────────────────────






# ── Guest Admin Endpoints ─────────────────────────────────────────────




# ── Guest Identity Endpoint ───────────────────────────────────────────




# =====================================================================
# BACKGROUND AUTO-TRADER TASK & WATCHDOG
# =====================================================================
_last_autotrader_heartbeat = time.time()





# =====================================================================
# FOREX ROUTES & INTEGRATION
# =====================================================================



def start_background_tasks():
    pass

# Mount static directory and route index

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

from backend.database.models import DATA_DIR as _USERS_DATA_DIR
import logging
from urllib.parse import parse_qs
from urllib.parse import urlsplit
from backend.btc.ml_engine import get_ml_engine
from backend.auth.routes import PROFILE_PIC_TYPES

PROFILES_DIR = os.path.join(_USERS_DATA_DIR, "profiles")
os.makedirs(PROFILES_DIR, exist_ok=True)


@app.get("/profiles/{filename}")
def serve_profile_picture(filename: str):
    """Serve uploaded profile pictures as images only (never as HTML/SVG/script)."""
    name = os.path.basename(filename)
    ext = os.path.splitext(name)[1].lower()
    path = os.path.join(PROFILES_DIR, name)
    if ext not in PROFILE_PIC_TYPES or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, media_type=PROFILE_PIC_TYPES[ext], headers={
        "X-Content-Type-Options": "nosnif",
        "Content-Security-Policy": "default-src 'none'",
        "Cache-Control": "public, max-age=300",
    })


















