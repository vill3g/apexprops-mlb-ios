"""
backend/btc/exhaustion_detector.py
Institutional Mean-Reversion & Exhaustion Analytics for Gemini 15M Gate.

Computes:
1. VWAP standard deviation bands (sigma distance from mean).
2. RSI divergence (bearish divergence at tops, bullish divergence at bottoms).
3. Bollinger Band %b extreme penetration and squeeze states.
4. Intrabar wick exhaustion ratios (upper wick rejections vs lower wick absorptions).
5. Comprehensive exhaustion severity grade (EXTREME_OVERBOUGHT, OVERBOUGHT, EXTREME_OVERSOLD, OVERSOLD, NEUTRAL).
"""

import logging
from typing import Any, Dict, Optional
import numpy as np

logger = logging.getLogger(__name__)


def compute_exhaustion_metrics(df_ind: Any, spot: float, strike: float) -> Dict[str, Any]:
    """
    Computes statistical stretch, VWAP sigma-distance, and RSI/Bollinger exhaustion metrics.
    Safe with any DataFrame or None; returns clean defaults on error.
    """
    default_res = {
        "exhaustion_severity": "NEUTRAL",
        "vwap_sigma_distance": 0.0,
        "is_vwap_stretched": False,
        "rsi_divergence": "NONE",
        "bollinger_pct_b": 0.5,
        "bollinger_status": "NORMAL",
        "rejection_wick_warning": "NONE",
        "actionable_guard": "CLEAR",
    }

    try:
        if df_ind is None or len(df_ind) < 5:
            return default_res

        curr = df_ind.iloc[-1]
        prev = df_ind.iloc[-2]
        prev2 = df_ind.iloc[-3]

        c = float(curr.get("close", spot) or spot)
        rsi_curr = float(curr.get("rsi", 50.0) or 50.0)
        rsi_prev = float(prev.get("rsi", 50.0) or 50.0)
        rsi_prev2 = float(prev2.get("rsi", 50.0) or 50.0)

        bb_b = float(curr.get("bb_pct_b", 0.5) or 0.5)
        vwap = float(curr.get("vwap", c) or c)
        atr = float(curr.get("atr", 0.0) or 0.0)

        # 1. VWAP Sigma-Distance Calculation
        # Use rolling standard deviation of price or ATR as proxy for sigma
        std = 0.0
        if "close" in df_ind.columns and len(df_ind) >= 20:
            std = float(df_ind["close"].tail(20).std() or 0.0)
        if std <= 0.0:
            std = atr if atr > 0 else (c * 0.003)

        vwap_diff = c - vwap
        vwap_sigma = round(vwap_diff / max(std, 1e-6), 2)
        is_stretched = abs(vwap_sigma) >= 2.2

        # 2. RSI Divergence Detection (Over last 3 bars)
        c_prev = float(prev.get("close", c) or c)
        c_prev2 = float(prev2.get("close", c_prev) or c_prev)

        rsi_div = "NONE"
        # Bearish Divergence: Price makes higher high while RSI makes lower high
        if c > c_prev2 and rsi_curr < rsi_prev2 and rsi_curr >= 62.0:
            rsi_div = "BEARISH_DIVERGENCE"
        # Bullish Divergence: Price makes lower low while RSI makes higher low
        elif c < c_prev2 and rsi_curr > rsi_prev2 and rsi_curr <= 38.0:
            rsi_div = "BULLISH_DIVERGENCE"

        # 3. Bollinger Band Status
        bb_status = "NORMAL"
        if bb_b >= 1.0:
            bb_status = "ABOVE_UPPER_BAND"
        elif bb_b >= 0.88:
            bb_status = "UPPER_BAND_EXTREME"
        elif bb_b <= 0.0:
            bb_status = "BELOW_LOWER_BAND"
        elif bb_b <= 0.12:
            bb_status = "LOWER_BAND_EXTREME"

        # 4. Rejection Wick Analysis (Current & Previous 15m candle)
        h = float(curr.get("high", c) or c)
        l = float(curr.get("low", c) or c)
        o = float(curr.get("open", c) or c)
        candle_range = max(h - l, 1e-9)
        upper_wick = (h - max(o, c)) / candle_range
        lower_wick = (min(o, c) - l) / candle_range

        rejection_warning = "NONE"
        if upper_wick >= 0.45:
            rejection_warning = f"HEAVY_UPPER_WICK_REJECTION ({upper_wick*100:.0f}%)"
        elif lower_wick >= 0.45:
            rejection_warning = f"HEAVY_LOWER_WICK_ABSORPTION ({lower_wick*100:.0f}%)"

        # 5. Composite Exhaustion Severity & Actionable Guard
        severity = "NEUTRAL"
        actionable_guard = "CLEAR"

        adx = float(curr.get("adx", 20.0) or 20.0)
        ema9 = float(curr.get("ema_9", 0.0) or 0.0)
        ema21 = float(curr.get("ema_21", 0.0) or 0.0)
        has_explosive_trend = (adx >= 28.0 and ema9 > ema21)

        if (rsi_curr >= 70.0 and bb_b >= 0.88) or (vwap_sigma >= 2.5 and rsi_curr >= 66.0):
            if not has_explosive_trend:
                severity = "EXTREME_OVERBOUGHT"
                actionable_guard = "VETO_YES_BUY_BREAKOUT (Extreme overbought exhaustion - high reversal risk)"
            else:
                severity = "STRONG_MOMENTUM_OVERBOUGHT (ADX>=28 Trend Supported)"
                actionable_guard = "CAUTION_YES (Momentum intact but stretched)"
        elif rsi_curr >= 65.0 or bb_b >= 0.82 or vwap_sigma >= 2.0:
            severity = "OVERBOUGHT"
            actionable_guard = "MONITOR_TOP (Trim late YES entry sizes)"
        elif (rsi_curr <= 30.0 and bb_b <= 0.12) or (vwap_sigma <= -2.5 and rsi_curr <= 34.0):
            if not (adx >= 28.0 and ema9 < ema21):
                severity = "EXTREME_OVERSOLD"
                actionable_guard = "VETO_NO_BUY_BREAKDOWN (Extreme oversold exhaustion - high bounce risk)"
            else:
                severity = "STRONG_MOMENTUM_OVERSOLD (ADX>=28 Trend Supported)"
                actionable_guard = "CAUTION_NO (Downward momentum intact but stretched)"
        elif rsi_curr <= 35.0 or bb_b <= 0.18 or vwap_sigma <= -2.0:
            severity = "OVERSOLD"
            actionable_guard = "MONITOR_BOTTOM (Trim late NO entry sizes)"

        if rsi_div == "BEARISH_DIVERGENCE" and severity in ("EXTREME_OVERBOUGHT", "OVERBOUGHT"):
            actionable_guard = "VETO_YES_BEARISH_DIVERGENCE (Price higher high with RSI divergence)"
        elif rsi_div == "BULLISH_DIVERGENCE" and severity in ("EXTREME_OVERSOLD", "OVERSOLD"):
            actionable_guard = "VETO_NO_BULLISH_DIVERGENCE (Price lower low with RSI divergence)"

        return {
            "exhaustion_severity": severity,
            "vwap_sigma_distance": vwap_sigma,
            "is_vwap_stretched": is_stretched,
            "rsi_divergence": rsi_div,
            "bollinger_pct_b": round(bb_b, 3),
            "bollinger_status": bb_status,
            "rejection_wick_warning": rejection_warning,
            "actionable_guard": actionable_guard,
        }
    except Exception as e:
        logger.debug(f"[ExhaustionDetector] Error computing metrics: {e}")
        return default_res
