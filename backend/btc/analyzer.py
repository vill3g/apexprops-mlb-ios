"""
Bitcoin 15-Minute Confluence Analyzer & Direction Predictor.
Combines Candlestick Patterns, Market Structure (BOS/CHoCH), RSI Divergences,
EMA Ribbon, MACD momentum, and Volume Surge into a unified -100 to +100 score.
Generates direction (UP/DOWN/NEUTRAL), confidence %, reason breakdown, and trade setups.
"""

from dataclasses import dataclass, asdict
import pandas as pd

import math
import time
from datetime import datetime, timezone

try:
    from backend.btc.indicators import add_all_indicators, extract_indicator_summary
    from backend.btc.pattern_detector import (
        detect_candlestick_patterns,
        analyze_market_structure,
        detect_liquidity_sweeps,
        detect_fair_value_gaps,
        analyze_wick_absorption
    )
    from backend.btc.kalshi_client import get_kalshi_15m_market
except ImportError:
    from indicators import add_all_indicators, extract_indicator_summary
    from pattern_detector import (
        detect_candlestick_patterns,
        analyze_market_structure,
        detect_liquidity_sweeps,
        detect_fair_value_gaps,
        analyze_wick_absorption
    )
    from kalshi_client import get_kalshi_15m_market


@dataclass
class TradeSetup:
    direction: str            # "BUY (UP)" | "SELL (DOWN)" | "WAIT (NEUTRAL)"
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward_1: float
    risk_reward_2: float
    risk_amount: float
    risk_percent: float


@dataclass
class AnalysisResult:
    timestamp: str
    price: float
    direction: str            # "STRONG BULLISH (UP)" | "BULLISH (UP)" | "NEUTRAL / CHOPPY" | "BEARISH (DOWN)" | "STRONG BEARISH (DOWN)"
    primary_bias: str         # "UP" | "DOWN" | "NEUTRAL"
    confluence_score: int     # -100 to +100
    confidence_percent: int   # 50% to 95%
    reasons_bullish: list[str]
    reasons_bearish: list[str]
    detected_patterns: list[dict]
    market_structure: dict
    indicators: dict
    trade_setup: dict


def analyze_btc(df: pd.DataFrame, timeframe: str = "15m") -> dict:
    """
    Complete analysis pipeline for any Bitcoin timeframe (1m, 5m, 15m, 1h, 4h, 1d).
    Takes clean OHLCV DataFrame, calculates indicators, detects patterns,
    evaluates confluence score, and produces trade setup.
    """
    # 1. Calculate indicators
    df_ind = add_all_indicators(df)
    ind_summary = extract_indicator_summary(df_ind)

    # 2. Detect candlestick patterns, market structure, sweeps, FVGs, & wicks
    patterns = detect_candlestick_patterns(df_ind)
    structure = analyze_market_structure(df_ind)
    sweeps = detect_liquidity_sweeps(df_ind)
    fvgs = detect_fair_value_gaps(df_ind)
    wicks = analyze_wick_absorption(df_ind)

    curr_price = float(df_ind.iloc[-1]["close"])
    atr = ind_summary.get("atr", curr_price * 0.005)

    # 3. Calculate Confluence Score
    score = 0
    bullish_reasons = []
    bearish_reasons = []

    # --- A. Trend & Moving Averages (Weight: up to +-30) ---
    # Macro Trend (EMA 200)
    if ind_summary.get("macro_bull") is True:
        score += 10
        bullish_reasons.append(f"Price above 200 EMA (${ind_summary['ema_200']:.1f}) - Macro Bullish (+10)")
    elif ind_summary.get("macro_bull") is False:
        score -= 10
        bearish_reasons.append(f"Price below 200 EMA (${ind_summary['ema_200']:.1f}) - Macro Bearish (-10)")

    # EMA Ribbon (9 / 21 / 50)
    if ind_summary.get("bullish_ribbon"):
        score += 12
        bullish_reasons.append("Bullish EMA Ribbon (EMA 9 > 21 > 50 aligned) (+12)")
    elif ind_summary.get("bearish_ribbon"):
        score -= 12
        bearish_reasons.append("Bearish EMA Ribbon (EMA 9 < 21 < 50 aligned) (-12)")
    else:
        # Partial alignment
        if ind_summary.get("ema_9", 0) > ind_summary.get("ema_21", 0):
            score += 4
            bullish_reasons.append("Short-term EMA 9 above EMA 21 (+4)")
        else:
            score -= 4
            bearish_reasons.append("Short-term EMA 9 below EMA 21 (-4)")

    # EMA Crossover
    if ind_summary.get("ema_cross") == "BULLISH_CROSS":
        score += 8
        bullish_reasons.append("Recent Bullish EMA 9/21 Golden Crossover (+8)")
    elif ind_summary.get("ema_cross") == "BEARISH_CROSS":
        score -= 8
        bearish_reasons.append("Recent Bearish EMA 9/21 Death Crossover (-8)")

    # --- B. Candlestick Patterns (Weight: up to +-30) ---
    for p in patterns:
        p_name = p["name"]
        p_type = p["type"]
        p_strength = p.get("strength", 1)
        base_points = p_strength * 8  # 8, 16, 24 pts

        if p_type == "BULLISH":
            score += base_points
            bullish_reasons.append(f"Candlestick: {p_name} detected (+{base_points})")
        elif p_type == "BEARISH":
            score -= base_points
            bearish_reasons.append(f"Candlestick: {p_name} detected (-{base_points})")

    # --- C. Momentum & Divergence (Weight: up to +-25) ---
    # RSI Divergences (Highest weight momentum factor)
    for div in ind_summary.get("divergences", []):
        if div["type"] == "BULLISH_RSI_DIVERGENCE":
            score += 20
            bullish_reasons.append(f"HIGH CONVICTION: Bullish RSI Divergence ({div['description']}) (+20)")
        elif div["type"] == "BEARISH_RSI_DIVERGENCE":
            score -= 20
            bearish_reasons.append(f"HIGH CONVICTION: Bearish RSI Divergence ({div['description']}) (-20)")

    # RSI condition
    rsi = ind_summary.get("rsi", 50)
    if rsi <= 30:
        score += 8
        bullish_reasons.append(f"RSI deeply oversold at {rsi:.1f} (Mean-reversion bounce likely) (+8)")
    elif rsi >= 70:
        score -= 8
        bearish_reasons.append(f"RSI overbought at {rsi:.1f} (Overextended pullback risk) (-8)")
    elif 50 <= rsi < 65:
        score += 3
        bullish_reasons.append(f"RSI positive momentum at {rsi:.1f} (+3)")
    elif 35 < rsi < 50:
        score -= 3
        bearish_reasons.append(f"RSI negative momentum at {rsi:.1f} (-3)")

    # MACD crossover & histogram
    if ind_summary.get("macd_cross") == "BULLISH_CROSS":
        score += 10
        bullish_reasons.append("MACD Line crossed above Signal Line (+10)")
    elif ind_summary.get("macd_cross") == "BEARISH_CROSS":
        score -= 10
        bearish_reasons.append("MACD Line crossed below Signal Line (-10)")

    if ind_summary.get("macd_hist_direction") == "EXPANDING_UP":
        score += 4
        bullish_reasons.append("MACD histogram expanding upward (+4)")
    else:
        score -= 4
        bearish_reasons.append("MACD histogram expanding downward (-4)")

    # --- D. Market Structure & Volume (Weight: up to +-15) ---
    trend_bias = structure.get("trend_bias", "NEUTRAL")
    if trend_bias == "BULLISH":
        score += 8
        bullish_reasons.append("Market Structure: Higher Highs & Higher Lows (+8)")
    elif trend_bias == "BEARISH":
        score -= 8
        bearish_reasons.append("Market Structure: Lower Highs & Lower Lows (-8)")

    if structure.get("bos"):
        bos = structure["bos"]
        if bos["type"] == "BULLISH_BOS":
            score += 7
            bullish_reasons.append(f"Structure Breakout: {bos['description']} (+7)")
        elif bos["type"] == "BEARISH_BOS":
            score -= 7
            bearish_reasons.append(f"Structure Breakdown: {bos['description']} (-7)")

    if structure.get("choch"):
        choch = structure["choch"]
        if choch["type"] == "BULLISH_CHOCH":
            score += 10
            bullish_reasons.append(f"Trend Shift: {choch['description']} (+10)")
        elif choch["type"] == "BEARISH_CHOCH":
            score -= 10
            bearish_reasons.append(f"Trend Shift: {choch['description']} (-10)")

    if structure.get("double_pattern"):
        dp = structure["double_pattern"]
        if dp["type"] == "DOUBLE_BOTTOM":
            score += 10
            bullish_reasons.append(f"Chart Pattern: {dp['description']} (+10)")
        elif dp["type"] == "DOUBLE_TOP":
            score -= 10
            bearish_reasons.append(f"Chart Pattern: {dp['description']} (-10)")

    # Volume surge
    if ind_summary.get("vol_surge"):
        last_candle_green = df_ind.iloc[-1]["close"] >= df_ind.iloc[-1]["open"]
        if last_candle_green:
            score += 6
            bullish_reasons.append(f"High Volume Surge ({ind_summary['vol_ratio']:.1f}x avg volume) on Green candle (+6)")
        else:
            score -= 6
            bearish_reasons.append(f"High Volume Surge ({ind_summary['vol_ratio']:.1f}x avg volume) on Red candle (-6)")

    # VWAP factor
    if ind_summary.get("vwap"):
        vwap_val = ind_summary["vwap"]
        if ind_summary.get("vwap_status") == "ABOVE_VWAP":
            score += 6
            bullish_reasons.append(f"Holding above Session VWAP (${vwap_val:.1f}) - Buyer edge (+6)")
        else:
            score -= 6
            bearish_reasons.append(f"Trading below Session VWAP (${vwap_val:.1f}) - Seller edge (-6)")

    # Fair Value Gaps (FVG) factor
    for fvg in ind_summary.get("fvgs", [])[-2:]:
        if fvg["type"] == "BULLISH_FVG" and curr_price >= fvg["bottom"]:
            score += 5
            bullish_reasons.append(f"Smart Money: Reacting to {fvg['description']} (+5)")
        elif fvg["type"] == "BEARISH_FVG" and curr_price <= fvg["top"]:
            score -= 5
            bearish_reasons.append(f"Smart Money: Facing {fvg['description']} (-5)")

    # Clamp score to [-100, 100]
    score = max(-100, min(100, score))

    # Determine Direction & Bias
    if score >= 45:
        direction = "STRONG BULLISH (UP)"
        primary_bias = "UP"
    elif score >= 20:
        direction = "BULLISH (UP)"
        primary_bias = "UP"
    elif score <= -45:
        direction = "STRONG BEARISH (DOWN)"
        primary_bias = "DOWN"
    elif score <= -20:
        direction = "BEARISH (DOWN)"
        primary_bias = "DOWN"
    else:
        direction = "NEUTRAL / CHOPPY"
        primary_bias = "NEUTRAL"

    # Confidence calculation: 50% baseline up to 95%
    confidence_percent = int(round(50 + (abs(score) / 100.0) * 45))

    # --- 4. Dynamic Trade Setup Generation ---
    near_support = structure.get("nearest_support", curr_price - (1.5 * atr))
    near_resistance = structure.get("nearest_resistance", curr_price + (1.5 * atr))

    if primary_bias == "UP":
        sl_distance = max(1.2 * atr, curr_price - near_support)
        sl_distance = min(sl_distance, 2.5 * atr)
        stop_loss = round(curr_price - sl_distance, 2)
        tp1 = round(curr_price + (1.5 * sl_distance), 2)
        tp2 = round(curr_price + (2.5 * sl_distance), 2)
        risk_pct = round((sl_distance / curr_price) * 100, 2)
        setup = {
            "direction": "BUY (UP)",
            "entry_price": round(curr_price, 2),
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "risk_reward_1": 1.5,
            "risk_reward_2": 2.5,
            "risk_amount": round(sl_distance, 2),
            "risk_percent": risk_pct,
            "breakeven_rule": f"Move SL to Breakeven (${round(curr_price, 2)}) after TP1 hit"
        }
    elif primary_bias == "DOWN":
        sl_distance = max(1.2 * atr, near_resistance - curr_price)
        sl_distance = min(sl_distance, 2.5 * atr)
        stop_loss = round(curr_price + sl_distance, 2)
        tp1 = round(curr_price - (1.5 * sl_distance), 2)
        tp2 = round(curr_price - (2.5 * sl_distance), 2)
        risk_pct = round((sl_distance / curr_price) * 100, 2)
        setup = {
            "direction": "SELL (DOWN)",
            "entry_price": round(curr_price, 2),
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "risk_reward_1": 1.5,
            "risk_reward_2": 2.5,
            "risk_amount": round(sl_distance, 2),
            "risk_percent": risk_pct,
            "breakeven_rule": f"Move SL to Breakeven (${round(curr_price, 2)}) after TP1 hit"
        }
    else:
        setup = {
            "direction": "WAIT (NEUTRAL)",
            "entry_price": round(curr_price, 2),
            "stop_loss": round(near_support, 2),
            "take_profit_1": round(near_resistance, 2),
            "take_profit_2": round(near_resistance + atr, 2),
            "risk_reward_1": 1.0,
            "risk_reward_2": 1.5,
            "risk_amount": round(atr, 2),
            "risk_percent": round((atr / curr_price) * 100, 2),
            "breakeven_rule": "Range trading - scalp tight limits"
        }

    setup["timeframe"] = timeframe.upper()

    # --- 5. 15-Minute Price Target Benchmark & Above/Below Predictor ---
    n_rows = len(df_ind)
    active_target = curr_price
    target_source = "15M Candle Close"
    last_5_targets = []
    higher_count = 0
    lower_count = 0
    from datetime import datetime, timezone

    # Target benchmark is current 15m candle start/open price
    now_dt = datetime.now(timezone.utc)
    curr_15m_start_min = (now_dt.minute // 15) * 15
    interval_start_dt = now_dt.replace(minute=curr_15m_start_min, second=0, microsecond=0)
    start_time_12hr = interval_start_dt.strftime("%I:%M %p").lstrip('0')

    if n_rows > 0:
        active_target = round(float(df_ind.iloc[-1]["open"]), 2)
        target_source = f"15M Start Price ({start_time_12hr} UTC)"
    else:
        active_target = float(curr_price)
        target_source = "15M Start Price"

    if n_rows >= 7:
        # Last 5 completed targets (indices n - 6 to n - 2)
        for i in range(n_rows - 6, n_rows - 1):
            c = df_ind.iloc[i]
            p = df_ind.iloc[i - 1]
            c_close = float(c["close"])
            p_close = float(p["close"])
            diff = round(c_close - p_close, 2)
            diff_pct = round((diff / (p_close + 1e-10)) * 100, 2)
            is_up = diff >= 0
            if is_up:
                higher_count += 1
            else:
                lower_count += 1

            t_val = c.get("time")
            close_val = int(t_val) + 900 if t_val else None
            time_str = datetime.fromtimestamp(close_val, tz=timezone.utc).strftime("%I:%M %p").lstrip('0') if close_val else "--:--"

            last_5_targets.append({
                "time": time_str,
                "price": round(c_close, 2),
                "delta": diff,
                "delta_pct": diff_pct,
                "direction": "HIGHER" if is_up else "LOWER",
                "arrow": "▲" if is_up else "▼",
                "color": "green" if is_up else "red"
            })

    target_delta = round(curr_price - active_target, 2)
    target_delta_pct = round((target_delta / (active_target + 1e-10)) * 100, 3)
    target_status = "ABOVE" if target_delta >= 0 else "BELOW"

    # -------------------------------------------------------------------------
    # UNIFIED 15M CONTRACT INTELLIGENCE ENGINE (DIFFUSION & CONFLUENCE BLEND)
    # -------------------------------------------------------------------------
    # 1. Dynamic Time-Decay & Brownian Volatility Diffusion
    now_epoch = int(time.time())
    seconds_in_15m = now_epoch % 900
    seconds_remaining = max(10, 900 - seconds_in_15m)
    minutes_remaining = max(0.15, seconds_remaining / 60.0)

    atr_1m = max(4.0, atr / math.sqrt(15.0))
    expected_stddev = atr_1m * math.sqrt(minutes_remaining)
    z_score = target_delta / max(1.0, expected_stddev)

    # Base mathematical probability of closing above target
    p_decay_raw = 1.0 / (1.0 + math.exp(-1.702 * z_score))
    p_decay = p_decay_raw * 100.0

    pred_weight = 0
    pred_factors = []

    # A. Time-Decay Factor
    min_str = f"{seconds_remaining // 60}m {seconds_remaining % 60}s"
    if target_delta >= 0:
        if seconds_remaining <= 180 and target_delta > (atr_1m * 0.8):
            pred_factors.append(f"⏱️ Theta Lock: +${target_delta:.2f} lead with only {min_str} left (High probability lock)")
        else:
            pred_factors.append(f"⏱️ Time-Decay: Holding +${target_delta:.2f} lead ({min_str} remaining, Vol: ${expected_stddev:.1f})")
    else:
        if seconds_remaining <= 180 and abs(target_delta) > (atr_1m * 0.8):
            pred_factors.append(f"⏱️ Theta Deficit: -${abs(target_delta):.2f} deficit with only {min_str} left (Steep hurdle)")
        else:
            pred_factors.append(f"⏱️ Time-Decay: -${abs(target_delta):.2f} deficit ({min_str} remaining, Vol: ${expected_stddev:.1f})")

    # B. Multi-Timeframe Alignment (1H Macro + 15M + Micro)
    macro_bull = ind_summary.get("macro_bull")
    if macro_bull is True:
        pred_weight += 14
        pred_factors.append("🌐 MTF Context: 1H Macro Trend Bullish (Price above 200 EMA)")
    elif macro_bull is False:
        pred_weight -= 14
        pred_factors.append("🌐 MTF Context: 1H Macro Trend Bearish (Price below 200 EMA)")

    # 15M EMA Ribbon
    if ind_summary.get("bullish_ribbon"):
        pred_weight += 18
        pred_factors.append("📈 15M Ribbon: Bullish EMA 9 > 21 > 50 providing upward thrust")
    elif ind_summary.get("bearish_ribbon"):
        pred_weight -= 18
        pred_factors.append("📉 15M Ribbon: Bearish EMA 9 < 21 < 50 exerting downward pressure")
    elif ind_summary.get("ema_9", 0) > ind_summary.get("ema_21", 0):
        pred_weight += 6
        pred_factors.append("📈 Micro EMA: Short-term EMA 9 sloping above EMA 21")
    else:
        pred_weight -= 6
        pred_factors.append("📉 Micro EMA: Short-term EMA 9 sloping below EMA 21")

    # C. Smart Money Liquidity Sweeps (Judas Swings)
    for sw in sweeps:
        if sw["type"] == "BULLISH":
            pred_weight += 24
            pred_factors.append(f"🧲 SMC Sweep: {sw['name']} (+${sw['wick_depth']:.1f} dip reclaimed above target)")
        elif sw["type"] == "BEARISH":
            pred_weight -= 24
            pred_factors.append(f"🧲 SMC Sweep: {sw['name']} (+${sw['wick_depth']:.1f} spike rejected below target)")

    # D. Fair Value Gaps (FVG)
    for fvg in fvgs[:2]:
        if fvg["type"] == "BULLISH_FVG":
            pred_weight += 10
            pred_factors.append(f"📦 FVG Floor: Bullish imbalance support (${fvg['bottom']:.0f} - ${fvg['top']:.0f})")
        elif fvg["type"] == "BEARISH_FVG":
            pred_weight -= 10
            pred_factors.append(f"📦 FVG Ceiling: Bearish imbalance resistance (${fvg['bottom']:.0f} - ${fvg['top']:.0f})")

    # E. Order Flow & Wick Absorption
    if wicks["bias"] == "BUYER_ABSORPTION":
        pred_weight += 16
        pred_factors.append(f"📊 Order Flow: Institutional Bid Absorption ({wicks['buyer_absorption_pct']}% lower wicks)")
    elif wicks["bias"] == "SELLER_REJECTION":
        pred_weight -= 16
        pred_factors.append(f"📊 Order Flow: Heavy Overhead Capping ({wicks['seller_rejection_pct']}% upper wicks)")

    # F. Candle Progression & RSI Momentum
    last_candle = df_ind.iloc[-1]
    candle_green = float(last_candle["close"]) >= float(last_candle["open"])
    if candle_green:
        pred_weight += 10
        pred_factors.append("🟢 Active Candle: Green bar (buyers defending bid)")
    else:
        pred_weight -= 10
        pred_factors.append("🔴 Active Candle: Red bar (sellers in control)")

    rsi_val = ind_summary.get("rsi", 50)
    if rsi_val >= 58:
        pred_weight += 10
        pred_factors.append(f"⚡ RSI Momentum: Bullish expansion ({rsi_val:.1f})")
    elif rsi_val <= 42:
        pred_weight -= 10
        pred_factors.append(f"⚡ RSI Momentum: Bearish compression ({rsi_val:.1f})")

    # G. Market Structure (BOS, CHoCH)
    bos_info = structure.get("bos")
    if bos_info:
        if bos_info.get("type") == "BULLISH_BOS":
            pred_weight += 14
            pred_factors.append("🏛️ Structure: Bullish Break of Structure (BOS) confirmed")
        elif bos_info.get("type") == "BEARISH_BOS":
            pred_weight -= 14
            pred_factors.append("🏛️ Structure: Bearish Break of Structure (BOS) confirmed")

    choch_info = structure.get("choch")
    if choch_info:
        if choch_info.get("type") == "BULLISH_CHOCH":
            pred_weight += 10
            pred_factors.append("🏛️ Structure: Bullish Change of Character (CHoCH)")
        elif choch_info.get("type") == "BEARISH_CHOCH":
            pred_weight -= 10
            pred_factors.append("🏛️ Structure: Bearish Change of Character (CHoCH)")

    # H. Triple Confluence Check
    if macro_bull is True and candle_green and (ind_summary.get("bullish_ribbon") or sweeps):
        pred_factors.insert(0, "🔥 TRIPLE MTF ALIGNMENT: 1H Macro + 15M Trend + Buyers in Sync")
    elif macro_bull is False and (not candle_green) and (ind_summary.get("bearish_ribbon") or sweeps):
        pred_factors.insert(0, "❄️ TRIPLE MTF ALIGNMENT: 1H Macro + 15M Trend + Sellers in Sync")

    # -------------------------------------------------------------------------
    # Calibrated Probability Blending
    # -------------------------------------------------------------------------
    p_tech_shift = (pred_weight / 140.0) * 35.0
    decay_weight_factor = min(0.88, max(0.40, 1.0 - (minutes_remaining / 16.0)))
    p_final = (decay_weight_factor * p_decay) + ((1.0 - decay_weight_factor) * (50.0 + p_tech_shift))

    # Streak & Mean Reversion Dampener
    if higher_count >= 4 and target_delta > 0:
        p_final = max(52, p_final - 5)
        pred_factors.append(f"⚠️ Streak Warning: {higher_count} consecutive UP closes (Pullback risk elevated)")
    elif lower_count >= 4 and target_delta < 0:
        p_final = min(48, p_final + 5)
        pred_factors.append(f"⚠️ Streak Warning: {lower_count} consecutive DOWN closes (Oversold bounce risk elevated)")

    pred_prob = int(round(max(5, min(95, p_final))))
    pred_outcome = "ABOVE TARGET (OVER)" if pred_prob >= 50 else "BELOW TARGET (UNDER)"

    if pred_prob >= 80 or pred_prob <= 20:
        conf_badge = "LOCKED RUNWAY"
    elif pred_prob >= 70 or pred_prob <= 30:
        conf_badge = "HIGH CONVICTION"
    elif pred_prob >= 60 or pred_prob <= 40:
        conf_badge = "MODERATE EDGE"
    else:
        conf_badge = "TIGHT PIVOT BATTLE"

    # Prepend Kalshi Market Odds factor if available
    kalshi_m = None



    # -------------------------------------------------------------------------
    # 15M Prediction Accuracy Evaluator (Starts Counting Amount Right from 1)
    # -------------------------------------------------------------------------
    # Evaluate the most recently completed 15M interval
    last_cand = df_ind.iloc[-2] if n_rows >= 2 else df_ind.iloc[-1]
    prev_cand = df_ind.iloc[-3] if n_rows >= 3 else df_ind.iloc[-2] if n_rows >= 2 else df_ind.iloc[-1]
    
    p_up = float(prev_cand["close"]) >= float(prev_cand["open"])
    c_open = float(last_cand["open"])
    c_close = float(last_cand["close"])
    actual_is_above = (c_close >= c_open)
    pred_is_above = p_up
    is_hit = (pred_is_above == actual_is_above)

    # Initial boot baseline starts at 0 of 0 (counts up as 15m closes are logged)
    acc_total = 0
    acc_correct = 0
    acc_pct = 0.0
    acc_outcomes = []

    target_benchmark = {
        "target_price": active_target,
        "target_source": target_source,
        "kalshi": kalshi_m,
        "current_price": curr_price,
        "delta": target_delta,
        "delta_pct": target_delta_pct,
        "status": target_status,
        "predicted_outcome": pred_outcome,
        "probability_percent": pred_prob,
        "confidence_badge": conf_badge,
        "decision_factors": pred_factors,
        "last_5_targets": last_5_targets,
        "streak_summary": f"{higher_count} Higher / {lower_count} Lower",
        "prediction_accuracy": {
            "total_evaluated": acc_total,
            "correct_picks": acc_correct,
            "accuracy_percent": acc_pct,
            "ratio_text": f"{acc_correct} of {acc_total} Correct",
            "recent_outcomes": [o["correct"] for o in acc_outcomes[-5:]]
        }
    }

    return {
        "timestamp": str(df_ind.iloc[-1]["datetime"]),
        "timeframe": timeframe.upper(),
        "price": round(curr_price, 2),
        "direction": direction,
        "primary_bias": primary_bias,
        "confluence_score": score,
        "confidence_percent": confidence_percent,
        "reasons_bullish": bullish_reasons,
        "reasons_bearish": bearish_reasons,
        "detected_patterns": patterns,
        "market_structure": structure,
        "indicators": ind_summary,
        "trade_setup": setup,
        "target_benchmark": target_benchmark
    }


def analyze_btc_15m(df: pd.DataFrame) -> dict:
    """Backwards-compatibility alias."""
    return analyze_btc(df, timeframe="15m")


if __name__ == "__main__":
    from data_fetcher import fetch_15m_candles
    df = fetch_15m_candles(limit=250)
    result = analyze_btc_15m(df)
    print("=" * 60)
    print(f"BTC 15-MINUTE ANALYSIS: {result['direction']}")
    print(f"Current Price: ${result['price']:.2f}")
    print(f"Confluence Score: {result['confluence_score']} / 100")
    print(f"Confidence: {result['confidence_percent']}%")
    print("=" * 60)
    print("Bullish Factors:")
    for r in result["reasons_bullish"]:
        print(f"  + {r}")
    print("\nBearish Factors:")
    for r in result["reasons_bearish"]:
        print(f"  - {r}")
    print("\nTrade Setup:")
    for k, v in result["trade_setup"].items():
        print(f"  {k}: {v}")
