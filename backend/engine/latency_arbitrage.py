"""
Level 2: Cross-Market Latency Arbitrage Sniper for ShadowTrader AI.
Capitalizes on the latency gap between underlying spot exchanges (Coinbase / Binance)
and Kalshi's binary options market makers.

How it works:
1. Tracks high-velocity spot price impulses on premier spot exchanges (Coinbase/Binance).
2. Measures immediate strike proximity: when spot bursts through a 15m Kalshi strike
   (e.g. Strike = $81,950, Spot suddenly surges from $81,940 -> $81,975 with heavy volume),
   Kalshi market makers often take 300ms to 1,500ms to pull their 45c-55c limit orders.
3. Calculates mathematical expectancy and flags an immediate High-Frequency Sniping Alert.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("latency_arbitrage")

# In-memory tick history (timestamp, price, volume) per asset
_spot_ticks: Dict[str, deque] = {}
_tick_lock = threading.Lock()
MAX_TICKS = 120


class LatencyArbitrageSniper:
    """Detects lead-lag price discovery discrepancies against Kalshi quotes."""

    @classmethod
    def record_spot_tick(cls, asset: str, price: float, volume: float = 0.0) -> None:
        """Records an incoming real-time spot price tick."""
        if price <= 0:
            return
        asset_norm = str(asset or "BTC").upper().strip()
        now = time.time()
        with _tick_lock:
            if asset_norm not in _spot_ticks:
                _spot_ticks[asset_norm] = deque(maxlen=MAX_TICKS)
            _spot_ticks[asset_norm].append((now, float(price), float(volume)))

    @classmethod
    def evaluate_arbitrage_opportunity(
        cls,
        asset: str,
        kalshi_market: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates whether an active lead-lag latency arbitrage window is open.
        Returns:
            - is_arbitrage_active: bool
            - side: "YES" | "NO" | "NONE"
            - projected_edge_cents: float
            - spot_velocity_per_sec: float
            - rationale: str
        """
        asset_norm = str(asset or "BTC").upper().strip()
        now = time.time()

        if not kalshi_market:
            return cls._empty_arb_result("No Kalshi market available")

        strike = float(kalshi_market.get("target_price") or kalshi_market.get("floor_strike") or 0.0)
        if strike <= 0:
            return cls._empty_arb_result("No valid strike price")

        yes_ask = float(kalshi_market.get("yes_ask", 0.50) or 0.50)
        no_ask = float(kalshi_market.get("no_ask", 0.50) or 0.50)
        yes_bid = float(kalshi_market.get("yes_bid", 0.50) or 0.50)
        no_bid = float(kalshi_market.get("no_bid", 0.50) or 0.50)

        # Retrieve spot velocity from recent ticks
        with _tick_lock:
            ticks = list(_spot_ticks.get(asset_norm, []))

        if len(ticks) < 3:
            return cls._empty_arb_result("Insufficient spot tick history")

        # Filter to last 5 seconds of tick activity
        recent_ticks = [t for t in ticks if now - t[0] <= 5.0]
        if len(recent_ticks) < 2:
            return cls._empty_arb_result("No ticks in last 5 seconds")

        cur_spot = recent_ticks[-1][1]
        t_start = recent_ticks[0][0]
        t_end = recent_ticks[-1][0]
        dt = max(0.1, t_end - t_start)
        p_start = recent_ticks[0][1]
        p_delta = cur_spot - p_start
        velocity = p_delta / dt  # Dollars per second

        # Measure strike penetration and distance
        spot_distance_to_strike = cur_spot - strike
        distance_pct = (spot_distance_to_strike / strike) * 100.0

        # Scale velocity threshold relative to asset volatility
        min_velocity = 8.0 if asset_norm == "BTC" else (0.8 if asset_norm == "ETH" else 0.05)

        # CASE 1: Bullish Breakout Lag
        # Spot surged past the strike with strong positive velocity, but Kalshi YES ask is still underpriced
        if spot_distance_to_strike > 0 and velocity >= min_velocity:
            # Spot is cleanly above strike and running up fast.
            # Theoretical fair value of YES should be >= 0.70 - 0.90, but Kalshi is still quoting ask <= 0.62
            if yes_ask <= 0.62:
                edge = round((0.78 - yes_ask) * 100.0, 1)
                return {
                    "is_arbitrage_active": True,
                    "side": "YES",
                    "action": "BID YES (LATENCY ARBITRAGE)",
                    "target_strike": strike,
                    "spot_price": cur_spot,
                    "spot_velocity": round(velocity, 2),
                    "kalshi_ask": yes_ask,
                    "theoretical_value": 0.78,
                    "projected_edge_cents": edge,
                    "confidence": 84.0,
                    "rationale": (
                        f"⚡ Latency Arbitrage Snipe: Spot (${cur_spot:,.2f}) surged above strike (${strike:,.2f}) "
                        f"at +${velocity:,.1f}/sec. Kalshi YES ask is lagging at {yes_ask*100:.0f}¢ (Fair Value: 78¢)."
                    )
                }

        # CASE 2: Bearish Breakdown Lag
        # Spot plunged below the strike with strong negative velocity, but Kalshi NO ask is still underpriced
        elif spot_distance_to_strike < 0 and velocity <= -min_velocity:
            if no_ask <= 0.62:
                edge = round((0.78 - no_ask) * 100.0, 1)
                return {
                    "is_arbitrage_active": True,
                    "side": "NO",
                    "action": "BID NO (LATENCY ARBITRAGE)",
                    "target_strike": strike,
                    "spot_price": cur_spot,
                    "spot_velocity": round(velocity, 2),
                    "kalshi_ask": no_ask,
                    "theoretical_value": 0.78,
                    "projected_edge_cents": edge,
                    "confidence": 84.0,
                    "rationale": (
                        f"⚡ Latency Arbitrage Snipe: Spot (${cur_spot:,.2f}) plunged below strike (${strike:,.2f}) "
                        f"at -${abs(velocity):,.1f}/sec. Kalshi NO ask is lagging at {no_ask*100:.0f}¢ (Fair Value: 78¢)."
                    )
                }

        return cls._empty_arb_result("Quotes aligned with spot velocity")

    @classmethod
    def _empty_arb_result(cls, reason: str) -> Dict[str, Any]:
        return {
            "is_arbitrage_active": False,
            "side": "NONE",
            "action": "PASS",
            "target_strike": 0.0,
            "spot_price": 0.0,
            "spot_velocity": 0.0,
            "kalshi_ask": 0.50,
            "theoretical_value": 0.50,
            "projected_edge_cents": 0.0,
            "confidence": 50.0,
            "rationale": reason
        }
