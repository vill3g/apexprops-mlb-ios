
import logging

logger = logging.getLogger(__name__)
import os
import threading
from typing import Any, Dict, Optional

import pandas as pd

try:
    pass
except ImportError:
    pass
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data")
HISTORY_FILE = os.path.join(DATA_DIR, "trades_history.json")
CONFIG_FILE = os.path.join(DATA_DIR, "trading_config.json")

# Cross-process (web server + worker) and re-entrant: see backend/btc/proc_lock.py (audit H4).
from backend.btc.proc_lock import ReentrantProcessLock

_history_lock = ReentrantProcessLock("owner_trades_history")
_saas_candle_cache: dict = {}
_saas_candle_cache_lock = threading.Lock()
_SAAS_CANDLE_TTL = 8.0
_saas_users_cache: dict = {"ts": 0.0, "users": None}
_saas_users_cache_lock = threading.Lock()
_SAAS_USERS_TTL = 15.0
_user_trader_cache: dict = {}
_user_trader_cache_lock = threading.Lock()
_user_last_traded_cache: dict = {}
_user_last_traded_lock = threading.Lock()

from backend.btc import liquidation_stream


def classify_auto_regime(df_ind: Optional[pd.DataFrame], sec_left: Optional[float] = None) -> Dict[str, Any]:
    """
    Auto 2.0: Adaptive Market Regime Classification Engine.
    Dynamically maps current market microstructure, volatility, and trend conditions
    into one of 4 optimal execution styles, eliminating negative-expectancy chop bleed:

    1. STRONG_MOMENTUM -> MOMENTUM_SURFER
       Triggered when massive liquidation cascades ($1.5M+) occur or volume + ADX confirm
       a runaway breakout wave (Vol Ratio >= 1.4, ADX >= 25, |RSI - 50| >= 8) or MTF trend alignment.
    2. SQUEEZE_BREAKOUT -> AMBUSH
       Triggered when Bollinger Band compression (BBW < 0.020) erupts into volume expansion
       (Vol Ratio >= 1.25) and price crosses bands or expands range.
    3. TREND_CONTINUATION -> SNIPER
       Triggered during steady structural trends with healthy volume (ADX >= 20, |RSI - 50| >= 5,
       Vol Ratio >= 0.9).
    4. CHOP_DEADZONE -> CAPITAL_GUARD
       When market is in an ultra-low volatility deadzone (ADX < 18, Vol Ratio < 0.85, BBW < 0.018),
       emits a disciplined PASS recommendation to preserve capital instead of naive band fading.
    """
    if df_ind is None or len(df_ind) == 0:
        return {
            "style": "SNIPER",
            "regime": "DEFAULT_FALLBACK",
            "reason": "Insufficient candle data for regime detection",
            "metrics": {
                "vol_ratio": 1.0,
                "bb_width": 1.0,
                "adx": 20.0,
                "rsi": 50.0,
                "liq_total": 0.0,
                "trend_1h": "NEUTRAL",
            }
        }

    curr = df_ind.iloc[-1]
    try:
        vr_raw = curr.get("vol_ratio", 1.0)
        vol_ratio = float(vr_raw) if vr_raw is not None and not pd.isna(vr_raw) else 1.0
    except (ValueError, TypeError):
        vol_ratio = 1.0

    try:
        bb_raw = curr.get("bb_bandwidth", 1.0)
        bb_width = float(bb_raw) if bb_raw is not None and not pd.isna(bb_raw) else 1.0
    except (ValueError, TypeError):
        bb_width = 1.0

    try:
        adx_raw = curr.get("adx", 20.0)
        adx = float(adx_raw) if adx_raw is not None and not pd.isna(adx_raw) else 20.0
    except (ValueError, TypeError):
        adx = 20.0

    try:
        rsi_raw = curr.get("rsi", 50.0)
        rsi = float(rsi_raw) if rsi_raw is not None and not pd.isna(rsi_raw) else 50.0
    except (ValueError, TypeError):
        rsi = 50.0

    try:
        close = float(curr.get("close", 0.0) or 0.0)
        open_val = float(curr.get("open", 0.0) or 0.0)
        high = float(curr.get("high", 0.0) or 0.0)
        low = float(curr.get("low", 0.0) or 0.0)
        atr = float(curr.get("atr", 100.0) or 100.0)
        bb_upper = float(curr.get("bb_upper", high) or high)
        bb_lower = float(curr.get("bb_lower", low) or low)
    except (ValueError, TypeError):
        close = open_val = high = low = bb_upper = bb_lower = 0.0
        atr = 100.0

    # 1. Real-time liquidation metrics
    liq_total = 0.0
    try:
        liq = liquidation_stream.get_liquidation_imbalance()
        liq_total = float(liq.get("short_liquidations_usd", 0.0) + liq.get("long_liquidations_usd", 0.0))
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, ValueError, TypeError) as e:
        logger.warning(f"Error fetching liquidation imbalance: {e}")
        liq_total = 0.0

    # 2. 1-Hour Macro Trend Detection from in-memory candle history
    trend_1h = "NEUTRAL"
    try:
        if len(df_ind) >= 30:
            if "datetime" in df_ind.columns:
                dt_col = df_ind["datetime"]
            elif "timestamp" in df_ind.columns:
                dt_col = pd.to_datetime(df_ind["timestamp"], unit="s", utc=True)
            elif "time" in df_ind.columns:
                dt_col = pd.to_datetime(df_ind["time"], unit="s", utc=True)
            else:
                dt_col = None
            if dt_col is not None:
                df_temp = df_ind.copy()
                df_temp["_dt_resample"] = pd.to_datetime(dt_col)
                df_1h = df_temp.set_index("_dt_resample").resample("1h").agg({
                    "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
                }).dropna()
                if len(df_1h) >= 4:
                    e9_1h = float(df_1h["close"].ewm(span=9, adjust=False).mean().iloc[-1])
                    e21_1h = float(df_1h["close"].ewm(span=21, adjust=False).mean().iloc[-1])
                    if e9_1h > e21_1h * 1.0005:
                        trend_1h = "BULLISH"
                    elif e9_1h < e21_1h * 0.9995:
                        trend_1h = "BEARISH"
    except (ValueError, TypeError, KeyError, IndexError) as e:
        logger.warning(f"Trend detection failed: {e}")
        trend_1h = "NEUTRAL"

    # Evaluation conditions
    is_liq_cascade = (liq_total >= 1_500_000)
    is_vol_momentum = (vol_ratio >= 1.4 and adx >= 25.0 and abs(rsi - 50.0) >= 8.0)
    is_mtf_aligned_momentum = (
        vol_ratio >= 1.25 and adx >= 24.0 and (
            (trend_1h == "BULLISH" and rsi >= 56.0) or
            (trend_1h == "BEARISH" and rsi <= 44.0)
        )
    )

    is_bb_squeeze = (bb_width < 0.020)
    price_outside_bands = (close > bb_upper or close < bb_lower)
    candle_expansion = (abs(close - open_val) >= 0.7 * atr)
    is_squeeze_breakout = (is_bb_squeeze and vol_ratio >= 1.25 and (price_outside_bands or candle_expansion))
    is_pure_breakout = (vol_ratio >= 1.35 and (price_outside_bands or candle_expansion))

    is_chop_deadzone = (
        (adx < 18.0 and vol_ratio < 0.85 and bb_width < 0.018) or
        (adx < 16.0 and vol_ratio < 0.90)
    )

    is_trend_continuation = (adx >= 20.0 and abs(rsi - 50.0) >= 5.0 and vol_ratio >= 0.9)

    # Classification Hierarchy
    if is_liq_cascade or is_vol_momentum or is_mtf_aligned_momentum:
        style = "MOMENTUM_SURFER"
        regime = "STRONG_MOMENTUM"
        reason = f"High velocity trend / liquidation cascade (Vol: {vol_ratio:.2f}, ADX: {adx:.1f}, Liq: ${liq_total/1e6:.1f}M, 1H: {trend_1h})"
    elif is_squeeze_breakout or is_pure_breakout:
        style = "AMBUSH"
        regime = "SQUEEZE_BREAKOUT"
        reason = f"Squeeze breakout expansion (BBW: {bb_width:.4f}, Vol: {vol_ratio:.2f}, Range Exp: {candle_expansion})"
    elif is_chop_deadzone:
        style = "CAPITAL_GUARD"
        regime = "CHOP_DEADZONE"
        reason = f"Low-volatility compression deadzone (ADX: {adx:.1f} < 18, Vol: {vol_ratio:.2f} < 0.85, BBW: {bb_width:.4f}). Capital Guard active."
    elif is_trend_continuation:
        style = "SNIPER"
        regime = "TREND_CONTINUATION"
        reason = f"Directional trend continuation (ADX: {adx:.1f}, RSI: {rsi:.1f}, Vol: {vol_ratio:.2f})"
    else:
        style = "SNIPER"
        regime = "NORMAL_MARKET"
        reason = f"Standard market regime; routing to disciplined SNIPER confluence (ADX: {adx:.1f}, Vol: {vol_ratio:.2f})"

    return {
        "style": style,
        "regime": regime,
        "reason": reason,
        "metrics": {
            "vol_ratio": round(vol_ratio, 3),
            "bb_width": round(bb_width, 5),
            "adx": round(adx, 2),
            "rsi": round(rsi, 2),
            "liq_total": round(liq_total, 2),
            "trend_1h": trend_1h,
        }
    }

__all__ = [
    "DATA_DIR", "HISTORY_FILE", "CONFIG_FILE",
    "_history_lock", "_saas_candle_cache", "_saas_candle_cache_lock", "_SAAS_CANDLE_TTL",
    "_saas_users_cache", "_saas_users_cache_lock", "_SAAS_USERS_TTL",
    "_user_trader_cache", "_user_trader_cache_lock",
    "_user_last_traded_cache", "_user_last_traded_lock",
    "classify_auto_regime"
]

