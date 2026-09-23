import os
import json
import logging
import time
import threading
from typing import Dict, Any

from backend.btc.rl_agent import get_rl_agent
from backend.btc.ml_engine import FEATURE_KEYS, NEUTRAL_FEATURE_DEFAULTS

logger = logging.getLogger(__name__)

# Cache shadow trades file
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SHADOW_TRADES_FILE = os.path.join(DATA_DIR, "rl_shadow_trades.json")

_shadow_file_lock = threading.Lock()

def _build_state_vector(raw_features: dict) -> list:
    vec = []
    for k in FEATURE_KEYS:
        default_val = NEUTRAL_FEATURE_DEFAULTS.get(k, 0.0)
        val = raw_features.get(k, default_val)
        try:
            val = float(val)
            import math
            if not math.isfinite(val):
                val = default_val
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
        if len(state) != len(FEATURE_KEYS):
            logger.error(f"[ShadowExecutor] State dim mismatch: got {len(state)}, expected {len(FEATURE_KEYS)}")
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
        entry_price = kalshi_market.get("yes_ask", 0.50) if action == 1 else kalshi_market.get("no_ask", 0.50)

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
        with _shadow_file_lock:
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
            
            if not is_dup:
                trades.append(shadow_trade)

                # Keep last 500
                if len(trades) > 500:
                    trades = trades[-500:]

                with open(SHADOW_TRADES_FILE, 'w') as f:
                    json.dump(trades, f, indent=2)

        if not is_dup:
            logger.info(f"[ShadowExecutor] RL Agent placed shadow trade: {direction} on {ticker} @ {entry_price}")

    except Exception as e:
        logger.error(f"[ShadowExecutor] Error in shadow loop: {e}")

def update_shadow_settlements(kalshi_trader, official_results=None):
    """
    Called by auto_executor.check_settlements().
    Checks Kalshi for resolution of OPEN shadow trades and calculates reward.
    """
    try:
        with _shadow_file_lock:
            if not os.path.exists(SHADOW_TRADES_FILE):
                return
            with open(SHADOW_TRADES_FILE, 'r') as f:
                trades = json.load(f)

        updated = False
        rl_agent = get_rl_agent()
        
        if official_results is None:
            official_results = {}
            
        api_calls_this_cycle = 0

        for t in trades:
            if t.get("status") == "OPEN":
                ticker = t.get("ticker")
                
                # Fast fail: Don't check Kalshi if the contract hasn't even expired yet.
                close_time_str = t.get("close_time", "")
                if close_time_str:
                    try:
                        from datetime import datetime
                        close_epoch = datetime.fromisoformat(close_time_str.replace("Z", "+00:00")).timestamp()
                        if time.time() < close_epoch + 15:  # Give it 15s grace period
                            continue
                    except (TypeError, ValueError):
                        pass

                # Rate Limit Fix: Prevent Kalshi HTTP 429
                if ticker not in official_results:
                    if api_calls_this_cycle >= 1:
                        continue  # Only do 1 fetch per cycle to slowly drain the backlog
                    official_results[ticker] = kalshi_trader.get_market_result(ticker)
                    api_calls_this_cycle += 1

                res = official_results[ticker]
                
                # If market is closed/settled
                if res and str(res.get("status", "")).upper() in ["SETTLED", "CLOSED", "FINALIZED"]:
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
                        
                        # CHOP PENALTY:
                        # Dynamically find vol_regime_percentile in FEATURE_KEYS.
                        # If volatility is in the bottom 25th percentile, lightly penalize trading.
                        try:
                            vol_idx = FEATURE_KEYS.index("vol_regime_percentile")
                            if len(state) > vol_idx and state[vol_idx] < 25.0:
                                reward -= 0.5  # Fixed penalty for trading in chop
                        except (ValueError, IndexError):
                            pass
                                
                        next_state = state # Terminal state approximation
                        rl_agent.memory.push(state, action, reward, next_state, done=True)
                        rl_agent.train_step()

        if updated:
            with _shadow_file_lock:
                with open(SHADOW_TRADES_FILE, 'w') as f:
                    json.dump(trades, f, indent=2)
            rl_agent.save()
            logger.info("[ShadowExecutor] Updated RL shadow settlements and trained DQN.")

    except Exception as e:
        logger.error(f"[ShadowExecutor] Error in shadow settlement loop: {e}")
