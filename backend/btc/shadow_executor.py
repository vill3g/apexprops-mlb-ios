import os
import json
import logging
import time
from typing import Dict, Any

from backend.btc.rl_agent import get_rl_agent
from backend.btc.ml_engine import FEATURE_KEYS, NEUTRAL_FEATURE_DEFAULTS

logger = logging.getLogger(__name__)

# Cache shadow trades file
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SHADOW_TRADES_FILE = os.path.join(DATA_DIR, "rl_shadow_trades.json")

def _build_state_vector(raw_features: dict) -> list:
    vec = []
    for k in FEATURE_KEYS:
        default_val = NEUTRAL_FEATURE_DEFAULTS.get(k, 0.0)
        val = raw_features.get(k, default_val)
        try:
            val = float(val)
        except (ValueError, TypeError):
            val = default_val
        vec.append(val)
    return vec

def execute_shadow_trade(forecast: Dict[str, Any], kalshi_market: dict = None):
    """
    Called by auto_executor right after evaluate_next_15m_contract.
    Observes the market state and decides if RL agent wants to take a shadow trade.
    """
    try:
        raw_features = forecast.get("raw_features", {})
        if not raw_features:
            return

        state = _build_state_vector(raw_features)
        if len(state) != 60:
            logger.error(f"[ShadowExecutor] State dim mismatch: got {len(state)}, expected 60")
            return

        rl_agent = get_rl_agent()
        action = rl_agent.select_action(state)

        # 0: PASS, 1: BUY YES (ABOVE), 2: BUY NO (BELOW)
        if action == 0:
            return # PASS, do nothing

        direction = "ABOVE" if action == 1 else "BELOW"
        strike = kalshi_market.get("strike_price", 0.0) if kalshi_market else 0.0
        ticker = kalshi_market.get("ticker", "UNKNOWN") if kalshi_market else "UNKNOWN"
        close_time = kalshi_market.get("close_time", "") if kalshi_market else ""

        # Use Kalshi prices if available
        entry_price = kalshi_market.get("yes_ask", 50) / 100.0 if action == 1 else kalshi_market.get("no_ask", 50) / 100.0

        shadow_trade = {
            "id": f"shadow_{int(time.time())}",
            "ticker": ticker,
            "strike": strike,
            "direction": direction,
            "entry_price": entry_price,
            "entry_time": time.time(),
            "close_time": close_time,
            "status": "OPEN",
            "pnl": 0.0,
            "rl_epsilon": round(rl_agent.epsilon, 3),
            "state_vector": state, # Save for RL memory replay later
            "action": action
        }

        # Write to rl_shadow_trades.json
        trades = []
        if os.path.exists(SHADOW_TRADES_FILE):
            with open(SHADOW_TRADES_FILE, 'r') as f:
                try:
                    trades = json.load(f)
                except json.JSONDecodeError:
                    trades = []


        # Check for duplicates
        is_dup = False
        for t in trades:
            if t.get("ticker") == ticker and t.get("status") == "OPEN":
                is_dup = True
                break
        
        if is_dup:
            return
            
        trades.append(shadow_trade)


        # Keep last 500
        if len(trades) > 500:
            trades = trades[-500:]

        with open(SHADOW_TRADES_FILE, 'w') as f:
            json.dump(trades, f, indent=2)

        logger.info(f"[ShadowExecutor] RL Agent placed shadow trade: {direction} on {ticker} @ {entry_price}")

    except Exception as e:
        logger.error(f"[ShadowExecutor] Error in shadow loop: {e}")

def update_shadow_settlements(kalshi_trader):
    """
    Called by auto_executor.check_settlements().
    Checks Kalshi for resolution of OPEN shadow trades and calculates reward.
    """
    try:
        if not os.path.exists(SHADOW_TRADES_FILE):
            return

        with open(SHADOW_TRADES_FILE, 'r') as f:
            trades = json.load(f)

        updated = False
        rl_agent = get_rl_agent()

        for t in trades:
            if t.get("status") == "OPEN":
                # Check Kalshi API for settlement
                ticker = t.get("ticker")
                res = kalshi_trader.get_market_result(ticker)
                
                # If market is closed/settled
                if res and str(res.get("status", "")).upper() in ["SETTLED", "CLOSED"]:
                    official_result = str(res.get("result", "")).upper() # 'YES' or 'NO'
                    
                    if not official_result:
                        continue

                    # Calculate PNL
                    is_yes_win = (official_result == "YES")
                    trade_dir = t.get("direction")
                    is_win = (is_yes_win and trade_dir == "ABOVE") or (not is_yes_win and trade_dir == "BELOW")
                    
                    entry = float(t.get("entry_price", 0.5))
                    pnl = (1.0 - entry) if is_win else -entry

                    t["status"] = "SETTLED"
                    t["official_result"] = official_result
                    t["pnl"] = round(pnl, 4)
                    updated = True

                    # Train RL Agent (Push to memory and step)
                    state = t.get("state_vector")
                    action = t.get("action")
                    if state is not None and action is not None:
                        reward = pnl * 10.0 # Scale reward for DQN
                        next_state = state # Terminal state approximation
                        rl_agent.memory.push(state, action, reward, next_state, done=True)
                        rl_agent.train_step()

        if updated:
            with open(SHADOW_TRADES_FILE, 'w') as f:
                json.dump(trades, f, indent=2)
            rl_agent.save()
            logger.info("[ShadowExecutor] Updated RL shadow settlements and trained DQN.")

    except Exception as e:
        logger.error(f"[ShadowExecutor] Error in shadow settlement loop: {e}")
