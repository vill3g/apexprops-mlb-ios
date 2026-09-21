import logging
logger = logging.getLogger(__name__)
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


def compute_cvd_proxy(df: pd.DataFrame) -> pd.Series:
    """
    Approximates Cumulative Volume Delta (CVD) using candle structure.
    Formula: Volume * ((Close - Open) / (High - Low + epsilon))
    """
    # Use replace(0) then clip to avoid doji candles producing inf/nan in delta
    range_hl = (df["high"] - df["low"]).replace(0, 1e-9)
    range_hl = range_hl.where(range_hl.abs() >= 1e-9, 1e-9)
    delta_proxy = df["volume"] * ((df["close"] - df["open"]) / range_hl)
    return delta_proxy.cumsum()

def detect_rsi_divergences(df: pd.DataFrame, lookback: int = 25) -> list[dict]:
    """
    Detect regular bullish and bearish RSI divergences.
    - Bullish: Price Lower Low while RSI Higher Low (in oversold/rebound territory < 45).
    - Bearish: Price Higher High while RSI Lower High (in overbought/toppy territory > 55).
    """
    divergences = []
    if df is None or len(df) == 0:
        return divergences
    df = df.reset_index(drop=True)
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

        if curr_low < prev_low and curr_rsi > prev_rsi and curr_rsi < 45 and prev_rsi < 45 and (curr_idx - prev_low_idx) >= 3:
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

        if curr_high > prev_high and curr_rsi < prev_rsi and curr_rsi > 55 and prev_rsi > 55 and (curr_idx - prev_high_idx) >= 3:
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


def detect_cvd_divergences(df: pd.DataFrame, lookback: int = 25) -> list[dict]:
    """
    Detect CVD (Cumulative Volume Delta) divergences against price action.
    Bullish Divergence: Price making Lower Lows, but CVD making Higher Lows.
    Bearish Divergence: Price making Higher Highs, but CVD making Lower Highs.
    """
    divs = []
    if len(df) < lookback + 5 or "cvd" not in df.columns:
        return divs
        
    window = df.tail(lookback)
    p_highs, p_lows = window["high"].values, window["low"].values
    c_vals = window["cvd"].values
    
    # Bearish CVD Divergence (Price HH, CVD LH)
    if p_highs[-1] >= max(p_highs[:-1]) and c_vals[-1] < max(c_vals[:-1]):
        divs.append({
            "type": "BEARISH_CVD_DIVERGENCE",
            "description": "Price pushing to local highs but aggressive Volume Delta (CVD) is dropping (Fakeout up)"
        })
        
    # Bullish CVD Divergence (Price LL, CVD HL)
    if p_lows[-1] <= min(p_lows[:-1]) and c_vals[-1] > min(c_vals[:-1]):
        divs.append({
            "type": "BULLISH_CVD_DIVERGENCE",
            "description": "Price pushing to local lows but aggressive Volume Delta (CVD) is rising (Absorption)"
        })
        
    return divs


def compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    import numpy as np
    h = high.values
    l = low.values
    c = close.values
    
    plus_dm = h[1:] - h[:-1]
    minus_dm = l[:-1] - l[1:]
    
    plus_dm_arr = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm_arr = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
    
    tr1 = h[1:] - l[1:]
    tr2 = np.abs(h[1:] - c[:-1])
    tr3 = np.abs(l[1:] - c[:-1])
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    
    plus_dm_arr = np.concatenate([[0.0], plus_dm_arr])
    minus_dm_arr = np.concatenate([[0.0], minus_dm_arr])
    tr = np.concatenate([[0.0], tr])
    
    def smooth(data, win):
        res = np.zeros_like(data)
        if len(data) > win:
            res[win] = np.sum(data[1:win+1])
            for i in range(win+1, len(data)):
                res[i] = res[i-1] - (res[i-1]/win) + data[i]
        return res
        
    atr = smooth(tr, window)
    plus_di = 100 * smooth(plus_dm_arr, window) / np.where(atr == 0, 1, atr)
    minus_di = 100 * smooth(minus_dm_arr, window) / np.where(atr == 0, 1, atr)
    
    dx = 100 * np.abs(plus_di - minus_di) / np.where((plus_di + minus_di) == 0, 1, (plus_di + minus_di))
    adx = smooth(dx, window)
    
    return pd.Series(adx, index=high.index)

def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Append all technical indicators to the DataFrame.
    """
    df = df.copy()

    df["adx"] = compute_adx(df["high"], df["low"], df["close"], 14)

    # C4 FIX: Rate of Change indicators (were never computed, always 0.0)
    df["roc_15m"] = df["close"].pct_change(1) * 100   # 1-candle = 15 minutes
    df["roc_1h"] = df["close"].pct_change(4) * 100    # 4 candles = 1 hour
    df["roc_4h"] = df["close"].pct_change(16) * 100   # 16 candles = 4 hours

    # Moving Averages
    df["ema_9"] = compute_ema(df["close"], 9)
    df["ema_21"] = compute_ema(df["close"], 21)
    df["ema_50"] = compute_ema(df["close"], 50)
    df["ema_200"] = compute_ema(df["close"], 200)

    # RSI
    df["rsi"] = compute_rsi(df["close"], 14)
    df["rsi_224"] = compute_rsi(df["close"], 224)

    # MACD
    macd_line, signal_line, histogram = compute_macd(df["close"], 12, 26, 9)
    df["macd_line"] = macd_line
    df["macd_signal"] = signal_line
    df["macd_hist"] = histogram
    df["macd_hist_momentum"] = df["macd_hist"] - df["macd_hist"].shift(1).fillna(0)

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

    # VWAP
    df["vwap"] = compute_vwap(df)
    
    # CVD Proxy
    df["cvd"] = compute_cvd_proxy(df)
    df["cvd_acceleration"] = compute_cvd_acceleration(df)
    
    # Point of Control (POC)
    df["poc"] = compute_trailing_poc(df)

    return df


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    """Calculate Intraday Session (Daily) Volume Weighted Average Price (VWAP)."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    vol_price = typical_price * df["volume"]
    
    # We need a date column to group by. If 'timestamp' exists and is datetime, use it.
    if pd.api.types.is_datetime64_any_dtype(df.index):
        dates = df.index.date
    elif "datetime" in df.columns:
        dates = pd.to_datetime(df["datetime"]).dt.date
    else:
        # Fallback to cumulative if no datetime available
        cum_vol_price = vol_price.cumsum()
        cum_vol = df["volume"].cumsum().replace(0, np.nan)
        return cum_vol_price / cum_vol
        
    vwap = vol_price.groupby(dates).cumsum() / (df["volume"].groupby(dates).cumsum() + 1e-10)
    return vwap

def compute_atr_percentile(df: pd.DataFrame, period: int = 14, lookback: int = 100) -> float:
    """Calculates the current ATR as a percentile of its recent history (volatility regime)."""
    if "atr" not in df.columns:
        df["atr"] = compute_atr(df, period)
    
    if len(df) < lookback:
        return 50.0  # default middle ground
        
    recent_atrs = df["atr"].dropna().tail(lookback)
    if recent_atrs.empty:
        return 50.0
        
    current_atr = recent_atrs.iloc[-1]
    percentile = (recent_atrs < current_atr).mean() * 100.0
    return round(percentile, 1)


def detect_fair_value_gaps(df: pd.DataFrame, min_gap_pct: float = 0.03) -> list[dict]:
    """
    Detect Fair Value Gaps (FVG) / Imbalances on 3-candle sequences.
    - Bullish FVG: Candle 1 High < Candle 3 Low
    - Bearish FVG: Candle 1 Low > Candle 3 High
    """
    fvgs = []
    n = len(df)
    if n < 5:
        return fvgs

    for i in range(max(2, n - 20), n):
        c1 = df.iloc[i - 2]
        c2 = df.iloc[i - 1]
        c3 = df.iloc[i]

        if c3["low"] > c1["high"]:
            gap_size = c3["low"] - c1["high"]
            gap_pct = (gap_size / (c1["high"] + 1e-10)) * 100
            if gap_pct >= min_gap_pct:
                fvgs.append({
                    "type": "BULLISH_FVG",
                    "top": round(float(c3["low"]), 2),
                    "bottom": round(float(c1["high"]), 2),
                    "size": round(float(gap_size), 2),
                    "candle_index": i - 1,
                    "time": int(c2.get("time", 0)),
                    "description": f"Bullish FVG between ${c1['high']:.1f} and ${c3['low']:.1f} (+${gap_size:.1f})"
                })
        elif c1["low"] > c3["high"]:
            gap_size = c1["low"] - c3["high"]
            gap_pct = (gap_size / (c1["low"] + 1e-10)) * 100
            if gap_pct >= min_gap_pct:
                fvgs.append({
                    "type": "BEARISH_FVG",
                    "top": round(float(c1["low"]), 2),
                    "bottom": round(float(c3["high"]), 2),
                    "size": round(float(gap_size), 2),
                    "candle_index": i - 1,
                    "time": int(c2.get("time", 0)),
                    "description": f"Bearish FVG between ${c3['high']:.1f} and ${c1['low']:.1f} (-${gap_size:.1f})"
                })
    return fvgs


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
    cvd_divergences = detect_cvd_divergences(df)

    # MACD crossover
    macd_cross = None
    if prev["macd_line"] <= prev["macd_signal"] and last["macd_line"] > last["macd_signal"]:
        macd_cross = "BULLISH_CROSS"
    elif prev["macd_line"] >= prev["macd_signal"] and last["macd_line"] < last["macd_signal"]:
        macd_cross = "BEARISH_CROSS"

    macd_hist_direction = "EXPANDING_UP" if last["macd_hist"] > prev["macd_hist"] else "EXPANDING_DOWN"

    atr_percentile = compute_atr_percentile(df)

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
        "cvd_divergences": cvd_divergences,
        "macd_line": round(float(last["macd_line"]), 2),
        "macd_signal": round(float(last["macd_signal"]), 2),
        "macd_hist": round(float(last["macd_hist"]), 2),
        "macd_cross": macd_cross,
        "macd_hist_direction": macd_hist_direction,
        "bb_upper": round(float(last["bb_upper"]), 2),
        "bb_lower": round(float(last["bb_lower"]), 2),
        "bb_squeeze": bool(last["bb_squeeze"]),
        "atr": round(float(last["atr"]), 2),
        "atr_percentile": atr_percentile,
        "volume": round(float(last["volume"]), 4),
        "vol_ratio": round(float(last["vol_ratio"]), 2),
        "vol_surge": bool(last["vol_surge"]),
        "vwap": round(float(last["vwap"]), 2) if "vwap" in last and not pd.isna(last["vwap"]) else None,
        "vwap_status": "ABOVE_VWAP" if ("vwap" in last and last["close"] >= last["vwap"]) else "BELOW_VWAP",
        "fvgs": detect_fair_value_gaps(df),
        "cvd_acceleration": round(float(last["cvd_acceleration"]), 2) if "cvd_acceleration" in last and not pd.isna(last["cvd_acceleration"]) else 0.0,
        "poc": round(float(last["poc"]), 2) if "poc" in last and not pd.isna(last["poc"]) else None,
    }

def compute_cvd_acceleration(df: pd.DataFrame) -> pd.Series:
    range_hl = (df["high"] - df["low"]).replace(0, 1e-9)
    delta_proxy = df["volume"] * ((df["close"] - df["open"]) / range_hl)
    return delta_proxy.rolling(3).sum()

def compute_trailing_poc(df: pd.DataFrame, window: int = 96) -> pd.Series:
    import numpy as np
    pocs = np.zeros(len(df))
    close_vals = df['close'].values
    high_vals = df['high'].values
    low_vals = df['low'].values
    vol_vals = df['volume'].values
    typ_price = (high_vals + low_vals + close_vals) / 3.0
    
    for i in range(len(df)):
        if i < 10:
            pocs[i] = close_vals[i]
            continue
            
        start = max(0, i - window + 1)
        sub_high = high_vals[start:i+1]
        sub_low = low_vals[start:i+1]
        sub_typ = typ_price[start:i+1]
        sub_vol = vol_vals[start:i+1]
        
        min_p = np.min(sub_low)
        max_p = np.max(sub_high)
        
        if min_p == max_p:
            pocs[i] = min_p
            continue
            
        bins = np.linspace(min_p, max_p, 50)
        idx = np.digitize(sub_typ, bins) - 1
        idx = np.clip(idx, 0, 48)
        
        vol_profile = np.bincount(idx, weights=sub_vol, minlength=49)
        poc_idx = np.argmax(vol_profile)
        pocs[i] = (bins[poc_idx] + bins[poc_idx+1]) / 2.0
        
    return pd.Series(pocs, index=df.index) 

if __name__ == "__main__":
    from data_fetcher import fetch_15m_candles
    df = fetch_15m_candles(limit=250)
    df = add_all_indicators(df)
    summary = extract_indicator_summary(df)
    logger.info("Indicator Summary:")
    for k, v in summary.items():
        logger.info(f"  {k}: {v}")
