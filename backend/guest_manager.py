"""
Guest Manager for Kalshi AI Trader
Handles creation, validation, listing, and deletion of guest sessions.
Each guest gets an isolated paper trading sandbox with their own balance,
trades history, and trading config.
"""

import os
import json
import uuid
import shutil
import logging
import threading
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
GUESTS_DIR = os.path.join(DATA_DIR, "guests")
GUESTS_REGISTRY = os.path.join(GUESTS_DIR, "_registry.json")

_lock = threading.Lock()

DEFAULT_GUEST_BALANCE = 1000.0
DEFAULT_GUEST_CONFIG = {
    "enabled": False,
    "mode": "PAPER",
    "min_conviction": "GRADE A SETUP",
    "max_contracts": 10,
    "prediction_mode": False,
    "max_daily_risk": 500.0,
    "max_daily_trades": 50,
    "ai_settings": {
        "modelChoice": "Swarm",
        "trainWindow": 4000,
        "regC": 0.7,
        "classWeight": "balanced",
        "maxCap": 10,
        "minConf": 65,
        "minConviction": "A",
        "edgeWeightOn": True,
        "edgeWeightFactor": 1.1,
        "orderType": "market",
        "execDelay": 1,
        "pollInterval": 5,
        "verboseLog": False,
        "dryRun": True,
        "ignorePass": True,
        "ignorePassTechnicalOnly": False,
        "tradingStyle": "CHOP",
        "oneShotAiStartTrade": False,
        "xgbEstimators": 150,
        "xgbMaxDepth": 5,
        "xgbLearningRate": 0.05,
        "signalIsolation": "BLEND",
        "stopLossMoveDollars": 15,
        "stopLossMaxMinutes": 13,
        "takeProfitEnabled": True,
        "takeProfitPercent": 50,
        "useFinbertNLP": True,
        "dynamicStopLoss": True,
        "positionReversal": False,
        "slippageBufferDollars": 0.04
    }
}


def _load_registry() -> Dict:
    """Load the guest registry from disk."""
    if os.path.exists(GUESTS_REGISTRY):
        try:
            with open(GUESTS_REGISTRY, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_registry(registry: Dict):
    """Save the guest registry to disk."""
    os.makedirs(GUESTS_DIR, exist_ok=True)
    with open(GUESTS_REGISTRY, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)


def get_guest_data_dir(guest_id: str) -> str:
    """Return the data directory for a specific guest or SaaS user."""
    # If the guest_id is purely digits, it's a SaaS user from the SQLite database
    if str(guest_id).isdigit():
        return os.path.join(DATA_DIR, "users", str(guest_id))
    # Otherwise it's a transient UUID guest
    return os.path.join(GUESTS_DIR, guest_id)


def is_valid_guest(guest_id: str) -> bool:
    """Check if a guest ID is valid and exists."""
    if not guest_id or not isinstance(guest_id, str):
        return False
    # Sanitize: only allow alphanumeric + hyphens
    if not all(c.isalnum() or c == '-' for c in guest_id):
        return False
    with _lock:
        registry = _load_registry()
        return guest_id in registry


def create_guest(label: str = "") -> Dict:
    """Create a new guest session with isolated data directory."""
    guest_id = uuid.uuid4().hex[:12]
    guest_dir = get_guest_data_dir(guest_id)

    with _lock:
        os.makedirs(guest_dir, exist_ok=True)

        # Initialize paper balance
        with open(os.path.join(guest_dir, "paper_balance.json"), "w", encoding="utf-8") as f:
            json.dump({"balance": DEFAULT_GUEST_BALANCE}, f, indent=2)

        # Initialize empty trades history
        with open(os.path.join(guest_dir, "trades_history.json"), "w", encoding="utf-8") as f:
            json.dump([], f)

        # Initialize trading config
        with open(os.path.join(guest_dir, "trading_config.json"), "w", encoding="utf-8") as f:
            json.dump(DEFAULT_GUEST_CONFIG, f, indent=2)

        # Update registry
        registry = _load_registry()
        registry[guest_id] = {
            "label": label or f"Guest {len(registry) + 1}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "starting_balance": DEFAULT_GUEST_BALANCE,
        }
        _save_registry(registry)

    logger.info(f"[GuestManager] Created guest '{registry[guest_id]['label']}' (ID: {guest_id})")
    return {
        "guest_id": guest_id,
        "label": registry[guest_id]["label"],
        "created_at": registry[guest_id]["created_at"],
        "starting_balance": DEFAULT_GUEST_BALANCE,
    }


def list_guests() -> List[Dict]:
    """List all guests with their current balance and trade count."""
    with _lock:
        registry = _load_registry()

    guests = []
    for guest_id, meta in registry.items():
        guest_dir = get_guest_data_dir(guest_id)
        balance = DEFAULT_GUEST_BALANCE
        trade_count = 0

        try:
            bal_path = os.path.join(guest_dir, "paper_balance.json")
            if os.path.exists(bal_path):
                with open(bal_path, "r", encoding="utf-8") as f:
                    balance = json.load(f).get("balance", DEFAULT_GUEST_BALANCE)
        except Exception:
            pass

        try:
            hist_path = os.path.join(guest_dir, "trades_history.json")
            if os.path.exists(hist_path):
                with open(hist_path, "r", encoding="utf-8") as f:
                    trade_count = len(json.load(f))
        except Exception:
            pass

        guests.append({
            "guest_id": guest_id,
            "label": meta.get("label", ""),
            "created_at": meta.get("created_at", ""),
            "balance": balance,
            "pnl": round(balance - meta.get("starting_balance", DEFAULT_GUEST_BALANCE), 2),
            "trade_count": trade_count,
        })

    return guests


def delete_guest(guest_id: str) -> bool:
    """Delete a guest and all their data."""
    if not is_valid_guest(guest_id):
        return False

    guest_dir = get_guest_data_dir(guest_id)

    with _lock:
        # Remove from registry
        registry = _load_registry()
        label = registry.pop(guest_id, {}).get("label", guest_id)
        _save_registry(registry)

        # Remove data directory
        if os.path.exists(guest_dir):
            shutil.rmtree(guest_dir, ignore_errors=True)

    # Evict any cached executor for this guest
    try:
        from backend.btc.auto_executor import _evict_guest_executor
        _evict_guest_executor(guest_id)
    except Exception:
        pass

    logger.info(f"[GuestManager] Deleted guest '{label}' (ID: {guest_id})")
    return True
