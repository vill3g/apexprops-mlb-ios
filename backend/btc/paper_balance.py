import json
import os
import threading

_lock = threading.Lock()
BALANCE_PATH = os.path.join(os.path.dirname(__file__), "paper_balance.json")

def load_balance() -> float:
    if not os.path.exists(BALANCE_PATH):
        return 500.0
    try:
        with _lock:
            with open(BALANCE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("balance", 500.0)
    except Exception:
        return 500.0

def update_balance(delta: float) -> float:
    with _lock:
        try:
            if os.path.exists(BALANCE_PATH):
                with open(BALANCE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    balance = data.get("balance", 500.0)
            else:
                balance = 500.0
        except Exception:
            balance = 500.0
            
        new_balance = balance + delta
        with open(BALANCE_PATH, "w", encoding="utf-8") as f:
            json.dump({"balance": new_balance}, f, indent=2)
        return new_balance

def reset_balance() -> float:
    with _lock:
        with open(BALANCE_PATH, "w", encoding="utf-8") as f:
            json.dump({"balance": 500.0}, f, indent=2)
        return 500.0
