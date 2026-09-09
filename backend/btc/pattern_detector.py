"""
Candlestick Pattern & Market Structure Detector for 15-Minute Bitcoin Candles.
Detects single/multi-candle patterns, swing pivots, Market Structure (BOS, CHoCH, HH/HL),
Support/Resistance clusters, and Double Tops/Bottoms.
"""

import numpy as np
import pandas as pd


def detect_candlestick_patterns(df: pd.DataFrame) -> list[dict]:
    """
    Scans the latest 1-3 candles in the DataFrame for high-significance candlestick patterns.
    Returns a list of detected pattern dicts with:
      - name: e.g. "Bullish Engulfing"
      - type: "BULLISH" | "BEARISH" | "NEUTRAL"
      - strength: 1 to 3 (1=mild, 2=moderate, 3=strong)
      - description: readable explanation
      - candle_index: index of the triggering candle
    """
    patterns = []
    n = len(df)
    if n < 5:
        return patterns

    curr = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3]

    curr_body = abs(curr["close"] - curr["open"])
    curr_range = curr["high"] - curr["low"] + 1e-10
    curr_is_green = curr["close"] >= curr["open"]
    curr_upper_wick = curr["high"] - max(curr["close"], curr["open"])
    curr_lower_wick = min(curr["close"], curr["open"]) - curr["low"]

    prev_body = abs(prev["close"] - prev["open"])
    prev_range = prev["high"] - prev["low"] + 1e-10
    prev_is_green = prev["close"] >= prev["open"]

    prev2_body = abs(prev2["close"] - prev2["open"])
    prev2_is_green = prev2["close"] >= prev2["open"]

    avg_body = df["close"].sub(df["open"]).abs().tail(20).mean()

    # 1. Bullish Engulfing
    if (not prev_is_green) and curr_is_green and (curr["close"] >= prev["open"]) and (curr["open"] <= prev["close"]):
        if curr_body > avg_body * 0.8:
            patterns.append({
                "name": "Bullish Engulfing",
                "type": "BULLISH",
                "strength": 3,
                "description": "Strong green candle completely engulfed the previous red candle's body.",
                "candle_index": n - 1
            })

    # 2. Bearish Engulfing
    if prev_is_green and (not curr_is_green) and (curr["open"] >= prev["close"]) and (curr["close"] <= prev["open"]):
        if curr_body > avg_body * 0.8:
            patterns.append({
                "name": "Bearish Engulfing",
                "type": "BEARISH",
                "strength": 3,
                "description": "Strong red candle completely engulfed the previous green candle's body.",
                "candle_index": n - 1
            })

    # 3. Hammer (Bullish Pin Bar)
    # Lower wick >= 2x body, small upper wick <= 25% range, body in top 35% of candle
    if curr_lower_wick >= (curr_body * 2.0) and curr_upper_wick <= (curr_range * 0.25) and curr_body > (curr_range * 0.1):
        patterns.append({
            "name": "Hammer (Bullish Pin Bar)",
            "type": "BULLISH",
            "strength": 2,
            "description": f"Long lower rejection wick ({curr_lower_wick:.1f} pts) indicates aggressive buyers stepping in.",
            "candle_index": n - 1
        })

    # 4. Shooting Star (Bearish Pin Bar)
    # Upper wick >= 2x body, small lower wick <= 25% range, body in bottom 35% of candle
    if curr_upper_wick >= (curr_body * 2.0) and curr_lower_wick <= (curr_range * 0.25) and curr_body > (curr_range * 0.1):
        patterns.append({
            "name": "Shooting Star (Bearish Pin Bar)",
            "type": "BEARISH",
            "strength": 2,
            "description": f"Long upper rejection wick ({curr_upper_wick:.1f} pts) indicates aggressive sellers rejecting highs.",
            "candle_index": n - 1
        })

    # 5. Inverted Hammer (at potential bottom)
    if curr_upper_wick >= (curr_body * 2.0) and curr_lower_wick <= (curr_range * 0.15) and not prev_is_green:
        patterns.append({
            "name": "Inverted Hammer",
            "type": "BULLISH",
            "strength": 2,
            "description": "Buyers tested higher prices following a downward move, setting up reversal.",
            "candle_index": n - 1
        })

    # 6. Hanging Man (at potential top)
    if curr_lower_wick >= (curr_body * 2.0) and curr_upper_wick <= (curr_range * 0.15) and prev_is_green:
        patterns.append({
            "name": "Hanging Man",
            "type": "BEARISH",
            "strength": 1,
            "description": "Sellers pushed price sharply down during the session before a late recovery.",
            "candle_index": n - 1
        })

    # 7. Morning Star (Bullish Reversal 3-bar)
    if (not prev2_is_green) and prev2_body > avg_body * 0.7:
        if prev_body < avg_body * 0.5:  # small middle star
            if curr_is_green and curr["close"] > (prev2["open"] + prev2["close"]) / 2:
                patterns.append({
                    "name": "Morning Star",
                    "type": "BULLISH",
                    "strength": 3,
                    "description": "Classic 3-candle bullish reversal: strong selloff -> pause -> strong green surge.",
                    "candle_index": n - 1
                })

    # 8. Evening Star (Bearish Reversal 3-bar)
    if prev2_is_green and prev2_body > avg_body * 0.7:
        if prev_body < avg_body * 0.5:
            if (not curr_is_green) and curr["close"] < (prev2["open"] + prev2["close"]) / 2:
                patterns.append({
                    "name": "Evening Star",
                    "type": "BEARISH",
                    "strength": 3,
                    "description": "Classic 3-candle bearish reversal: strong rally -> pause -> strong red drop.",
                    "candle_index": n - 1
                })

    # 9. Three White Soldiers (Strong Bullish Continuation)
    if n >= 4:
        c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
        if (c1["close"] > c1["open"] and c2["close"] > c2["open"] and c3["close"] > c3["open"] and
                c3["close"] > c2["close"] > c1["close"] and
                c3["open"] > c2["open"] > c1["open"]):
            patterns.append({
                "name": "Three White Soldiers",
                "type": "BULLISH",
                "strength": 3,
                "description": "Three consecutive advancing green candles with higher highs and higher closes.",
                "candle_index": n - 1
            })

    # 10. Three Black Crows (Strong Bearish Continuation)
    if n >= 4:
        c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
        if (c1["close"] < c1["open"] and c2["close"] < c2["open"] and c3["close"] < c3["open"] and
                c3["close"] < c2["close"] < c1["close"] and
                c3["open"] < c2["open"] < c1["open"]):
            patterns.append({
                "name": "Three Black Crows",
                "type": "BEARISH",
                "strength": 3,
                "description": "Three consecutive declining red candles with lower lows and lower closes.",
                "candle_index": n - 1
            })

    # 11. Tweezer Bottom (Identical lows at support)
    if abs(curr["low"] - prev["low"]) / (curr["close"] + 1e-10) < 0.0008:
        if (not prev_is_green) and curr_is_green:
            patterns.append({
                "name": "Tweezer Bottom",
                "type": "BULLISH",
                "strength": 2,
                "description": f"Dual candle rejection at identical low level ({curr['low']:.1f}).",
                "candle_index": n - 1
            })

    # 12. Tweezer Top (Identical highs at resistance)
    if abs(curr["high"] - prev["high"]) / (curr["close"] + 1e-10) < 0.0008:
        if prev_is_green and (not curr_is_green):
            patterns.append({
                "name": "Tweezer Top",
                "type": "BEARISH",
                "strength": 2,
                "description": f"Dual candle rejection at identical high level ({curr['high']:.1f}).",
                "candle_index": n - 1
            })

    # 13. Bullish Harami (Inside bar after red)
    if (not prev_is_green) and curr_is_green:
        if curr["open"] >= prev["close"] and curr["close"] <= prev["open"]:
            patterns.append({
                "name": "Bullish Harami",
                "type": "BULLISH",
                "strength": 1,
                "description": "Small green inside candle within previous red candle body indicating selling exhausted.",
                "candle_index": n - 1
            })

    # 14. Bearish Harami (Inside bar after green)
    if prev_is_green and (not curr_is_green):
        if curr["open"] <= prev["close"] and curr["close"] >= prev["open"]:
            patterns.append({
                "name": "Bearish Harami",
                "type": "BEARISH",
                "strength": 1,
                "description": "Small red inside candle within previous green candle body indicating buying exhausted.",
                "candle_index": n - 1
            })

    # 15. Doji / Dragonfly / Gravestone
    if curr_body <= (curr_range * 0.10):
        if curr_lower_wick > curr_range * 0.65:
            patterns.append({
                "name": "Dragonfly Doji",
                "type": "BULLISH",
                "strength": 2,
                "description": "Long lower wick with open/close near the absolute high of the bar.",
                "candle_index": n - 1
            })
        elif curr_upper_wick > curr_range * 0.65:
            patterns.append({
                "name": "Gravestone Doji",
                "type": "BEARISH",
                "strength": 2,
                "description": "Long upper wick with open/close near the absolute low of the bar.",
                "candle_index": n - 1
            })
        else:
            patterns.append({
                "name": "Doji (Indecision)",
                "type": "NEUTRAL",
                "strength": 1,
                "description": "Open and close virtually equal, representing market consolidation or balance.",
                "candle_index": n - 1
            })

    return patterns


def find_swing_points(df: pd.DataFrame, window: int = 2) -> tuple[list[dict], list[dict]]:
    """
    Identifies swing highs and swing lows (fractals).
    A swing high has a higher high than `window` candles to its left and right.
    A swing low has a lower low than `window` candles to its left and right.
    """
    swing_highs = []
    swing_lows = []
    n = len(df)

    for i in range(window, n - window):
        high_i = df.loc[i, "high"]
        low_i = df.loc[i, "low"]

        # Check swing high
        is_swing_high = all(high_i > df.loc[i - k, "high"] for k in range(1, window + 1)) and \
                        all(high_i >= df.loc[i + k, "high"] for k in range(1, window + 1))
        if is_swing_high:
            swing_highs.append({
                "index": i,
                "time": int(df.loc[i, "time"]),
                "price": float(high_i)
            })

        # Check swing low
        is_swing_low = all(low_i < df.loc[i - k, "low"] for k in range(1, window + 1)) and \
                       all(low_i <= df.loc[i + k, "low"] for k in range(1, window + 1))
        if is_swing_low:
            swing_lows.append({
                "index": i,
                "time": int(df.loc[i, "time"]),
                "price": float(low_i)
            })

    return swing_highs, swing_lows


def analyze_market_structure(df: pd.DataFrame) -> dict:
    """
    Determines:
    - Trend structure: Higher Highs + Higher Lows (Uptrend) vs Lower Highs + Lower Lows (Downtrend)
    - Break of Structure (BOS)
    - Change of Character (CHoCH)
    - Key Support and Resistance levels from recent swing clusters
    - Double Top / Double Bottom formations
    """
    swing_highs, swing_lows = find_swing_points(df, window=2)
    n = len(df)
    curr_price = float(df.iloc[-1]["close"])

    structure = {
        "trend": "SIDEWAYS / CHOPPY",
        "trend_bias": "NEUTRAL",
        "bos": None,
        "choch": None,
        "double_pattern": None,
        "nearest_support": None,
        "nearest_resistance": None,
        "support_levels": [],
        "resistance_levels": []
    }

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return structure

    sh_latest = swing_highs[-1]
    sh_prev = swing_highs[-2]
    sl_latest = swing_lows[-1]
    sl_prev = swing_lows[-2]

    # Trend structure determination
    higher_high = sh_latest["price"] > sh_prev["price"]
    higher_low = sl_latest["price"] > sl_prev["price"]
    lower_high = sh_latest["price"] < sh_prev["price"]
    lower_low = sl_latest["price"] < sl_prev["price"]

    if higher_high and higher_low:
        structure["trend"] = "UPTREND (Higher Highs & Higher Lows)"
        structure["trend_bias"] = "BULLISH"
    elif lower_high and lower_low:
        structure["trend"] = "DOWNTREND (Lower Highs & Lower Lows)"
        structure["trend_bias"] = "BEARISH"
    elif higher_high and lower_low:
        structure["trend"] = "EXPANDING BROADENING"
        structure["trend_bias"] = "VOLATILE"
    elif lower_high and higher_low:
        structure["trend"] = "CONTRACTING TRIANGLE"
        structure["trend_bias"] = "CONSOLIDATION"

    # Break of Structure (BOS) on latest candle
    last_close = float(df.iloc[-1]["close"])
    last_high = float(df.iloc[-1]["high"])
    last_low = float(df.iloc[-1]["low"])

    if last_close > sh_latest["price"]:
        structure["bos"] = {
            "type": "BULLISH_BOS",
            "broken_level": sh_latest["price"],
            "description": f"Price broke above recent swing high (${sh_latest['price']:.1f})"
        }
        if structure["trend_bias"] == "BEARISH":
            structure["choch"] = {
                "type": "BULLISH_CHOCH",
                "description": f"Change of Character: First break above swing high in downtrend"
            }
    elif last_close < sl_latest["price"]:
        structure["bos"] = {
            "type": "BEARISH_BOS",
            "broken_level": sl_latest["price"],
            "description": f"Price broke below recent swing low (${sl_latest['price']:.1f})"
        }
        if structure["trend_bias"] == "BULLISH":
            structure["choch"] = {
                "type": "BEARISH_CHOCH",
                "description": f"Change of Character: First break below swing low in uptrend"
            }

    # Double Top / Double Bottom detection
    if abs(sh_latest["price"] - sh_prev["price"]) / sh_latest["price"] < 0.0015:
        if (sh_latest["index"] - sh_prev["index"]) >= 4:
            structure["double_pattern"] = {
                "type": "DOUBLE_TOP",
                "neckline": sl_latest["price"],
                "level": (sh_latest["price"] + sh_prev["price"]) / 2,
                "description": f"Double Top formed near ${(sh_latest['price'] + sh_prev['price']) / 2:.1f}"
            }

    if abs(sl_latest["price"] - sl_prev["price"]) / sl_latest["price"] < 0.0015:
        if (sl_latest["index"] - sl_prev["index"]) >= 4:
            structure["double_pattern"] = {
                "type": "DOUBLE_BOTTOM",
                "neckline": sh_latest["price"],
                "level": (sl_latest["price"] + sl_prev["price"]) / 2,
                "description": f"Double Bottom formed near ${(sl_latest['price'] + sl_prev['price']) / 2:.1f}"
            }

    # Calculate Support & Resistance clusters
    recent_lows = [p["price"] for p in swing_lows[-8:]]
    recent_highs = [p["price"] for p in swing_highs[-8:]]

    supports = sorted([p for p in recent_lows if p < curr_price], reverse=True)
    resistances = sorted([p for p in recent_highs if p > curr_price])

    structure["nearest_support"] = supports[0] if supports else float(df["low"].tail(20).min())
    structure["nearest_resistance"] = resistances[0] if resistances else float(df["high"].tail(20).max())
    structure["support_levels"] = supports[:3]
    structure["resistance_levels"] = resistances[:3]

    return structure


if __name__ == "__main__":
    from data_fetcher import fetch_15m_candles
    df = fetch_15m_candles(limit=150)
    patterns = detect_candlestick_patterns(df)
    print("Detected Candlestick Patterns in latest candles:")
    for p in patterns:
        print(f"  [{p['type']}] {p['name']} (Strength {p['strength']}): {p['description']}")
    struct = analyze_market_structure(df)
    print("\nMarket Structure:")
    for k, v in struct.items():
        print(f"  {k}: {v}")
