import logging
import os
from typing import Optional

from fastapi import Header, HTTPException, Request

logger = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")

_LAN_PREFIXES = ("192.168.", "10.", "fe80:")
_LOOPBACK = ("127.0.0.1", "localhost", "::1", "testclient")


def _get_guest_id(request: Request) -> Optional[str]:
    gid = getattr(request.state, "guest_id", None)
    if gid:
        return gid
    if getattr(request.state, "is_owner", False) or caller_has_owner_access(request):
        return None
    uid = getattr(request.state, "user_id", None)
    if uid and not getattr(request.state, "is_owner", False):
        return str(uid)
    return None


def _is_local_client(request) -> bool:
    return False


def _extract_jwt(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization") or ""
    if auth_header.startswith("Bearer ") and len(auth_header) > 7:
        candidate = auth_header.split(" ", 1)[1].strip()
        if candidate and candidate not in ("null", "undefined", "None"):
            return candidate
    return request.cookies.get("saas_token") or None


def is_owner_request(request: Request, x_api_token: Optional[str] = None) -> bool:
    """Owner = on this PC / home network, or presenting the master API token."""
    from backend.auth.security import is_valid_master_token
    if _is_local_client(request):
        return True
    token = x_api_token or request.headers.get("X-API-Token")
    return is_valid_master_token(token)


def require_auth(
    request: Request,
    x_api_token: Optional[str] = Header(None, alias="X-API-Token")
):
    """Allow a valid SaaS login (JWT), a local/LAN client, or the master API token."""
    token = _extract_jwt(request)
    if token:
        try:
            from backend.auth.security import decode_jwt_token
            payload = decode_jwt_token(token)
            if payload:
                from backend.database.models import get_user_by_id, is_owner_account
                user = get_user_by_id(payload.get("user_id"))
                if user and not user.get("is_active", 1):
                    raise HTTPException(status_code=403, detail="This account has been disabled.")
                if user:
                    request.state.user_id = payload.get("user_id")
                    if is_owner_account(user) or user.get("role") == "admin":
                        request.state.is_owner = True
                    return
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Failed to decode SaaS JWT: {e}")

    if is_owner_request(request, x_api_token):
        request.state.is_owner = True
        return
    # Guest links (?guest=<token>) are validated by GuestMiddleware; they only
    # ever reach isolated PAPER guest executors.
    if _get_guest_id(request):
        return
    raise HTTPException(status_code=401, detail="Login required.")


def _user_is_admin(user_id) -> bool:
    if not user_id:
        return False
    try:
        from backend.database.models import get_user_by_id
        user = get_user_by_id(user_id)
    except Exception as e:
        logger.warning(f"Role lookup failed for user {user_id}: {e}")
        return False
    return bool(user) and user.get("role") == "admin" and bool(user.get("is_active", 1))


def caller_has_owner_access(request: Request) -> bool:
    """True for the owner (local/LAN/master token) or a logged-in admin account."""
    if getattr(request.state, "is_owner", False) or is_owner_request(request):
        return True
    return _user_is_admin(getattr(request.state, "user_id", None))


def require_owner(request: Request):
    """Owner-only operations (the main bot, guests, scalp engine).
    Must be listed after require_auth so request.state is populated."""
    if _get_guest_id(request):
        raise HTTPException(status_code=403, detail="This operation is not available in guest mode.")
    if caller_has_owner_access(request):
        return
    raise HTTPException(status_code=403, detail="Owner access required")


def require_bot_control(request: Request):
    """For /api/engine/* endpoints that act on the main (owner) bot when the
    caller is not a guest. Guests are routed to their own PAPER executor by the
    endpoint itself; everyone else needs owner/admin access. Must follow
    require_auth in the dependency list."""
    if _get_guest_id(request):
        return
    if caller_has_owner_access(request):
        return
    if getattr(request.state, "user_id", None):
        return
    raise HTTPException(status_code=403, detail="This control is only available to the account owner.")

