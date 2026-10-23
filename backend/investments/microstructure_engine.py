"""
backend.investments.microstructure_engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Frontier 1: Level 2 Order Book Imbalance (OBI), Cumulative Volume Delta (CVD),
and Multi-Timeframe Anchored VWAP with Standard Deviation Corridors (1σ, 2σ, 3σ).
"""

import math
import time
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MicrostructureEngine:
    @staticmethod
    def calculate_order_book_imbalance(
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
        depth: int = 5
    ) -> Dict[str, Any]:
        """
        Calculates instantaneous Order Book Imbalance (OBI) across top k levels.
        Formula: OBI = (Sum(Bid_Volume) - Sum(Ask_Volume)) / (Sum(Bid_Volume) + Sum(Ask_Volume))
        Range: [-1.0 (pure selling depth), +1.0 (pure buying depth)]
        """
        top_bids = bids[:depth]
        top_asks = asks[:depth]

        bid_vol = sum(vol for _, vol in top_bids) if top_bids else 0.0
        ask_vol = sum(vol for _, vol in top_asks) if top_asks else 0.0
        total_vol = bid_vol + ask_vol

        if total_vol <= 0.0:
            return {
                "obi": 0.0,
                "bias": "NEUTRAL",
                "bid_volume": 0.0,
                "ask_volume": 0.0,
                "imbalance_ratio": 1.0,
                "signal": "BALANCED_BOOK"
            }

        obi = (bid_vol - ask_vol) / total_vol
        obi = round(max(-1.0, min(1.0, obi)), 3)

        if obi > 0.35:
            signal = "HEAVY_BID_ACCUMULATION"
            bias = "BULLISH"
        elif obi < -0.35:
            signal = "HEAVY_ASK_ABSORPTION"
            bias = "BEARISH"
        else:
            signal = "BALANCED_DEPTH"
            bias = "NEUTRAL"

        return {
            "obi": obi,
            "bias": bias,
            "bid_volume": round(bid_vol, 2),
            "ask_volume": round(ask_vol, 2),
            "imbalance_ratio": round((bid_vol / max(ask_vol, 0.01)), 2),
            "signal": signal
        }

    @staticmethod
    def compute_anchored_vwap_bands(
        bars: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Computes Anchored VWAP with ±1σ, ±2σ, and ±3σ statistical volatility corridors.
        """
        if not bars:
            return {
                "vwap": 0.0,
                "sigma": 0.0,
                "upper_1s": 0.0,
                "lower_1s": 0.0,
                "upper_2s": 0.0,
                "lower_2s": 0.0,
                "upper_3s": 0.0,
                "lower_3s": 0.0,
                "stretch": "AT_VWAP"
            }

        cum_pv = 0.0
        cum_vol = 0.0

        for b in bars:
            high = float(b.get("high") or b.get("close") or 0.0)
            low = float(b.get("low") or b.get("close") or 0.0)
            close = float(b.get("close") or 0.0)
            vol = float(b.get("volume") or 1.0)

            typical_price = (high + low + close) / 3.0
            cum_pv += (typical_price * vol)
            cum_vol += vol

        if cum_vol <= 0:
            return {"vwap": 0.0, "sigma": 0.0, "stretch": "NO_VOLUME"}

        vwap = cum_pv / cum_vol

        # Variance calculation
        variance_sum = 0.0
        for b in bars:
            typical_price = (float(b.get("high", 0)) + float(b.get("low", 0)) + float(b.get("close", 0))) / 3.0
            vol = float(b.get("volume") or 1.0)
            variance_sum += ((typical_price - vwap) ** 2) * vol

        sigma = math.sqrt(variance_sum / cum_vol)
        last_price = float(bars[-1].get("close") or vwap)

        # Stretch classification
        diff = last_price - vwap
        if diff > (2.0 * sigma):
            stretch = "OVEREXTENDED_HIGH"
        elif diff < (-2.0 * sigma):
            stretch = "OVEREXTENDED_LOW"
        elif diff > (1.0 * sigma):
            stretch = "MILD_EXTENSION_HIGH"
        elif diff < (-1.0 * sigma):
            stretch = "MILD_EXTENSION_LOW"
        else:
            stretch = "AT_VALUE"

        return {
            "vwap": round(vwap, 2),
            "sigma": round(sigma, 2),
            "upper_1s": round(vwap + sigma, 2),
            "lower_1s": round(vwap - sigma, 2),
            "upper_2s": round(vwap + 2 * sigma, 2),
            "lower_2s": round(vwap - 2 * sigma, 2),
            "upper_3s": round(vwap + 3 * sigma, 2),
            "lower_3s": round(vwap - 3 * sigma, 2),
            "stretch": stretch,
            "distance_from_vwap_pct": round(((last_price - vwap) / max(vwap, 0.01)) * 100.0, 2)
        }
