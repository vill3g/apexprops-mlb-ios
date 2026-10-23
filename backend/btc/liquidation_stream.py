import asyncio
import json
import logging
import threading
import time
from typing import Dict, List, Tuple

import requests
import websockets

logger = logging.getLogger(__name__)

# Thread-safe lock for all list mutations
_lock = threading.Lock()

# Per-asset rolling tally variables: asset -> list of (timestamp, amount_usd)
_SUPPORTED_ASSETS = ("BTC", "ETH", "SOL", "DOGE")
# OKX SWAP contract multipliers (in coin units per contract)
_OKX_CT_VAL = {"BTC": 0.01, "ETH": 0.1, "SOL": 1.0, "DOGE": 1000.0}

_long_liquidations: Dict[str, List[Tuple[float, float]]] = {a: [] for a in _SUPPORTED_ASSETS}
_short_liquidations: Dict[str, List[Tuple[float, float]]] = {a: [] for a in _SUPPORTED_ASSETS}

_loop = None
_thread = None


def _cleanup_old_liquidations():
    """Remove liquidations older than 15 minutes across all assets. MUST be called under _lock."""
    cutoff = time.time() - 900
    for a in _SUPPORTED_ASSETS:
        _long_liquidations[a] = [liq for liq in _long_liquidations.get(a, []) if liq[0] >= cutoff]
        _short_liquidations[a] = [liq for liq in _short_liquidations.get(a, []) if liq[0] >= cutoff]


def _symbol_to_asset(sym: str) -> str:
    s = str(sym or "").upper()
    for a in _SUPPORTED_ASSETS:
        if s.startswith(a):
            return a
    return ""


def _seed_recent_okx_liquidations():
    """Seeds the last 15 minutes of filled liquidations from OKX public REST on startup."""
    cutoff_ms = (time.time() - 900) * 1000.0
    for a in _SUPPORTED_ASSETS:
        try:
            r = requests.get(
                f"https://www.okx.com/api/v5/public/liquidation-orders?instType=SWAP&uly={a}-USDT&state=filled",
                timeout=2.5,
            )
            if r.status_code == 200:
                blocks = r.json().get("data", [])
                details = blocks[0].get("details", []) if blocks else []
                ct_mult = _OKX_CT_VAL.get(a, 1.0)
                with _lock:
                    for item in details:
                        ts_ms = float(item.get("ts") or item.get("time") or 0.0)
                        if ts_ms >= cutoff_ms:
                            px = float(item.get("bkPx", 0.0) or 0.0)
                            sz = float(item.get("sz", 0.0) or 0.0)
                            usd_amt = px * sz * ct_mult
                            pos_side = str(item.get("posSide", "")).lower()
                            side = str(item.get("side", "")).lower()
                            if pos_side == "short" or side == "buy":
                                _short_liquidations[a].append((ts_ms / 1000.0, usd_amt))
                            elif pos_side == "long" or side == "sell":
                                _long_liquidations[a].append((ts_ms / 1000.0, usd_amt))
        except Exception as e:
            logger.debug(f"[LiquidationStream] OKX seed error for {a}: {e}")


async def _okx_liquidation_stream():
    """Streams live perpetual swap liquidations for BTC, ETH, SOL, DOGE via OKX v5 public WebSocket."""
    url = "wss://ws.okx.com:8443/ws/v5/public"
    sub_msg = {
        "op": "subscribe",
        "args": [{"channel": "liquidation-orders", "instType": "SWAP"}],
    }
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                await ws.send(json.dumps(sub_msg))
                logger.info("[LiquidationStream] Connected to OKX v5 multi-asset SWAP liquidations (BTC, ETH, SOL, DOGE).")
                while True:
                    msg = await ws.recv()
                    raw = json.loads(msg)
                    data_list = raw.get("data", []) if isinstance(raw, dict) else []
                    for block in data_list:
                        inst_id = block.get("instId", "") or block.get("uly", "")
                        asset_key = _symbol_to_asset(inst_id)
                        if not asset_key:
                            continue
                        ct_mult = _OKX_CT_VAL.get(asset_key, 1.0)
                        for det in block.get("details", []):
                            px = float(det.get("bkPx", 0.0) or 0.0)
                            sz = float(det.get("sz", 0.0) or 0.0)
                            usd_amt = px * sz * ct_mult
                            pos_side = str(det.get("posSide", "")).lower()
                            side = str(det.get("side", "")).lower()
                            with _lock:
                                _cleanup_old_liquidations()
                                if pos_side == "short" or side == "buy":
                                    _short_liquidations[asset_key].append((time.time(), usd_amt))
                                elif pos_side == "long" or side == "sell":
                                    _long_liquidations[asset_key].append((time.time(), usd_amt))
        except Exception as e:
            logger.debug(f"[LiquidationStream] OKX WS reconnecting in 5s: {e}")
            await asyncio.sleep(5)


def _start_async_loop():
    global _loop
    _seed_recent_okx_liquidations()
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _loop.run_until_complete(_okx_liquidation_stream())


def start_stream():
    """Starts the background thread for the multi-asset liquidation WebSocket stream."""
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_start_async_loop, daemon=True, name="LiquidationWS")
        _thread.start()
        logger.info("[LiquidationStream] Background thread started.")


def get_liquidation_imbalance(asset: str = "BTC") -> dict:
    """
    Returns the total dollar amount of liquidations in the last 15 minutes for the specified asset.
    """
    a_up = str(asset or "BTC").upper().strip()
    if a_up not in _SUPPORTED_ASSETS:
        a_up = "BTC"

    with _lock:
        _cleanup_old_liquidations()
        total_longs = sum(liq[1] for liq in _long_liquidations.get(a_up, []))
        total_shorts = sum(liq[1] for liq in _short_liquidations.get(a_up, []))

    return {
        "asset": a_up,
        "long_liquidations_usd": round(total_longs, 2),
        "short_liquidations_usd": round(total_shorts, 2),
        "net_imbalance_usd": round(total_shorts - total_longs, 2)  # Positive -> more shorts liquidated (bullish)
    }
