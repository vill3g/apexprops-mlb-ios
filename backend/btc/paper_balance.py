import json
import os
import threading
import logging

logger = logging.getLogger(__name__)

from backend.btc.io_utils import atomic_json_write

_lock = threading.RLock()
BALANCE_PATH = os.path.join(os.path.dirname(__file__), "paper_balance.json")
_cached_balance: float = 500.0
_cached_balance_mtime: float = 0.0

# Guest balance caches: {guest_id: (balance, mtime)}
_guest_caches: dict = {}


def _get_guest_balance_path(guest_id: str) -> str:
    """Return the paper_balance.json path for a guest."""
    from backend.guest_manager import get_guest_data_dir
    return os.path.join(get_guest_data_dir(guest_id), "paper_balance.json")


def load_balance(guest_id: str = None) -> float:
    global _cached_balance, _cached_balance_mtime
    if guest_id:
        return _load_guest_balance(guest_id)
    with _lock:
        if not os.path.exists(BALANCE_PATH):
            return 500.0
        try:
            mtime = os.path.getmtime(BALANCE_PATH)
            if _cached_balance_mtime == mtime:
                return _cached_balance
            with open(BALANCE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                _cached_balance = float(data.get("balance", 500.0))
                _cached_balance_mtime = mtime
                return _cached_balance
        except Exception as e:
            logger.error(f"Failed to load paper balance: {e}")
            return _cached_balance


def _load_guest_balance(guest_id: str) -> float:
    path = _get_guest_balance_path(guest_id)
    with _lock:
        if not os.path.exists(path):
            return 1000.0
        try:
            mtime = os.path.getmtime(path)
            cached = _guest_caches.get(guest_id)
            if cached and cached[1] == mtime:
                return cached[0]
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                bal = float(data.get("balance", 1000.0))
                _guest_caches[guest_id] = (bal, mtime)
                return bal
        except Exception as e:
            logger.error(f"Failed to load guest balance for {guest_id}: {e}")
            cached = _guest_caches.get(guest_id)
            return cached[0] if cached else 1000.0


def update_balance(delta: float, guest_id: str = None) -> float:
    global _cached_balance, _cached_balance_mtime
    if guest_id:
        return _update_guest_balance(delta, guest_id)
    with _lock:
        current = load_balance()
        new_balance = round(current + delta, 4)
        atomic_json_write(BALANCE_PATH, {"balance": new_balance})
        _cached_balance = new_balance
        _cached_balance_mtime = os.path.getmtime(BALANCE_PATH)
        return new_balance


def _update_guest_balance(delta: float, guest_id: str) -> float:
    path = _get_guest_balance_path(guest_id)
    with _lock:
        current = _load_guest_balance(guest_id)
        new_balance = round(current + delta, 4)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        atomic_json_write(path, {"balance": new_balance})
        _guest_caches[guest_id] = (new_balance, os.path.getmtime(path))
        return new_balance


def reset_balance(guest_id: str = None) -> float:
    global _cached_balance, _cached_balance_mtime
    if guest_id:
        return _reset_guest_balance(guest_id)
    with _lock:
        atomic_json_write(BALANCE_PATH, {"balance": 500.0})
        _cached_balance = 500.0
        _cached_balance_mtime = os.path.getmtime(BALANCE_PATH)
        return 500.0


def _reset_guest_balance(guest_id: str) -> float:
    path = _get_guest_balance_path(guest_id)
    with _lock:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        atomic_json_write(path, {"balance": 1000.0})
        _guest_caches[guest_id] = (1000.0, os.path.getmtime(path))
        return 1000.0
