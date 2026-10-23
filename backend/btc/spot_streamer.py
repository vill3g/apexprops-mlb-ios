"""
backend/btc/spot_streamer.py
High-Frequency Sub-Second Crypto Spot Ticker Streamer.

Constituent source: Kraken & Coinbase indices (the exact primary constituents of CF Benchmarks BRTI/ETHUSD).
Provides sub-second live spot prices for BTC, ETH, and SOL.
"""

import asyncio
import json
import logging
import threading
import time
from typing import Any, Dict, Optional
import requests

logger = logging.getLogger(__name__)

# Global sub-second live spot cache
_LIVE_SPOT_TICKS: Dict[str, Dict[str, Any]] = {}
_TICK_LOCK = threading.Lock()
_STREAMER_THREAD: Optional[threading.Thread] = None
_RUNNING = False


def get_live_spot_tick(asset: str) -> Optional[Dict[str, Any]]:
    """Returns the latest spot tick for asset (e.g. BTC, ETH, SOL, DOGE)."""
    a_up = str(asset or "BTC").upper().strip()
    with _TICK_LOCK:
        tick = _LIVE_SPOT_TICKS.get(a_up)
        if tick and (time.time() - tick.get("timestamp", 0)) < 10.0:
            return dict(tick)
    return None


def get_live_spot_price(asset: str, fallback_price: float = 0.0) -> float:
    """Returns the exact current spot price float, or fallback."""
    t = get_live_spot_tick(asset)
    if t and t.get("price", 0) > 0:
        return float(t["price"])
    return float(fallback_price)


async def _kraken_ws_stream_worker():
    """Streams live spot trades/ticks via Kraken public WebSocket v2 (CF Benchmarks primary constituent)."""
    import websockets

    ws_url = "wss://ws.kraken.com/v2"

    sub_msg = {
        "method": "subscribe",
        "params": {
            "channel": "ticker",
            "symbol": ["BTC/USD", "ETH/USD", "SOL/USD", "DOGE/USD"]
        }
    }

    while _RUNNING:
        try:
            logger.info("[SpotStreamer] Connecting to Kraken v2 ticker stream (CF Benchmarks constituent)...")
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                await ws.send(json.dumps(sub_msg))
                logger.info("[SpotStreamer] Subscribed to Kraken real-time BTC/ETH/SOL/DOGE ticker stream.")

                while _RUNNING:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if data.get("channel") == "ticker" and "data" in data:
                        for item in data["data"]:
                            sym = item.get("symbol", "")
                            last_p = float(item.get("last", 0.0) or item.get("bid", 0.0) or 0.0)
                            if last_p > 0:
                                a = "BTC" if "BTC" in sym else ("ETH" if "ETH" in sym else ("SOL" if "SOL" in sym else ("DOGE" if "DOGE" in sym else None)))
                                if a:
                                    with _TICK_LOCK:
                                        _LIVE_SPOT_TICKS[a] = {
                                            "asset": a,
                                            "price": last_p,
                                            "timestamp": time.time(),
                                            "source": "kraken_cf_constituent_ws",
                                        }
        except Exception as e:
            logger.debug(f"[SpotStreamer] Kraken WS reconnecting: {e}")
            await asyncio.sleep(2.0)


def _poll_rest_fallback():
    """Fallback REST polling every 1 second to guarantee fresh ticks if WS disconnects."""
    headers = {"User-Agent": "ApexProps-Trader/1.0"}
    while _RUNNING:
        try:
            r = requests.get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD,ETHUSD,SOLUSD,XDGUSD", headers=headers, timeout=2.0)
            if r.status_code == 200:
                res = r.json().get("result", {})
                for k, v in res.items():
                    price = float(v.get("c", [0.0])[0])
                    if price > 0:
                        a = "BTC" if ("XBT" in k or "BTC" in k) else ("ETH" if "ETH" in k else ("SOL" if "SOL" in k else ("DOGE" if ("XDG" in k or "DOGE" in k) else None)))
                        if a:
                            with _TICK_LOCK:
                                # Only set if WS tick is older than 1.5s
                                curr = _LIVE_SPOT_TICKS.get(a)
                                if not curr or (time.time() - curr.get("timestamp", 0)) > 1.5:
                                    _LIVE_SPOT_TICKS[a] = {
                                        "asset": a,
                                        "price": price,
                                        "timestamp": time.time(),
                                        "source": "kraken_rest_fallback",
                                    }
        except Exception:
            pass
        time.sleep(1.0)


def _thread_runner():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_kraken_ws_stream_worker())
    finally:
        loop.close()


def start_spot_streamer():
    """Starts the background spot streamer thread and REST fallback."""
    global _STREAMER_THREAD, _RUNNING
    if _RUNNING or (_STREAMER_THREAD and _STREAMER_THREAD.is_alive()):
        return
    _RUNNING = True
    _STREAMER_THREAD = threading.Thread(target=_thread_runner, daemon=True, name="KrakenSpotStreamerThread")
    _STREAMER_THREAD.start()

    rest_t = threading.Thread(target=_poll_rest_fallback, daemon=True, name="KrakenSpotRestThread")
    rest_t.start()
    logger.info("[SpotStreamer] Sub-second Kraken spot streamer launched.")


start_spot_streamer()
