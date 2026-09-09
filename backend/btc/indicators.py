"""
Technical Indicators & Momentum Calculations for 15-Minute Bitcoin Analysis.
Includes EMAs (9, 21, 50, 200), RSI (14) with Bullish/Bearish Divergence,
MACD (12, 26, 9), Bollinger Bands (20, 2), ATR (14), and Volume Surge detection.
"""

import numpy as np
import pandas as pd


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index (RSI) using Wilder's smoothing."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Calculate MACD Line, Signal Line, and Histogram."""
    ema_fast = compute_ema(series, fast)
    ema_slow = compute_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = compute_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0):
    """Calculate Bollinger Bands and Bandwidth."""
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    bandwidth = (upper - lower) / (sma + 1e-10)
    return upper, sma, lower, bandwidth


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range (ATR)."""
    high = df["high"]
    low = df["low"]
    close_prev = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return atr


def detect_rsi_divergences(df: pd.DataFrame, lookback: int = 25) -> list[dict]:
    """
    Detect regular bullish and bearish RSI divergences.
    - Bullish: Price Lower Low while RSI Higher Low (in oversold/rebound territory < 45).
    - Bearish: Price Higher High while RSI Lower High (in overbought/toppy territory > 55).
    """
    divergences = []
    n = len(df)
    if n < lookback + 5:
        return divergences

    # Inspect the last few candles (indices n-1, n-2) against previous swing points in lookback
    curr_idx = n - 1
    curr_low = df.loc[curr_idx, "low"]
    curr_high = df.loc[curr_idx, "high"]
    curr_rsi = df.loc[curr_idx, "rsi"]

    start_idx = max(0, curr_idx - lookback)

    # Search for regular Bullish Divergence:
    # Find minimum price in lookback (excluding the latest 2 candles)
    prev_low_slice = df.loc[start_idx : curr_idx - 3, "low"]
    if not prev_low_slice.empty:
        prev_low_idx = prev_low_slice.idxmin()
        prev_low = df.loc[prev_low_idx, "low"]
        prev_rsi = df.loc[prev_low_idx, "rsi"]

        if curr_low < prev_low and curr_rsi > prev_rsi and curr_rsi < 45 and (curr_idx - prev_low_idx) >= 3:
            divergences.append({
                "type": "BULLISH_RSI_DIVERGENCE",
                "curr_idx": curr_idx,
                "prev_idx": int(prev_low_idx),
                "price_low_curr": curr_low,
                "price_low_prev": prev_low,
                "rsi_curr": round(curr_rsi, 2),
                "rsi_prev": round(prev_rsi, 2),
                "description": f"Price made Lower Low ({curr_low:.1f} < {prev_low:.1f}) but RSI made Higher Low ({curr_rsi:.1f} > {prev_rsi:.1f})"
            })

    # Search for regular Bearish Divergence:
    prev_high_slice = df.loc[start_idx : curr_idx - 3, "high"]
    if not prev_high_slice.empty:
        prev_high_idx = prev_high_slice.idxmax()
        prev_high = df.loc[prev_high_idx, "high"]
        prev_rsi = df.loc[prev_high_idx, "rsi"]

        if curr_high > prev_high and curr_rsi < prev_rsi and curr_rsi > 55 and (curr_idx - prev_high_idx) >= 3:
            divergences.append({
                "type": "BEARISH_RSI_DIVERGENCE",
                "curr_idx": curr_idx,
                "prev_idx": int(prev_high_idx),
                "price_high_curr": curr_high,
                "price_high_prev": prev_high,
                "rsi_curr": round(curr_rsi, 2),
                "rsi_prev": round(prev_rsi, 2),
                "description": f"Price made Higher High ({curr_high:.1f} > {prev_high:.1f}) but RSI made Lower High ({curr_rsi:.1f} < {prev_rsi:.1f})"
            })

    return divergences


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Append all technical indicators to the DataFrame.
    """
    df = df.copy()

    # Moving Averages
    df["ema_9"] = compute_ema(df["close"], 9)
    df["ema_21"] = compute_ema(df["close"], 21)
    df["ema_50"] = compute_ema(df["close"], 50)
    df["ema_200"] = compute_ema(df["close"], 200)

    # RSI
    df["rsi"] = compute_rsi(df["close"], 14)

    # MACD
    macd_line, signal_line, histogram = compute_macd(df["close"], 12, 26, 9)
    df["macd_line"] = macd_line
    df["macd_signal"] = signal_line
    df["macd_hist"] = histogram

    # Bollinger Bands
    upper, middle, lower, bandwidth = compute_bollinger_bands(df["close"], 20, 2.0)
    df["bb_upper"] = upper
    df["bb_middle"] = middle
    df["bb_lower"] = lower
    df["bb_bandwidth"] = bandwidth
    # 50-candle lowest 20% quantile for squeeze detection
    df["bb_squeeze"] = df["bb_bandwidth"] < df["bb_bandwidth"].rolling(50, min_periods=20).quantile(0.20)

    # ATR
    df["atr"] = compute_atr(df, 14)

    # Volume
    df["vol_sma"] = df["volume"].rolling(20, min_periods=5).mean()
    df["vol_ratio"] = df["volume"] / (df["vol_sma"] + 1e-10)
    df["vol_surge"] = df["vol_ratio"] >= 1.5

    return df


def extract_indicator_summary(df: pd.DataFrame) -> dict:
    """
    Extract a clean status summary of the latest candle's indicators.
    """
    if df.empty or len(df) < 5:
        return {}

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Trend ribbon
    bullish_ribbon = (last["ema_9"] > last["ema_21"] > last["ema_50"])
    bearish_ribbon = (last["ema_9"] < last["ema_21"] < last["ema_50"])
    macro_bull = last["close"] > last["ema_200"] if not pd.isna(last["ema_200"]) else None

    # EMA crossover
    ema_cross = None
    if prev["ema_9"] <= prev["ema_21"] and last["ema_9"] > last["ema_21"]:
        ema_cross = "BULLISH_CROSS"
    elif prev["ema_9"] >= prev["ema_21"] and last["ema_9"] < last["ema_21"]:
        ema_cross = "BEARISH_CROSS"

    # RSI condition
    rsi_val = float(last["rsi"]) if not pd.isna(last["rsi"]) else 50.0
    rsi_status = "OVERSOLD" if rsi_val <= 30 else ("OVERBOUGHT" if rsi_val >= 70 else "NEUTRAL")

    # Divergences
    divergences = detect_rsi_divergences(df)

    # MACD crossover
    macd_cross = None
    if prev["macd_line"] <= prev["macd_signal"] and last["macd_line"] > last["macd_signal"]:
        macd_cross = "BULLISH_CROSS"
    elif prev["macd_line"] >= prev["macd_signal"] and last["macd_line"] < last["macd_signal"]:
        macd_cross = "BEARISH_CROSS"

    macd_hist_direction = "EXPANDING_UP" if last["macd_hist"] > prev["macd_hist"] else "EXPANDING_DOWN"

    return {
        "price": float(last["close"]),
        "ema_9": float(last["ema_9"]),
        "ema_21": float(last["ema_21"]),
        "ema_50": float(last["ema_50"]),
        "ema_200": float(last["ema_200"]) if not pd.isna(last["ema_200"]) else None,
        "bullish_ribbon": bool(bullish_ribbon),
        "bearish_ribbon": bool(bearish_ribbon),
        "macro_bull": macro_bull,
        "ema_cross": ema_cross,
        "rsi": round(rsi_val, 2),
        "rsi_status": rsi_status,
        "divergences": divergences,
        "macd_line": round(float(last["macd_line"]), 2),
        "macd_signal": round(float(last["macd_signal"]), 2),
        "macd_hist": round(float(last["macd_hist"]), 2),
        "macd_cross": macd_cross,
        "macd_hist_direction": macd_hist_direction,
        "bb_upper": round(float(last["bb_upper"]), 2),
        "bb_lower": round(float(last["bb_lower"]), 2),
        "bb_squeeze": bool(last["bb_squeeze"]),
        "atr": round(float(last["atr"]), 2),
        "volume": round(float(last["volume"]), 4),
        "vol_ratio": round(float(last["vol_ratio"]), 2),
        "vol_surge": bool(last["vol_surge"]),
    }


if __name__ == "__main__":
    from data_fetcher import fetch_15m_candles
    df = fetch_15m_candles(limit=250)
    df = add_all_indicators(df)
    summary = extract_indicator_summary(df)
    print("Indicator Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
