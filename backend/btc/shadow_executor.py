import json
import logging
import os
import time
import uuid
from typing import Any, Dict

from backend.btc.ml_engine import (FEATURE_KEYS, NEUTRAL_FEATURE_DEFAULTS,
                                   normalize_features)
from backend.btc.rl_agent import get_rl_agent

logger = logging.getLogger(__name__)

# Cache shadow trades file
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SHADOW_TRADES_FILE = os.path.join(DATA_DIR, "rl_shadow_trades.json")

from backend.btc.io_utils import atomic_json_write
from backend.database.models import CrossProcessLock

# Shared by the web server and the worker process (both run the auto-executor hooks)
_shadow_file_lock = CrossProcessLock("rl_shadow_trades")

RL_DEFAULT_TRADE_SIZE_DOLLARS = 100.0

# Version 2 = state built from forecast["ml_features"] (build_live_ml_features), i.e. the
# exact vector the live RL signal sees. Version 1 records used the analyzer's ledger dict,
# which differs (current-candle shape, 3-day "24h" window, missing keys) and is no longer
# used for training.
SHADOW_FEATURE_VERSION = 2

def get_rl_trade_size() -> float:
    try:
        val = os.environ.get("RL_TRADE_SIZE_DOLLARS")
        if val is not None:
            return float(val)
    except (ValueError, TypeError):
        pass
    return RL_DEFAULT_TRADE_SIZE_DOLLARS

def _build_state_vector(raw_features: dict) -> list:
    norm_features = normalize_features(raw_features) if raw_features else {}
    vec = []
    for k in FEATURE_KEYS:
        default_val = NEUTRAL_FEATURE_DEFAULTS.get(k, 0.0)
        val = norm_features.get(k, default_val)
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
        raw_features = forecast.get("ml_features")
        if not raw_features:
            logger.debug("[ShadowExecutor] No live ml_features on forecast; skipping shadow trade.")
            return

        state = _build_state_vector(raw_features)
        if len(state) != len(FEATURE_KEYS):
            logger.error(f"[ShadowExecutor] State dim mismatch: got {len(state)}, expected {len(FEATURE_KEYS)}")
            return

        rl_agent = get_rl_agent()
        action = rl_agent.select_action(state)
        # What the live, price-aware policy would have done on this exact state
        try:
            live_eval = rl_agent.evaluate_contract(state, kalshi_market)
        except Exception as ee:
            logger.debug(f"[ShadowExecutor] evaluate_contract failed: {ee}")
            live_eval = {}

        # 0: PASS, 1: BUY YES (ABOVE), 2: BUY NO (BELOW)
        if action == 0:
            return # PASS, do nothing

        direction = "ABOVE" if action == 1 else "BELOW"
        strike = kalshi_market.get("strike_price", 0.0) if kalshi_market else 0.0
        ticker = kalshi_market.get("ticker", "UNKNOWN") if kalshi_market else "UNKNOWN"
        close_time = kalshi_market.get("close_time", "") if kalshi_market else ""

        # Use Kalshi prices if available
        raw_entry = kalshi_market.get("yes_ask", 0.50) if action == 1 else kalshi_market.get("no_ask", 0.50)
        try:
            entry_price = float(raw_entry)
            if entry_price <= 0.0 or entry_price >= 1.0:
                entry_price = 0.50
        except (ValueError, TypeError):
            entry_price = 0.50

        trade_size = get_rl_trade_size()
        contracts = max(1, int(trade_size / entry_price))
        cost = round(contracts * entry_price, 2)

        shadow_trade = {
            "id": f"shadow_{uuid.uuid4().hex[:12]}",
            "ticker": ticker,
            "strike": strike,
            "direction": direction,
            "trade_size": trade_size,
            "contracts": contracts,
            "cost": cost,
            "entry_price": entry_price,
            "entry_time": time.time(),
            "close_time": close_time,
            "status": "OPEN",
            "pnl": 0.0,
            "rl_epsilon": round(rl_agent.epsilon, 3),
            "state_vector": state, # Save for RL memory replay later
            "action": action,
            "feature_version": SHADOW_FEATURE_VERSION,
            # Market prices at decision time (the network input still carries a neutral
            # kalshi_yes_prob; these let a future retrain learn from real prices)
            "yes_bid": kalshi_market.get("yes_bid") if kalshi_market else None,
            "yes_ask": kalshi_market.get("yes_ask") if kalshi_market else None,
            "no_bid": kalshi_market.get("no_bid") if kalshi_market else None,
            "no_ask": kalshi_market.get("no_ask") if kalshi_market else None,
            "calibrated_p_yes": live_eval.get("p_yes"),  # market-anchored
            "model_p_yes": live_eval.get("p_model"),  # calibrated model alone
            "edge_yes": live_eval.get("edge_yes"),
            "edge_no": live_eval.get("edge_no"),
            "live_policy_action": live_eval.get("action"),
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

                atomic_json_write(SHADOW_TRADES_FILE, trades, indent=2)

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
                ticker = str(t.get("ticker", "")).strip()
                
                # Synthetic or invalid ticker handling
                if not ticker or ticker.endswith("_SYNTH"):
                    t["status"] = "CANCELLED"
                    updated = True
                    continue

                # Fast fail: Don't check Kalshi if the contract hasn't even expired yet.
                close_time_str = t.get("close_time", "")
                close_epoch = None
                if close_time_str:
                    try:
                        from datetime import datetime
                        close_epoch = datetime.fromisoformat(close_time_str.replace("Z", "+00:00")).timestamp()
                        if time.time() < close_epoch + 15:  # Give it 15s grace period
                            continue
                    except (TypeError, ValueError):
                        pass
                else:
                    # If there's no close time and it's older than 1 hour, cancel it
                    if time.time() - float(t.get("entry_time", 0)) > 3600:
                        t["status"] = "CANCELLED"
                        updated = True
                        continue

                # Rate Limit Fix: Prevent Kalshi HTTP 429 while draining backlog
                if ticker not in official_results:
                    if api_calls_this_cycle >= 8:
                        continue  # Batch 8 fetches per cycle to safely and quickly drain backlog
                    official_results[ticker] = kalshi_trader.get_market_result(ticker)
                    api_calls_this_cycle += 1

                res = official_results[ticker]
                
                # If market not found or failed, and contract closed > 2 hours ago, mark expired
                if (not res or not res.get("success")) and close_epoch and (time.time() > close_epoch + 7200):
                    t["status"] = "EXPIRED"
                    updated = True
                    continue

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
                    trade_sz = float(t.get("trade_size", get_rl_trade_size()))
                    contracts = int(t.get("contracts", max(1, int(trade_sz / entry))))
                    cost = round(contracts * entry, 2)

                    unit_pnl = (1.0 - entry) if is_win else -entry
                    dollar_pnl = round(unit_pnl * contracts, 2)

                    t["status"] = "SETTLED"
                    t["official_result"] = official_result
                    t["trade_size"] = trade_sz
                    t["contracts"] = contracts
                    t["cost"] = cost
                    t["unit_pnl"] = round(unit_pnl, 4)
                    t["pnl"] = dollar_pnl
                    updated = True

                    # Train RL Agent (Push to memory and step)
                    state = t.get("state_vector")
                    action = t.get("action")
                    if int(t.get("feature_version", 1) or 1) < SHADOW_FEATURE_VERSION:
                        state = None  # legacy feature layout: settle for stats, don't train on it
                    if state is not None and action is not None:
                        # Asymmetric Reward Shaping: Punish false positives to enforce conservative trading
                        if unit_pnl < 0:
                            reward = (unit_pnl * 2.0) * 1.5  # Asymmetric penalty for losses
                        else:
                            reward = unit_pnl * 2.0
                        
                        # CHOP PENALTY:
                        # Dynamically find vol_regime_percentile in FEATURE_KEYS.
                        # If volatility is in the bottom 25th percentile (< 0.25), penalize trading in chop.
                        try:
                            vol_idx = FEATURE_KEYS.index("vol_regime_percentile")
                            if len(state) > vol_idx and state[vol_idx] < 0.25:
                                reward -= 0.5  # Fixed penalty for trading in chop
                        except (ValueError, IndexError):
                            pass
                        
                        # Clip reward to prevent extreme outliers from destabilizing training
                        reward = max(-3.0, min(3.0, reward))
                                
                        next_state = state # Terminal state approximation
                        rl_agent.memory.push(state, action, reward, next_state, done=True)
                        import threading
                        threading.Thread(target=rl_agent.train_step, daemon=True).start()

        if updated:
            with _shadow_file_lock:
                # Re-read latest file state to merge with any new trades added since our read
                fresh_trades = []
                if os.path.exists(SHADOW_TRADES_FILE):
                    try:
                        with open(SHADOW_TRADES_FILE, 'r') as f:
                            fresh_trades = json.load(f)
                    except json.JSONDecodeError:
                        fresh_trades = []
                
                # Build a map of our settled trade updates by id
                settled_map = {t["id"]: t for t in trades if t.get("status") in ("SETTLED", "EXPIRED", "CANCELLED")}
                
                # Apply our updates onto the fresh file state
                for i, ft in enumerate(fresh_trades):
                    if ft["id"] in settled_map:
                        fresh_trades[i] = settled_map[ft["id"]]
                
                atomic_json_write(SHADOW_TRADES_FILE, fresh_trades, indent=2)
            rl_agent.save()
            logger.info("[ShadowExecutor] Updated RL shadow settlements and trained DQN.")

    except Exception as e:
        logger.error(f"[ShadowExecutor] Error in shadow settlement loop: {e}")
