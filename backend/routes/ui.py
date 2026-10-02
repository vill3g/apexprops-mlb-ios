import logging
import os
from typing import Optional

from fastapi import Response, APIRouter, Header, Request
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)


# Main imports
from backend.auth.dependencies import STATIC_DIR
from backend.auth.routes import (copy_community_user_settings,
                                 get_community_leaderboard, get_current_user,
                                 get_optional_user)

router = APIRouter()

@router.get("/api/social/leaderboard")
def api_social_leaderboard(authorization: Optional[str] = Header(None)):
    """Convenience alias for /api/auth/community leaderboard endpoint."""

    current_user = get_optional_user(authorization)
    return get_community_leaderboard(current_user)

@router.post("/api/social/copy_settings/{target_user_id}")
def api_social_copy_settings(target_user_id: int, authorization: Optional[str] = Header(None)):
    """Convenience alias for /api/auth/community/copy_settings/{target_user_id}."""

    current_user = get_current_user(authorization)
    return copy_community_user_settings(target_user_id, current_user)

@router.get("/api/health")
def health_check():
    return {"status": "ok", "version": "4.1.0", "service": "BTC 15M Engine"}

@router.api_route("/favicon.ico", methods=["GET", "HEAD"])
def serve_root_favicon():

    ico_path = os.path.join(STATIC_DIR, "assets", "app_icon.ico")
    if os.path.exists(ico_path):
        return FileResponse(ico_path, media_type="image/x-icon")
    return Response(status_code=404)

@router.api_route("/apple-touch-icon.png", methods=["GET", "HEAD"])
@router.api_route("/apple-touch-icon-precomposed.png", methods=["GET", "HEAD"])
def serve_root_apple_touch_icon():

    icon_path = os.path.join(STATIC_DIR, "assets", "apple-touch-icon.png")
    if os.path.exists(icon_path):
        return FileResponse(icon_path, media_type="image/png")
    return Response(status_code=404)

@router.api_route("/", methods=["GET", "HEAD"])
def serve_index(request: Request):

    # Return login.html directly to avoid 302 redirect on iOS PWA startup,
    # which breaks localStorage and cookie persistence.
    # login.html has its own client-side auto-redirect to saas_dashboard.html.
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))

@router.api_route("/trades", methods=["GET", "HEAD"])
@router.api_route("/trade-list", methods=["GET", "HEAD"])
@router.api_route("/trades.html", methods=["GET", "HEAD"])
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

@router.get("/login")
@router.get("/login.html")
def get_login(request: Request):

    # Return login.html directly. The client-side JS handles the auto-redirect 
    # to saas_dashboard.html if a valid token exists. This prevents 302 
    # redirects which break iOS PWA standalone storage.
    return FileResponse(os.path.join(STATIC_DIR, "login.html"))

@router.get("/saas_dashboard.html")
@router.get("/saas_dashboard")
def get_saas_dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "saas_dashboard.html"))

@router.get("/index.html")
@router.get("/admin")
@router.get("/dashboard")
def get_admin_dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@router.get("/admin/mobile")
def get_admin_mobile():
    return FileResponse(
        os.path.join(STATIC_DIR, "admin_mobile.html"),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )
