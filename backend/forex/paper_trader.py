import json
import os
import threading
import logging
import uuid
from typing import List, Dict, Optional
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "forex_paper_state.json")
_lock = threading.RLock()

# Standard lot sizes
STANDARD_LOT = 100_000
MINI_LOT = 10_000
MICRO_LOT = 1_000

def _get_default_state() -> dict:
    return {
        "balance": 10000.0,
        "positions": [],
        "trade_history": []
    }

def _load_state() -> dict:
    with _lock:
        if not os.path.exists(STATE_PATH):
            return _get_default_state()
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load forex paper state: {e}")
            return _get_default_state()

def _save_state(state: dict):
    from backend.btc.io_utils import atomic_json_write
    with _lock:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        atomic_json_write(STATE_PATH, state)

def get_balance() -> float:
    return _load_state().get("balance", 10000.0)

def get_open_positions() -> List[dict]:
    state = _load_state()
    return state.get("positions", [])

def get_trade_history() -> List[dict]:
    return _load_state().get("trade_history", [])

def calculate_pip_value(pair: str, size_units: int, current_rate: float) -> float:
    """
    Calculate pip value in USD.
    For EUR/USD, GBP/USD, AUD/USD, 1 pip = 0.0001
    Value = (0.0001 / 1) * size_units = 0.0001 * 10,000 = $1 per mini lot.
    For USD/JPY, 1 pip = 0.01.
    Value = (0.01 / current_rate) * size_units
    """
    if pair.endswith("USD"):
        # Quote is USD, pip value is fixed
        return size_units * 0.0001
    elif pair.startswith("USD"):
        # Base is USD (e.g. USDJPY)
        pip_decimal = 0.01 if "JPY" in pair else 0.0001
        return (pip_decimal / current_rate) * size_units
    return 0.0 # Simplify for now (no cross pairs)

def open_position(pair: str, side: str, size_units: int, current_price: float, sl: float = None, tp: float = None) -> dict:
    with _lock:
        state = _load_state()
        
        pos_id = str(uuid.uuid4())[:8]
        # Simulate spread
        spread = 0.0002 if "JPY" not in pair else 0.02
        entry_price = current_price + (spread/2) if side == "BUY" else current_price - (spread/2)
        
        position = {
            "id": pos_id,
            "pair": pair,
            "side": side,
            "size": size_units,
            "entry_price": entry_price,
            "sl": sl,
            "tp": tp,
            "status": "OPEN",
            "opened_at": datetime.now(pytz.utc).isoformat(),
            "unrealized_pnl": 0.0
        }
        
        state.setdefault("positions", []).append(position)
        _save_state(state)
        logger.info(f"Opened FOREX Position {pos_id}: {side} {size_units} {pair} @ {entry_price}")
        return position

def close_position(pos_id: str, current_price: float, reason: str = "MANUAL") -> Optional[dict]:
    with _lock:
        state = _load_state()
        positions = state.get("positions", [])
        
        for idx, pos in enumerate(positions):
            if pos["id"] == pos_id:
                # Calculate PnL
                size = pos["size"]
                entry = pos["entry_price"]
                pair = pos["pair"]
                
                pip_decimal = 0.01 if "JPY" in pair else 0.0001
                
                if pos["side"] == "BUY":
                    pips_gained = (current_price - entry) / pip_decimal
                else:
                    pips_gained = (entry - current_price) / pip_decimal
                    
                pip_value = calculate_pip_value(pair, size, current_price)
                realized_pnl = round(pips_gained * (pip_value / pip_decimal) * pip_decimal, 2)
                
                state["balance"] = round(state.get("balance", 10000.0) + realized_pnl, 2)
                
                pos["close_price"] = current_price
                pos["realized_pnl"] = realized_pnl
                pos["status"] = "CLOSED"
                pos["closed_at"] = datetime.now(pytz.utc).isoformat()
                pos["close_reason"] = reason
                
                # Move to history
                positions.pop(idx)
                state.setdefault("trade_history", []).insert(0, pos)
                # Keep history short
                state["trade_history"] = state["trade_history"][:50]
                
                _save_state(state)
                logger.info(f"Closed FOREX Position {pos_id} [{reason}] PNL: ${realized_pnl}")
                return pos
                
        return None

def evaluate_stops_and_limits(pair: str, current_price: float):
    """Called every tick/cycle to check SL and TP."""
    with _lock:
        state = _load_state()
        positions = state.get("positions", [])
        modified = False
        
        to_close = []
        for pos in positions:
            if pos["pair"] != pair:
                continue
                
            sl = pos.get("sl")
            tp = pos.get("tp")
            side = pos["side"]
            
            if side == "BUY":
                if sl and current_price <= sl:
                    to_close.append((pos["id"], "STOP_LOSS"))
                elif tp and current_price >= tp:
                    to_close.append((pos["id"], "TAKE_PROFIT"))
            else: # SELL
                if sl and current_price >= sl:
                    to_close.append((pos["id"], "STOP_LOSS"))
                elif tp and current_price <= tp:
                    to_close.append((pos["id"], "TAKE_PROFIT"))
                    
        if to_close:
            for pos_id, reason in to_close:
                close_position(pos_id, current_price, reason)

