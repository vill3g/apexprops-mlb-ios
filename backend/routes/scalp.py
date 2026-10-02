import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Main imports
from backend.auth.dependencies import require_auth, require_owner
from backend.btc.scalp_engine import get_scalp_engine
from backend.core.registry import SUPPORTED_ASSETS
from backend.forex.auto_executor import ACTIVE_PAIRS


class ScalpConfigUpdate(BaseModel):
    max_risk_dollars: float = 50.0
    target_profit_dollars: float = 5.0
    max_open_positions: int = 2
    entry_confidence_threshold: float = 80.0
    tick_interval_ms: int = 500




def _validate_asset(request: Request):
    """Reject unknown /{asset} path values with 404 instead of a 500."""
    asset = str(request.path_params.get("asset", "") or "").upper().strip()
    if asset and asset not in SUPPORTED_ASSETS and asset not in ACTIVE_PAIRS:
        raise HTTPException(status_code=404, detail=f"Unknown asset '{asset}'")

router = APIRouter(dependencies=[Depends(_validate_asset)])

@router.post("/api/engine/{asset}/scalp/start", dependencies=[Depends(require_auth), Depends(require_owner)])
def api_btc_scalp_start(asset: str):
    """Start the scalp engine background monitor."""
    get_scalp_engine(asset).start()
    return JSONResponse({"status": "scalp engine started"})

@router.post("/api/engine/{asset}/scalp/stop", dependencies=[Depends(require_auth), Depends(require_owner)])
def api_btc_scalp_stop(asset: str):
    """Stop the scalp engine background monitor."""
    get_scalp_engine(asset).stop()
    return JSONResponse({"status": "scalp engine stopped"})

@router.get("/api/engine/{asset}/scalp/config", dependencies=[Depends(require_auth), Depends(require_owner)])
def api_btc_scalp_config(asset: str):
    """Get current scalp engine configuration."""
    return JSONResponse(get_scalp_engine(asset).load_config())

@router.get("/api/engine/{asset}/scalp/status", dependencies=[Depends(require_auth), Depends(require_owner)])
def api_btc_scalp_status(asset: str):
    """Get current scalp engine runtime status and monitored positions."""
    return JSONResponse(get_scalp_engine(asset).get_status())

@router.patch("/api/engine/{asset}/scalp/config", dependencies=[Depends(require_auth), Depends(require_owner)])
def api_btc_scalp_config_update(asset: str, config: ScalpConfigUpdate):
    """Update scalp engine configuration with validated input."""
    body = config.model_dump(exclude_none=True)
    if not body:
        raise HTTPException(status_code=400, detail="No valid configuration fields provided")
    get_scalp_engine(asset).save_config(body)
    return JSONResponse({"status": "config updated", "config": get_scalp_engine(asset).load_config()})
