import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Main imports
from backend.auth.dependencies import (_get_guest_id, require_auth,
                                       require_owner)
from backend.guest_manager import (_load_registry, create_guest, delete_guest,
                                   list_guests)

router = APIRouter()

@router.post("/api/admin/guests/create", dependencies=[Depends(require_auth), Depends(require_owner)])
async def api_admin_guest_create(request: Request):
    """Create a new guest session. Returns the guest_id and shareable URL."""

    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse guest create request: {e}")
        body = {}
    label = body.get("label", "")
    guest = create_guest(label=label)
    # Build a shareable URL
    host = request.headers.get("host", "localhost:8056")
    scheme = "https" if "https" in str(request.url) else "http"
    guest["guest_url"] = f"{scheme}://{host}/?guest={guest['guest_id']}"
    return JSONResponse(guest)

@router.get("/api/admin/guests", dependencies=[Depends(require_auth), Depends(require_owner)])
def api_admin_guest_list():
    """List all guest sessions with balance and trade stats."""

    return JSONResponse({"guests": list_guests()})

@router.delete("/api/admin/guests/{guest_id}", dependencies=[Depends(require_auth), Depends(require_owner)])
def api_admin_guest_delete(guest_id: str):
    """Delete a guest and all their data."""

    success = delete_guest(guest_id)
    if not success:
        raise HTTPException(status_code=404, detail="Guest not found")
    return JSONResponse({"status": "deleted", "guest_id": guest_id})

@router.get("/api/guest/me")
def api_guest_me(request: Request):
    """Returns the current guest identity, or null if not a guest."""
    guest_id = _get_guest_id(request)
    if not guest_id:
        return JSONResponse({"is_guest": False})

    registry = _load_registry()
    meta = registry.get(guest_id, {})
    return JSONResponse({
        "is_guest": True,
        "guest_id": guest_id,
        "label": meta.get("label", ""),
    })
