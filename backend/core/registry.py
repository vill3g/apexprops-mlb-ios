import os
import threading
from typing import Any, Dict, Optional

_executors: Dict[str, Any] = {}
_guest_executors: Dict[str, Any] = {}
SUPPORTED_ASSETS = {"BTC", "ETH", "GOLD", "NDQ"}

def get_auto_executor(asset: str = "BTC", guest_id: Optional[str] = None) -> Any:
    """Return a singleton AutoExecutor for the given asset.
    When guest_id is provided, returns a guest-specific executor with
    isolated data paths and PAPER-only mode.
    """
    from backend.btc.auto_executor import AutoExecutor

    # Normalize: "/api/engine/btc/..." used to create a second, independent BTC
    # executor (with its own config file). Unknown assets are rejected instead of
    # creating a new executor (and config file) for any string in the URL.
    asset = str(asset or "BTC").upper().strip()
    if asset not in SUPPORTED_ASSETS:
        raise ValueError(f"Unsupported asset '{asset}'")

    if not guest_id:
        if asset not in _executors:
            _executors[asset] = AutoExecutor(asset)
        return _executors[asset]

    key = f"GUEST:{guest_id}:{asset}"
    if key not in _guest_executors:
        from backend.guest_manager import get_guest_data_dir
        guest_dir = get_guest_data_dir(guest_id)
        os.makedirs(guest_dir, exist_ok=True)
        executor = AutoExecutor.__new__(AutoExecutor)
        # Manually initialize to avoid connecting to shared SQLite trade_db
        executor.asset = asset
        executor.enabled = False
        executor.mode = "PAPER"
        executor.min_conviction = "GRADE A SETUP"
        executor.max_contracts = 10
        executor.prediction_mode = False
        executor.max_daily_risk = 500.0
        executor.max_daily_trades = 50
        executor.last_traded_interval = None
        executor.last_check_time = 0.0
        executor.ai_settings = {}
        executor._rollover_lock = threading.Lock()
        executor._cached_trades = []
        executor._cached_trades_mtime = 0.0
        executor._settled_since_drift_check = 0
        
        # Guest-specific paths
        executor._config_file = os.path.join(guest_dir, "trading_config.json")
        executor._history_file = os.path.join(guest_dir, "trades_history.json")
        executor._is_guest = True
        executor._guest_id = guest_id
        
        # Disable shared SQLite DB for guests
        executor.trade_db = None
        
        # Load guest or user config
        executor._load_config()
        
        _guest_executors[key] = executor
        
    return _guest_executors[key]

def _evict_guest_executor(guest_id: str):
    keys_to_remove = [k for k in _guest_executors.keys() if k.startswith(f"GUEST:{guest_id}:")]
    for k in keys_to_remove:
        del _guest_executors[k]
