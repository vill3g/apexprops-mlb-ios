"""
backend.investments.subsecond_tape_engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Realm 1: Real-Time Sub-Second Tape Reader & Level 2 Depth Imbalance Engine.
Tracks:
- Millisecond order flow prints (Time & Sales)
- Aggressive Buy vs Sell Volume Delta (Cumulative Volume Delta - CVD)
- Institutional Block Sweep Detection (trades >= 5,000 shares or >= $500,000 notional)
- Real-time Bid/Ask Wall Absorption Tracking
"""

import time
import math
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Set

logger = logging.getLogger(__name__)


class SubSecondTapeEngine:
    _tape_buffers: Dict[str, List[Dict[str, Any]]] = {}
    _MAX_BUFFER = 200
    _active_subscribers: Set[Any] = set()

    @classmethod
    def ingest_print(
        cls,
        symbol: str,
        price: float,
        size: float,
        bid: float,
        ask: float,
        timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Ingests a single Time & Sales print and classifies aggressive side:
        - If price >= ask: Aggressive Buyer (Taker Buy)
        - If price <= bid: Aggressive Seller (Taker Sell)
        - If between: Inferred by tick direction
        """
        sym = symbol.strip().upper()
        now = timestamp or time.time()
        buf = cls._tape_buffers.setdefault(sym, [])

        # Side classification via Lee-Ready algorithm
        if ask > 0 and price >= ask:
            side = "BUY"
        elif bid > 0 and price <= bid:
            side = "SELL"
        else:
            prev_price = buf[-1]["price"] if buf else price
            side = "BUY" if price >= prev_price else "SELL"

        notional = round(price * size, 2)
        is_block = size >= 5000 or notional >= 500000.0

        print_obj = {
            "time": now,
            "price": price,
            "size": size,
            "notional": notional,
            "side": side,
            "is_block": is_block
        }

        buf.append(print_obj)
        if len(buf) > cls._MAX_BUFFER:
            cls._tape_buffers[sym] = buf[-cls._MAX_BUFFER:]

        # Broadcast real-time print event to all active WebSocket listeners
        cls._broadcast_realtime_event({
            "type": "TAPE_PRINT",
            "symbol": sym,
            "print": print_obj,
            "analytics": cls.get_order_flow_analytics(sym)
        })

        return print_obj

    @classmethod
    def register_subscriber(cls, websocket: Any) -> None:
        """Registers an active WebSocket connection for sub-second streaming."""
        cls._active_subscribers.add(websocket)

    @classmethod
    def unregister_subscriber(cls, websocket: Any) -> None:
        """Removes a disconnected WebSocket connection."""
        cls._active_subscribers.discard(websocket)

    @classmethod
    def _broadcast_realtime_event(cls, payload: Dict[str, Any]) -> None:
        """Asynchronously fans out real-time tape prints to all connected subscribers."""
        if not cls._active_subscribers:
            return
        dead = []
        for ws in list(cls._active_subscribers):
            try:
                # Schedule coroutine if event loop is running
                try:
                    loop = asyncio.get_running_loop()
                    if loop.is_running():
                        loop.create_task(ws.send_json(payload))
                except RuntimeError:
                    # In sync thread or background task without active loop
                    pass
            except Exception:
                dead.append(ws)
        for d in dead:
            cls._active_subscribers.discard(d)

    @classmethod
    def get_order_flow_analytics(cls, symbol: str) -> Dict[str, Any]:
        """
        Computes real-time Cumulative Volume Delta (CVD), Buyer/Seller Ratio,
        and Institutional Block Sweep Summary.
        """
        sym = symbol.strip().upper()
        buf = cls._tape_buffers.get(sym, [])
        if not buf:
            return {
                "symbol": sym,
                "cvd": 0.0,
                "buy_volume": 0.0,
                "sell_volume": 0.0,
                "flow_bias": "NEUTRAL",
                "delta_ratio": 1.0,
                "block_sweeps_count": 0,
                "recent_prints_count": 0,
                "absorption_detected": False
            }

        buy_vol = sum(p["size"] for p in buf if p["side"] == "BUY")
        sell_vol = sum(p["size"] for p in buf if p["side"] == "SELL")
        cvd = buy_vol - sell_vol
        total_vol = buy_vol + sell_vol
        blocks = [p for p in buf if p["is_block"]]

        delta_ratio = round((buy_vol / max(sell_vol, 0.01)), 2)

        if delta_ratio > 1.4:
            flow_bias = "AGGRESSIVE_BUYING"
        elif delta_ratio < 0.7:
            flow_bias = "AGGRESSIVE_SELLING"
        else:
            flow_bias = "BALANCED"

        # Absorption: Heavy selling delta but price rising, or heavy buying delta but price falling
        absorption = False
        if len(buf) >= 10:
            p_start = buf[0]["price"]
            p_end = buf[-1]["price"]
            if cvd < -10000 and p_end >= p_start:
                absorption = True  # Passive buyers absorbing aggressive sellers
            elif cvd > 10000 and p_end <= p_start:
                absorption = True  # Passive sellers absorbing aggressive buyers

        return {
            "symbol": sym,
            "cvd": round(cvd, 2),
            "buy_volume": round(buy_vol, 2),
            "sell_volume": round(sell_vol, 2),
            "flow_bias": flow_bias,
            "delta_ratio": delta_ratio,
            "block_sweeps_count": len(blocks),
            "recent_prints_count": len(buf),
            "absorption_detected": absorption
        }
