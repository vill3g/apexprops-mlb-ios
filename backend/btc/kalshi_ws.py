import asyncio
import base64
import json
import logging
import threading
import time
from typing import Dict, Any, List, Set

import websockets
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

logger = logging.getLogger("kalshi_ws")

WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"

# Global cache to hold market data pushed by the WS
_market_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.Lock()

# Tickers we want to stay subscribed to
_subscribed_tickers: Set[str] = set()
_subscription_lock = threading.Lock()

# Shared reference to push messages to the active websocket loop
_command_queue: asyncio.Queue = None

def get_market_cache(ticker: str) -> Dict[str, Any]:
    with _cache_lock:
        return _market_cache.get(ticker, {})

def subscribe_to_market(ticker: str):
    """Adds a ticker to the subscription list and queues a subscribe command if WS is active."""
    with _subscription_lock:
        if ticker in _subscribed_tickers:
            return
        _subscribed_tickers.add(ticker)
    
    if _command_queue:
        cmd = {
            "id": int(time.time() * 1000),
            "cmd": "subscribe",
            "params": {
                "channels": ["ticker"],
                "market_tickers": [ticker]
            }
        }
        # Schedule the push asynchronously
        try:
            _command_queue.put_nowait(cmd)
        except Exception as e:
            logger.debug(f"[KalshiWS] Failed to queue subscribe: {e}")

async def _ws_loop(trader_instance):
    global _command_queue
    _command_queue = asyncio.Queue()

    while True:
        try:
            # 1. Generate Auth Headers
            timestamp = str(int(time.time() * 1000))
            msg_string = timestamp + "GET" + "/trade-api/ws/v2"
            
            signature = trader_instance._private_key_obj.sign(
                msg_string.encode("utf-8"),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            signature_b64 = base64.b64encode(signature).decode("utf-8")
            
            headers = {
                "KALSHI-ACCESS-KEY": trader_instance.key_id,
                "KALSHI-ACCESS-SIGNATURE": signature_b64,
                "KALSHI-ACCESS-TIMESTAMP": timestamp
            }

            logger.info(f"[KalshiWS] Connecting to {WS_URL}...")
            import inspect
            ws_kwargs = {}
            if "additional_headers" in inspect.signature(websockets.connect).parameters:
                ws_kwargs["additional_headers"] = headers
            else:
                ws_kwargs["extra_headers"] = headers

            async with websockets.connect(WS_URL, **ws_kwargs) as ws:
                logger.info("[KalshiWS] Authenticated & Connected to Kalshi v2 WebSocket!")
                
                # Resubscribe to existing tickers on reconnect
                with _subscription_lock:
                    tickers_to_sub = list(_subscribed_tickers)
                
                if tickers_to_sub:
                    # chunk it so we don't send too huge of a message
                    chunk_size = 50
                    for i in range(0, len(tickers_to_sub), chunk_size):
                        sub_msg = {
                            "id": int(time.time() * 1000) + i,
                            "cmd": "subscribe",
                            "params": {
                                "channels": ["ticker"],
                                "market_tickers": tickers_to_sub[i:i+chunk_size]
                            }
                        }
                        await ws.send(json.dumps(sub_msg))

                async def receive_messages():
                    async for message in ws:
                        data = json.loads(message)
                        msg_type = data.get("type")
                        
                        if msg_type == "ticker":
                            msg_data = data.get("msg", {})
                            ticker = msg_data.get("market_ticker")
                            if ticker:
                                with _cache_lock:
                                    _market_cache[ticker] = msg_data
                        elif msg_type == "heartbeat":
                            # Respond with ping? Kalshi WS might handle this automatically, or we ignore
                            pass
                        elif msg_type == "error":
                            logger.warning(f"[KalshiWS] Server Error: {data}")

                async def process_commands():
                    while True:
                        cmd = await _command_queue.get()
                        await ws.send(json.dumps(cmd))

                await asyncio.gather(
                    receive_messages(),
                    process_commands()
                )

        except Exception as e:
            logger.warning(f"[KalshiWS] Connection lost or failed: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)

def start_kalshi_ws(trader_instance):
    """
    Starts the Kalshi WebSocket background thread.
    Requires a configured KalshiTrader instance to inherit credentials.
    """
    if not trader_instance or not trader_instance.is_authenticated():
        logger.warning("[KalshiWS] Cannot start WebSocket: provided trader is unauthenticated.")
        return

    def run_in_thread():
        asyncio.run(_ws_loop(trader_instance))

    t = threading.Thread(target=run_in_thread, daemon=True, name="KalshiWebSocket")
    t.start()
    logger.info("[KalshiWS] Background thread started.")
