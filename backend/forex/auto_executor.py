import time
import logging
import threading
from typing import Optional

from backend.forex.data_fetcher import is_forex_market_open, get_forex_ticker
from backend.forex.analyzer import analyze_forex_pair
from backend.forex.paper_trader import open_position, evaluate_stops_and_limits, get_open_positions, get_balance, calculate_pip_value
from backend.forex.news_calendar import is_safe_to_trade

logger = logging.getLogger(__name__)

_execution_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_is_running = False

# Default Config
ACTIVE_PAIRS = ["EURUSD", "GBPUSD", "USDJPY"]
RISK_PCT = 1.0 # 1% risk per trade

def forex_trading_loop():
    logger.info("Forex Auto-Executor started.")
    
    while not _stop_event.is_set():
        try:
            if not is_forex_market_open():
                logger.info("Forex market is closed for the weekend. Sleeping.")
                _stop_event.wait(300)
                continue
                
            open_positions = get_open_positions()
            current_balance = get_balance()
            
            for pair in ACTIVE_PAIRS:
                # 1. Update prices & evaluate SL/TP
                ticker = get_forex_ticker(pair)
                curr_price = ticker["price"]
                if curr_price == 0:
                    continue
                    
                evaluate_stops_and_limits(pair, curr_price)
                
                # Check if we already have an open position for this pair
                has_position = any(p["pair"] == pair for p in open_positions)
                if has_position:
                    continue # Wait for it to close
                    
                # 2. Check News Circuit Breaker
                news_status = is_safe_to_trade(pair)
                if not news_status["safe"]:
                    logger.debug(f"[{pair}] Skipping execution. {news_status['reason']}")
                    continue

                # 3. Analyze Technicals
                analysis = analyze_forex_pair(pair, timeframe="15m")
                signal = analysis.get("signal", "HOLD")
                
                # 4. Execute with Dynamic Sizing
                if signal in ["BUY", "SELL"]:
                    sl = analysis["sl"]
                    tp = analysis["tp"]
                    
                    # Risk management: Exact fractional sizing based on ATR SL
                    risk_amount = current_balance * (RISK_PCT / 100.0)
                    
                    sl_dist = abs(curr_price - sl)
                    pip_decimal = 0.01 if "JPY" in pair else 0.0001
                    pips_to_sl = sl_dist / pip_decimal
                    
                    if pips_to_sl > 0:
                        # Value of 1 standard unit (1 micro lot) in USD
                        # e.g., for EURUSD, 1 unit = $0.0001 per pip
                        pip_value_per_unit = calculate_pip_value(pair, 1, curr_price)
                        
                        if pip_value_per_unit > 0:
                            # Formula: Units = Risk_Amount / (Pips * Pip_Value_per_Unit)
                            exact_units = risk_amount / (pips_to_sl * pip_value_per_unit)
                            
                            # Round to nearest micro lot (1,000 units)
                            size = int(exact_units // 1000) * 1000
                            
                            if size >= 1000:
                                open_position(pair, signal, size, curr_price, sl, tp)
                                logger.info(f"EXECUTED FOREX {signal} on {pair} @ {curr_price}. Size: {size} units (Risking ${risk_amount:.2f}). SL: {sl}, TP: {tp}")
                            else:
                                logger.warning(f"[{pair}] Trade signal generated, but Stop Loss ({pips_to_sl:.1f} pips) is too wide to risk ${risk_amount:.2f} using micro lots.")
                        
            # Sleep 15 seconds before next cycle
            _stop_event.wait(15)
            
        except Exception as e:
            logger.error(f"Error in Forex loop: {e}", exc_info=True)
            _stop_event.wait(15)

def start_forex_executor():
    global _execution_thread, _is_running
    if _is_running:
        return
        
    _stop_event.clear()
    _execution_thread = threading.Thread(target=forex_trading_loop, daemon=True, name="ForexExecutor")
    _execution_thread.start()
    _is_running = True
    logger.info("Forex execution loop initiated.")

def stop_forex_executor():
    global _is_running
    _stop_event.set()
    _is_running = False
    logger.info("Forex execution loop stopped.")

def get_forex_status() -> dict:
    return {
        "running": _is_running,
        "active_pairs": ACTIVE_PAIRS,
        "balance": get_balance(),
        "open_positions": len(get_open_positions())
    }
