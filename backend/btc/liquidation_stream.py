import asyncio
import websockets
import json
import logging
import threading
import time

logger = logging.getLogger(__name__)

# C5 FIX: Thread-safe lock for all list mutations
_lock = threading.Lock()

# Global rolling tally variables
# We store liquidations as tuples of (timestamp, amount)
_long_liquidations = []
_short_liquidations = []

_loop = None
_thread = None

def _cleanup_old_liquidations():
    """Remove liquidations older than 15 minutes. MUST be called under _lock."""
    cutoff = time.time() - 900
    global _long_liquidations, _short_liquidations
    _long_liquidations = [liq for liq in _long_liquidations if liq[0] >= cutoff]
    _short_liquidations = [liq for liq in _short_liquidations if liq[0] >= cutoff]

async def _binance_force_order_stream():
    url = "wss://fstream.binance.com/ws/btcusdt@forceOrder"
    while True:
        try:
            async with websockets.connect(url) as ws:
                logger.info("[LiquidationStream] Connected to Binance Futures liquidations.")
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if "o" in data:
                        order = data["o"]
                        side = order.get("S") # 'BUY' or 'SELL'
                        amount = float(order.get("q", 0)) * float(order.get("p", 0)) # quantity * price = dollar amount
                        
                        with _lock:
                            _cleanup_old_liquidations()
                            
                            # If a short is liquidated, the forced order is a 'BUY'
                            if side == "BUY":
                                _short_liquidations.append((time.time(), amount))
                            # If a long is liquidated, the forced order is a 'SELL'
                            elif side == "SELL":
                                _long_liquidations.append((time.time(), amount))
        except Exception as e:
            logger.warning(f"[LiquidationStream] Disconnected or error: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)

def _start_async_loop():
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _loop.run_until_complete(_binance_force_order_stream())

def start_stream():
    """Starts the background thread for the Binance WebSocket stream."""
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_start_async_loop, daemon=True, name="LiquidationWS")
        _thread.start()
        logger.info("[LiquidationStream] Background thread started.")

def get_liquidation_imbalance() -> dict:
    """
    Returns the total dollar amount of liquidations in the last 15 minutes.
    """
    with _lock:
        _cleanup_old_liquidations()
        total_longs = sum(liq[1] for liq in _long_liquidations)
        total_shorts = sum(liq[1] for liq in _short_liquidations)
    
    return {
        "long_liquidations_usd": total_longs,
        "short_liquidations_usd": total_shorts,
        "net_imbalance_usd": total_shorts - total_longs # Positive -> more shorts liquidated (bullish)
    }
