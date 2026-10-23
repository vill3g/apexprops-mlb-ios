import math
import logging

logger = logging.getLogger("Remediations")

# Remediation 2: Exit Discipline with Pre-Settlement Expiration Guard
def evaluate_exit_discipline(trade: dict, current_bid: float, spot_price: float, strike_price: float, seconds_left: int) -> dict:
    entry_price = float(trade.get("entry_price", 0.50))
    direction = str(trade.get("direction", "ABOVE")).upper()
    side = str(trade.get("side", "")).upper()
    is_yes = (direction in ["ABOVE", "YES"] or side == "YES")

    # 1. High Conviction Hold: If contract is deeply in the money (bid >= 88c), let it settle to 100c
    if current_bid >= 0.88:
        return {
            "should_close": False,
            "reason": "HIGH_CONVICTION_HOLD_TO_SETTLEMENT",
            "exit_price": current_bid
        }

    # Measure spot distance to strike
    spot_cushion = (spot_price - strike_price) if is_yes else (strike_price - spot_price)
    spot_deficit = -spot_cushion

    # 2. Pre-Settlement Expiration Guard (T-90s to T-15s before expiry)
    # Prevents holding dangerous coin-flips into a 0c settlement wipeout
    if 15 <= seconds_left <= 90:
        # If contract has low cushion (less than $20 spot cushion) or market bid is weak (< 65c)
        if current_bid > 0.05 and (current_bid < 0.70 or spot_cushion < 25.0):
            return {
                "should_close": True,
                "reason": f"PRE_SETTLEMENT_SALVAGE_GUARD (T-{seconds_left}s bid ${current_bid:.2f}, cushion ${spot_cushion:.1f})",
                "exit_price": current_bid
            }

    # 3. Structural Mid-Interval Invalidation
    if spot_deficit > 75.0 and seconds_left > 300:
        return {
            "should_close": True,
            "reason": "STRUCTURAL_SPOT_INVALIDATION",
            "exit_price": current_bid
        }

    return {"should_close": False, "reason": "HOLD_TO_SETTLEMENT"}

# Remediation 3
def is_reentry_permitted(user_history: list, current_ticker: str, last_exit_reason: str, seconds_left: int) -> bool:
    if "STOP_LOSS" in str(last_exit_reason).upper() or "INVALIDATION" in str(last_exit_reason).upper():
        logger.info(f"[ReEntry Guard] Blocked: Re-entry after stop loss prohibited on {current_ticker}.")
        return False
        
    if seconds_left < 120:
        return False
        
    return True

# Remediation 4
def calculate_anti_whipsaw_trailing_stop(
    entry_price: float,
    max_seen_bid: float,
    current_bid: float,
    ts_activation_pct: float = 35.0,
    ts_distance_pct: float = 6.0,
    min_buffer_cents: float = 0.02
) -> dict:
    if entry_price <= 0:
        return {"should_exit": False}
    profit_pct = ((max_seen_bid - entry_price) / entry_price) * 100.0
    
    if profit_pct < ts_activation_pct:
        return {"should_exit": False}
        
    percentage_distance = max_seen_bid * (ts_distance_pct / 100.0)
    effective_trail_distance = max(min_buffer_cents, percentage_distance)
    
    stop_threshold = max_seen_bid - effective_trail_distance
    
    # Guarantee at least break-even (or minimum profit floor of entry + 1 cent) once trailing stop activates
    breakeven_floor = entry_price + 0.01
    stop_threshold = max(stop_threshold, breakeven_floor)
    
    if current_bid <= stop_threshold:
        return {
            "should_exit": True,
            "exit_threshold": round(stop_threshold, 2),
            "current_bid": round(current_bid, 2),
            "reason": "ANTI_WHIPSAW_TRAILING_STOP"
        }
        
    return {"should_exit": False, "stop_threshold": round(stop_threshold, 2)}

# Remediation 5
def determine_execution_signal(model_prob: float, heuristic_grade: str, is_force_flag: bool) -> dict:
    if is_force_flag:
        logger.warning("[Execution Gate] Force trade flag detected. Bypassing force mode; applying strict EV validation.")
        
    MINIMUM_CONVICTION = 55.0
    if model_prob < MINIMUM_CONVICTION:
        return {
            "execute": False,
            "direction": "PASS",
            "reason": f"INSUFFICIENT_CONVICTION: Model {model_prob:.1f}% < {MINIMUM_CONVICTION}% required"
        }
        
    direction = "YES" if model_prob >= 50.0 else "NO"
    
    return {
        "execute": True,
        "direction": direction,
        "conviction": model_prob
    }

# Remediation 7
def check_kalshi_market_structure_confluence(kalshi_market: dict, thresholds: dict) -> dict:
    if not kalshi_market:
        return {"override": False}
        
    raw_yes = float(kalshi_market.get("yes_ask", 0.50) or 0.50)
    raw_no = float(kalshi_market.get("no_ask", 0.50) or 0.50)
    
    yes_cents = raw_yes * 100.0 if raw_yes <= 1.0 else raw_yes
    no_cents = raw_no * 100.0 if raw_no <= 1.0 else raw_no
    imbalance = float(kalshi_market.get("book_imbalance", 0.0) or 0.0)
    
    target_yes = float(thresholds.get("kalshi_override_yes", 62.0))
    target_imbalance = float(thresholds.get("kalshi_imbalance_threshold", 0.35))
    
    if yes_cents >= target_yes or imbalance >= target_imbalance:
        return {
            "override": True,
            "direction": "YES",
            "implied_prob": yes_cents,
            "imbalance": imbalance
        }
        
    return {"override": False}

# Remediation 8
def is_entry_timing_valid(seconds_left: int, timeframe_seconds: int = 900) -> dict:
    seconds_elapsed = timeframe_seconds - seconds_left
    minute_elapsed = seconds_elapsed // 60
    
    if seconds_left < 120:
        return {
            "valid": False,
            "reason": f"TERMINAL_GAMMA_LOCK: {seconds_left}s remaining < 120s minimum corridor"
        }
        
    return {"valid": True, "minute": minute_elapsed, "seconds_left": seconds_left}

# Remediation 9
def evaluate_consecutive_interval_circuit_breaker(today_trades: list, max_consecutive_losing_intervals: int = 3) -> str:
    interval_pnl_map = {}
    
    for trade in sorted(today_trades, key=lambda x: str(x.get("timestamp", ""))):
        ticker = trade.get("ticker")
        if trade.get("status") in ["SETTLED", "CLOSED"]:
            pnl = float(trade.get("pnl", 0.0))
            interval_pnl_map.setdefault(ticker, []).append(pnl)
            
    consecutive_losses = 0
    for ticker in reversed(list(interval_pnl_map.keys())):
        net_interval_pnl = sum(interval_pnl_map[ticker])
        if net_interval_pnl < 0.0:
            consecutive_losses += 1
            if consecutive_losses >= max_consecutive_losing_intervals:
                return f"CIRCUIT_BREAKER_ACTIVE: {consecutive_losses} consecutive losing INTERVALS. Halting trading."
        else:
            break
            
    return "OK"
