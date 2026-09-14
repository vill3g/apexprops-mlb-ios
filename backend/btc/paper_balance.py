import json
import os
import threading
from backend.btc.io_utils import atomic_json_write

_lock = threading.RLock()
BALANCE_PATH = os.path.join(os.path.dirname(__file__), "paper_balance.json")
_cached_balance: float = 500.0
_cached_balance_mtime: float = 0.0

def load_balance() -> float:
    global _cached_balance, _cached_balance_mtime
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
        except Exception:
            return _cached_balance

def update_balance(delta: float) -> float:
    global _cached_balance, _cached_balance_mtime
    with _lock:
        current = load_balance()
        new_balance = round(current + delta, 4)
        atomic_json_write(BALANCE_PATH, {"balance": new_balance})
        _cached_balance = new_balance
        _cached_balance_mtime = os.path.getmtime(BALANCE_PATH)
        return new_balance

def reset_balance() -> float:
    global _cached_balance, _cached_balance_mtime
    with _lock:
        atomic_json_write(BALANCE_PATH, {"balance": 500.0})
        _cached_balance = 500.0
        _cached_balance_mtime = os.path.getmtime(BALANCE_PATH)
        return 500.0
