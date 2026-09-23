import logging
logger = logging.getLogger(__name__)
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
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor

_ANALYZER_EXECUTOR = None

try:
    from backend.btc.indicators import add_all_indicators, extract_indicator_summary
    from backend.btc.pattern_detector import (
        detect_candlestick_patterns,
        analyze_market_structure,
        detect_liquidity_sweeps,
        detect_fair_value_gaps,
        detect_order_blocks,
        analyze_wick_absorption
    )
    from backend.btc.kalshi_client import get_kalshi_15m_market
    from backend.btc.trend_boxes import (
        compute_last_5_targets,
        compute_streak_summary,
        enrich_targets_with_ml
    )
    from backend.btc.ml_engine import build_live_ml_features
except ImportError:
    from indicators import add_all_indicators, extract_indicator_summary
    from pattern_detector import (
        detect_candlestick_patterns,
        analyze_market_structure,
        detect_liquidity_sweeps,
        detect_fair_value_gaps,
        detect_order_blocks,
        analyze_wick_absorption
    )
    from kalshi_client import get_kalshi_15m_market
    from trend_boxes import (
        compute_last_5_targets,
        compute_streak_summary,
        enrich_targets_with_ml
    )
    from ml_engine import build_live_ml_features

# -------------------------------------------------------------------
# Centralized thresholds & blending weights for analyzer.py
# Calibrated from walk-forward backtest (see backend/data/backtest_report.json).
# -------------------------------------------------------------------
THRESHOLDS = {
    # evaluate_next_15m_contract blending (tuned via walk-forward grid search, see backend/data/backtest_report.json)
    "heuristic_weight": 0.40,
    "ml_weight": 0.60,
    "model_conflict_threshold": 15.0,
    "model_conflict_cap": 58.0,

    # analyze_btc rules vs ML blend
    "analyze_rules_weight": 0.70,
    "analyze_ml_weight": 0.30,

    # Kalshi market-structure thresholds
    "kalshi_override_yes": 62.0,
    "kalshi_override_no": 62.0,
    "kalshi_imbalance_threshold": 25.0,
    "kalshi_whales_extreme_yes": 75.0,
    "kalshi_whales_extreme_no": 25.0,

    # Strike pin risk & dead zone
    "pin_delta_dollars": 15.0,
    "pin_atr_max": 45.0,

    # Setup detection thresholds
    "bollinger_wick_min": 0.35,
    "bollinger_rsi_bear": 62.0,
    "bollinger_rsi_bull": 38.0,
    "climax_rsi_bear": 64.0,
    "climax_rsi_bull": 36.0,
    "ribbon_wick_min": 0.28,
    "b_setup_rsi_bear": 58.0,
    "b_setup_rsi_bull": 42.0,
    "thrust_range_closure_bull": 0.80,
    "thrust_range_closure_bear": 0.20,
    "thrust_body_range_min": 0.55,
    "rsi_bb_momentum_bull": 65.0,
    "rsi_bb_flush_bear": 35.0,

    # Order flow / CVD & Imbalance gates
    "cvd_gate_bear_limit": -2.0,
    "cvd_gate_bull_limit": 2.0,
    "imbalance_gate_bear_wall": -30.0,
    "imbalance_gate_bid_wall": 30.0,
}

HEURISTIC_WEIGHT = THRESHOLDS["heuristic_weight"]
ML_WEIGHT = THRESHOLDS["ml_weight"]



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


def analyze_btc(df: pd.DataFrame, asset: str = "BTC", timeframe: str = "15m") -> dict:
    """
    Complete analysis pipeline for any Bitcoin timeframe (1m, 5m, 15m, 1h, 4h, 1d).
    Takes clean OHLCV DataFrame, calculates indicators, detects patterns,
    evaluates confluence score, and produces trade setup.
    """
    # 0. MTF Macro Alignment Fetching
    macro_trend_1h = "NEUTRAL"
    macro_trend_4h = "NEUTRAL"
    try:
        from backend.engine.multi_asset_fetcher import fetch_asset_candles as fetch_candles
        from backend.btc.indicators import compute_ema
        df_1h = fetch_candles(asset, "1h", limit=50)
        df_4h = fetch_candles(asset, "4h", limit=50)
        if df_1h is not None and not df_1h.empty:
            ema50_1h = compute_ema(df_1h["close"], 50).iloc[-1]
            macro_trend_1h = "BULLISH" if float(df_1h.iloc[-1]["close"]) > float(ema50_1h) else "BEARISH"
        if df_4h is not None and not df_4h.empty:
            ema50_4h = compute_ema(df_4h["close"], 50).iloc[-1]
            macro_trend_4h = "BULLISH" if float(df_4h.iloc[-1]["close"]) > float(ema50_4h) else "BEARISH"
    except Exception as e:
        pass

    # 1. Calculate indicators
    df_ind = add_all_indicators(df)
    if df_ind is None or df_ind.empty:
        logger.warning(f"[Analyzer] Empty DataFrame after adding indicators for {asset} {timeframe}. Returning neutral fallback.")
        return {
            "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET"),
            "price": 0.0, "direction": "NEUTRAL / CHOPPY", "primary_bias": "NEUTRAL",
            "confluence_score": 0, "confidence_percent": 50,
            "reasons_bullish": [], "reasons_bearish": ["No candle data available"],
            "detected_patterns": [], "market_structure": {}, "indicators": {},
            "trade_setup": {"action": "WAIT", "reason": "Insufficient data"}
        }
    ind_summary = extract_indicator_summary(df_ind)

    # 2. Detect candlestick patterns, market structure, sweeps, FVGs, & wicks
    patterns = detect_candlestick_patterns(df_ind)
    structure = analyze_market_structure(df_ind)
    sweeps = detect_liquidity_sweeps(df_ind)
    fvgs = detect_fair_value_gaps(df_ind)
    obs = detect_order_blocks(df_ind)
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
        score += 3
        bullish_reasons.append(f"Price above 200 EMA (${ind_summary['ema_200']:.1f}) - Macro Bullish (+3)")
    elif ind_summary.get("macro_bull") is False:
        score -= 3
        bearish_reasons.append(f"Price below 200 EMA (${ind_summary['ema_200']:.1f}) - Macro Bearish (-3)")

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

    # CVD Divergences
    for cdiv in ind_summary.get("cvd_divergences", []):
        if cdiv["type"] == "BULLISH_CVD_DIVERGENCE":
            score += 18
            bullish_reasons.append(f"CVD: Bullish Volume Delta Divergence ({cdiv['description']}) (+18)")
        elif cdiv["type"] == "BEARISH_CVD_DIVERGENCE":
            score -= 18
            bearish_reasons.append(f"CVD: Bearish Volume Delta Divergence ({cdiv['description']}) (-18)")

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

    # MTF Macro Alignment
    if macro_trend_4h == "BULLISH" and macro_trend_1h == "BULLISH":
        score += 5
        bullish_reasons.append("MTF Alignment: 1H and 4H charts are heavily BULLISH (+5)")
    elif macro_trend_4h == "BEARISH" and macro_trend_1h == "BEARISH":
        score -= 5
        bearish_reasons.append("MTF Alignment: 1H and 4H charts are heavily BEARISH (-5)")
    elif macro_trend_4h == "BULLISH":
        score += 2
        bullish_reasons.append("MTF Macro: 4H trend is BULLISH (+2)")
    elif macro_trend_4h == "BEARISH":
        score -= 2
        bearish_reasons.append("MTF Macro: 4H trend is BEARISH (-2)")

    # Volume Profile Point of Control (POC)
    if ind_summary.get("poc"):
        poc = ind_summary["poc"]
        if curr_price > poc:
            score += 8
            bullish_reasons.append(f"Volume Profile: Trading above 24H Point of Control (${poc:.1f}) (+8)")
            if curr_price <= poc * 1.002:
                score += 10
                bullish_reasons.append(f"Volume Profile: Perfect rejection bounce off POC Support (+10)")
        elif curr_price < poc:
            score -= 8
            bearish_reasons.append(f"Volume Profile: Trading below 24H Point of Control (${poc:.1f}) (-8)")
            if curr_price >= poc * 0.998:
                score -= 10
                bearish_reasons.append(f"Volume Profile: Perfect rejection fade off POC Resistance (-10)")

    # CVD Acceleration (Trapped Trader Logic)
    cvd_accel = ind_summary.get("cvd_acceleration", 0.0)
    if cvd_accel > 0 and ind_summary.get("vol_surge"):
        score += 10
        bullish_reasons.append("CVD Acceleration: Fresh aggressive market buying detected (+10)")
    elif cvd_accel < 0 and ind_summary.get("vol_surge"):
        score -= 10
        bearish_reasons.append("CVD Acceleration: Aggressive market selling into volume surge (-10)")
    elif df_ind.iloc[-1]["close"] > df_ind.iloc[-1]["open"] and cvd_accel < 0:
        score -= 15
        bearish_reasons.append("TRAP DETECTED: Green candle with negative CVD (Short covering / Limit Selling absorption) (-15)")
    elif df_ind.iloc[-1]["close"] < df_ind.iloc[-1]["open"] and cvd_accel > 0:
        score += 15
        bullish_reasons.append("TRAP DETECTED: Red candle with positive CVD (Long liquidation / Limit Buying absorption) (+15)")

    # Clamp score to [-100, 100]
    

    # --- F. Derivatives & Market Microstructure (Weight: up to +-40) ---
    cb_ob = {}
    try:
        from backend.btc.data_fetcher import get_coinbase_orderbook_imbalance
        cb_ob = get_coinbase_orderbook_imbalance()
        imb = cb_ob.get('imbalance', 0.0)
        
        # Check resting liquidity walls
        largest_bid = cb_ob.get('largest_bid_wall')
        largest_ask = cb_ob.get('largest_ask_wall')
        
        if largest_ask and curr_price <= largest_ask <= curr_price * 1.0015:
            score -= 20
            bearish_reasons.append(f"L2 Heatmap: Massive Sell Wall sitting right overhead at ${largest_ask:.2f} (-20)")
        if largest_bid and curr_price >= largest_bid >= curr_price * 0.9985:
            score += 20
            bullish_reasons.append(f"L2 Heatmap: Massive Buy Wall sitting right underneath at ${largest_bid:.2f} (+20)")

        if imb >= 25.0:
            score += 15
            bullish_reasons.append(f"Massive Spot Buy Wall (+{imb}% Bid Imbalance) (+15)")
        elif imb <= -25.0:
            score -= 15
            bearish_reasons.append(f"Massive Spot Sell Wall ({imb}% Ask Imbalance) (-15)")
        elif imb >= 10.0:
            score += 5
            bullish_reasons.append(f"Spot Bid Skew (+{imb}%) (+5)")
        elif imb <= -10.0:
            score -= 5
            bearish_reasons.append(f"Spot Ask Skew ({imb}%) (-5)")
    except Exception as _e:
        logger.warning(f"[Analyzer] Orderbook imbalance fetch failed: {_e}")

    try:
        from backend.btc.kalshi_client import get_kalshi_15m_market
        kalshi_market = get_kalshi_15m_market(allow_synthetic=True)
        if kalshi_market:
            yes_prob = kalshi_market.get('yes_prob', 50.0)
            if yes_prob >= 75.0:
                score += 10
                bullish_reasons.append(f"Kalshi Whales Heavily Bullish ({yes_prob}% YES) (+10)")
            elif yes_prob <=25.0:
                score -= 10
                bearish_reasons.append(f"Kalshi Whales Heavily Bearish ({yes_prob}% YES) (-10)")
            elif yes_prob >= 60.0:
                score += 5
                bullish_reasons.append(f"Kalshi Sentiment Bullish ({yes_prob}% YES) (+5)")
            elif yes_prob <= 40.0:
                score -= 5
                bearish_reasons.append(f"Kalshi Sentiment Bearish ({yes_prob}% YES) (-5)")
    except Exception as _e:
        logger.warning(f"[Analyzer] Kalshi market fetch failed: {_e}")

    try:
        from backend.btc.data_fetcher import get_binance_futures_data
        futures = get_binance_futures_data()
        if futures:
            fr = futures.get('funding_rate', 0.0)
            if fr > 0.015:
                score -= 10
                bearish_reasons.append(f"Retail Over-leveraged Long (High Funding {fr:.4f}%) - Liquidation risk (-10)")
            elif fr < -0.015:
                score += 10
                bullish_reasons.append(f"Retail Heavily Short (Negative Funding {fr:.4f}%) - Short squeeze risk (+10)")
    except Exception as _e:
        logger.warning(f"[Analyzer] Binance futures fetch failed: {_e}")

    try:
        from backend.btc.news_fetcher import get_news_sentiment_summary
        news_summary = get_news_sentiment_summary()
        n_score = news_summary.get("sentiment_score", 0.0)
        
        if n_score >= 0.15:
            score += int(n_score * 15)
            bullish_reasons.append(f"📰 Breaking News: Bullish sentiment (+{n_score:.2f}) (+{int(n_score * 15)})")
        elif n_score <= -0.15:
            score -= int(abs(n_score) * 15)
            bearish_reasons.append(f"📰 Breaking News: Bearish sentiment ({n_score:.2f}) (-{int(abs(n_score) * 15)})")
    except Exception as _e:
        logger.warning(f"[Analyzer] News sentiment fetch failed: {_e}")

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
    near_support = structure.get("nearest_support") or (curr_price - (1.5 * atr))
    near_resistance = structure.get("nearest_resistance") or (curr_price + (1.5 * atr))

    if primary_bias == "UP":
        sl_distance = max(1.2 * atr, curr_price - near_support)
        sl_distance = min(sl_distance, 2.5 * atr)
        stop_loss = round(curr_price - sl_distance, 2)
        
        # M2: Constrain TP1 to structural resistance if closer than standard 1.5R
        raw_tp1 = curr_price + (1.5 * sl_distance)
        if near_resistance > curr_price:
            tp1_val = min(raw_tp1, near_resistance)
            tp1_val = max(tp1_val, curr_price + (0.5 * atr)) # Ensure minimum viable profit distance
        else:
            tp1_val = raw_tp1
        tp1 = round(tp1_val, 2)
        tp2 = round(max(tp1 + (1.0 * sl_distance), curr_price + (2.5 * sl_distance)), 2)
        
        rr1 = round(abs(tp1 - curr_price) / max(sl_distance, 1e-9), 2)
        rr2 = round(abs(tp2 - curr_price) / max(sl_distance, 1e-9), 2)
        risk_pct = round((sl_distance / max(curr_price, 1e-9)) * 100, 2)
        setup = {
            "direction": "BUY (UP)",
            "entry_price": round(curr_price, 2),
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "risk_reward_1": rr1,
            "risk_reward_2": rr2,
            "risk_amount": round(sl_distance, 2),
            "risk_percent": risk_pct,
            "breakeven_rule": f"Move SL to Breakeven (${round(curr_price, 2)}) after TP1 hit"
        }
    elif primary_bias == "DOWN":
        sl_distance = max(1.2 * atr, near_resistance - curr_price)
        sl_distance = min(sl_distance, 2.5 * atr)
        stop_loss = round(curr_price + sl_distance, 2)
        
        # M2: Constrain TP1 to structural support if closer than standard 1.5R
        raw_tp1 = curr_price - (1.5 * sl_distance)
        if near_support < curr_price:
            tp1_val = max(raw_tp1, near_support)
            tp1_val = min(tp1_val, curr_price - (0.5 * atr)) # Ensure minimum viable profit distance
        else:
            tp1_val = raw_tp1
        tp1 = round(tp1_val, 2)
        tp2 = round(min(tp1 - (1.0 * sl_distance), curr_price - (2.5 * sl_distance)), 2)
        
        rr1 = round(abs(curr_price - tp1) / max(sl_distance, 1e-9), 2)
        rr2 = round(abs(curr_price - tp2) / max(sl_distance, 1e-9), 2)
        risk_pct = round((sl_distance / max(curr_price, 1e-9)) * 100, 2)
        setup = {
            "direction": "SELL (DOWN)",
            "entry_price": round(curr_price, 2),
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "risk_reward_1": rr1,
            "risk_reward_2": rr2,
            "risk_amount": round(sl_distance, 2),
            "risk_percent": risk_pct,
            "breakeven_rule": f"Move SL to Breakeven (${round(curr_price, 2)}) after TP1 hit"
        }
    else:
        direction = "PASS"
        action = "PASS" 
        setup = {
            "direction": "WAIT (NEUTRAL)",
            "entry_price": round(curr_price, 2),
            "stop_loss": round(near_support, 2),
            "take_profit_1": round(near_resistance, 2),
            "take_profit_2": round(near_resistance + atr, 2),
            "risk_reward_1": 1.0,
            "risk_reward_2": 1.5,
            "risk_amount": round(atr, 2),
            "risk_percent": round((atr / max(curr_price, 1e-9)) * 100, 2),
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

    # Target benchmark is current 15m candle start/open price
    now_dt = datetime.now(ZoneInfo("America/New_York"))
    curr_15m_start_min = (now_dt.minute // 15) * 15
    interval_start_dt = now_dt.replace(minute=curr_15m_start_min, second=0, microsecond=0)
    start_time_12hr = interval_start_dt.strftime("%I:%M %p").lstrip('0')

    if n_rows > 0:
        active_target = round(float(df_ind.iloc[-1]["open"]), 2)
        target_source = f"15M Start Price ({start_time_12hr} ET)"
    else:
        active_target = float(curr_price)
        target_source = "15M Start Price"

    # Fetch auxiliary external datasets concurrently (Kalshi, Binance Futures, Fear & Greed)
    kalshi_m = None
    futures_data = None
    fng_data = None

    try:
        from concurrent.futures import ThreadPoolExecutor
        try:
            from backend.btc.kalshi_client import get_kalshi_15m_market
            from backend.btc.data_fetcher import get_binance_futures_data, get_fear_and_greed_index
        except ImportError:
            from kalshi_client import get_kalshi_15m_market
            from data_fetcher import get_binance_futures_data, get_fear_and_greed_index

        global _ANALYZER_EXECUTOR
        if _ANALYZER_EXECUTOR is None:
            _ANALYZER_EXECUTOR = ThreadPoolExecutor(max_workers=3)

        fut_kalshi = _ANALYZER_EXECUTOR.submit(get_kalshi_15m_market, series_ticker=f"KX{asset}15M")
        fut_futures = _ANALYZER_EXECUTOR.submit(get_binance_futures_data)
        fut_fng = _ANALYZER_EXECUTOR.submit(get_fear_and_greed_index)

        kalshi_m = fut_kalshi.result()
        futures_data = fut_futures.result()
        fng_data = fut_fng.result()

        if kalshi_m and kalshi_m.get("target_price"):
            active_target = float(kalshi_m["target_price"])
            target_source = "Kalshi Official Strike"
    except Exception as e:
        logger.error(f"Error fetching auxiliary datasets in analyzer: {e}")

    last_5_targets = compute_last_5_targets(df_ind)
    try:
        from backend.btc.ml_engine import get_ml_engine
        import os
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        ml_engine = get_ml_engine(data_dir, trading_style="SNIPER", asset=asset)
    except Exception:
        ml_engine = None
    last_5_targets = enrich_targets_with_ml(last_5_targets, df_ind, ml_engine=ml_engine)

    higher_count = sum(1 for t in last_5_targets if t.get("direction") == "HIGHER" or t.get("arrow") == "▲")
    lower_count = len(last_5_targets) - higher_count

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

    # B. Multi-Timeframe Alignment (1H & 4H Trend via Resampling)
    try:
        # 1H Trend (compare current close vs close 4 bars ago, i.e., 1h ago)
        trend_1h_up = float(df["close"].iloc[-1]) >= float(df["close"].iloc[-5]) if len(df) >= 5 else True
        # 4H Trend (compare current close vs open 16 bars ago, i.e., 4h ago)
        trend_4h_up = float(df["close"].iloc[-1]) >= float(df["open"].iloc[-16]) if len(df) >= 16 else True

        if trend_1h_up and trend_4h_up:
            pred_weight += 16
            pred_factors.append("🌐 MTF Context: 1H & 4H Macro Trends are BULLISH (Strong alignment)")
        elif (not trend_1h_up) and (not trend_4h_up):
            pred_weight -= 16
            pred_factors.append("🌐 MTF Context: 1H & 4H Macro Trends are BEARISH (Strong downward pressure)")
        elif trend_1h_up and not trend_4h_up:
            pred_weight += 4
            pred_factors.append("🌐 MTF Context: 1H Bullish, but 4H Bearish (Mixed Macro)")
        else:
            pred_weight -= 4
            pred_factors.append("🌐 MTF Context: 1H Bearish, but 4H Bullish (Mixed Macro)")
    except Exception as e:
        logger.error(f"[MTF] Error resampling timeframe: {e}")
        # fallback
        macro_bull = ind_summary.get("macro_bull")
        if macro_bull is True:
            pred_weight += 10
            pred_factors.append("🌐 MTF Context: 1H Macro Trend Bullish (Price above 200 EMA)")
        elif macro_bull is False:
            pred_weight -= 10
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
            pred_factors.append(f"🟢 FVG Floor: Bullish imbalance support (${fvg['bottom']:.0f} - ${fvg['top']:.0f})")
        elif fvg["type"] == "BEARISH_FVG":
            pred_weight -= 10
            pred_factors.append(f"🔴 FVG Ceiling: Bearish imbalance resistance (${fvg['bottom']:.0f} - ${fvg['top']:.0f})")

    # D2. Order Blocks (SMC)
    for ob in obs[:2]:
        if ob["type"] == "BULLISH_OB":
            pred_weight += 15
            pred_factors.append(f"🟢 SMC Order Block: Bullish institutional footprint (${ob['bottom']:.0f} - ${ob['top']:.0f})")
        elif ob["type"] == "BEARISH_OB":
            pred_weight -= 15
            pred_factors.append(f"🔴 SMC Order Block: Bearish institutional footprint (${ob['bottom']:.0f} - ${ob['top']:.0f})")

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

    # I. Kalshi & Robinhood Top-of-Book Order Flow & Market Implied Odds
    if kalshi_m and "yes_prob" in kalshi_m:
        k_yes = float(kalshi_m["yes_prob"])
        k_no = float(kalshi_m.get("no_prob") or (100.0 - k_yes))
        imbalance = float(kalshi_m.get("orderbook_imbalance") or 0.0)
        spread = float(kalshi_m.get("spread") or 0.04)

        if k_yes >= 58.0:
            k_shift = min(22, int((k_yes - 50.0) * 0.7))
            pred_weight += k_shift
            pred_factors.append(f"🎲 Order Flow (Kalshi/RH): Implied market odds favor ABOVE ({k_yes:.1f}% YES, +{k_shift} pts)")
        elif k_yes <= 42.0:
            k_shift = min(22, int((50.0 - k_yes) * 0.7))
            pred_weight -= k_shift
            pred_factors.append(f"🎲 Order Flow (Kalshi/RH): Implied market odds favor BELOW ({k_no:.1f}% NO, -{k_shift} pts)")
        elif k_yes >= 53.0:
            pred_weight += 8
            pred_factors.append(f"🎲 Order Flow (Kalshi/RH): Bullish market bias ({k_yes:.1f}% YES)")
        elif k_yes <= 47.0:
            pred_weight -= 8
            pred_factors.append(f"🎲 Order Flow (Kalshi/RH): Bearish market bias ({k_no:.1f}% NO)")

        if imbalance > 20.0:
            pred_weight += 8
            pred_factors.append(f"📊 Book Imbalance: Institutional Bid Pressure (+{imbalance:.1f}% net buy size)")
        elif imbalance < -20.0:
            pred_weight -= 8
            pred_factors.append(f"📊 Book Imbalance: Institutional Ask Capping ({imbalance:.1f}% net sell size)")

        if spread > 0 and spread <= 0.05:
            pred_factors.append(f"⚡ Market Liquidity: Tight Top-of-Book Spread (${spread:.2f})")

    # J. Advanced Signals: VWAP, Funding Rate, Volatility Regime
    vwap_val = ind_summary.get("vwap")
    if vwap_val and not pd.isna(vwap_val):
        if curr_price > vwap_val:
            pred_weight += 12
            pred_factors.append(f"📈 VWAP Context: Bullish (Price ${curr_price:.0f} > VWAP ${vwap_val:.0f})")
        else:
            pred_weight -= 12
            pred_factors.append(f"📉 VWAP Context: Bearish (Price ${curr_price:.0f} < VWAP ${vwap_val:.0f})")

    if futures_data:
        fr = futures_data.get("funding_rate", 0.0)
        oi = futures_data.get("open_interest", 0.0)
        
        # Funding rate is usually very small (e.g. 0.0001 = 0.01%)
        if fr > 0.0003: # High positive funding = overly long, risk of flush
            pred_weight -= 8
            pred_factors.append(f"⚠️ Funding Rate: Overheated (+{fr*100:.3f}%). Bearish contrarian signal.")
        elif fr < -0.0001: # Negative funding = overly short, short squeeze risk
            pred_weight += 8
            pred_factors.append(f"🚀 Funding Rate: Negative ({fr*100:.3f}%). Bullish squeeze potential.")
            
        if oi > 0:
            pred_factors.append(f"🧮 Futures Open Interest: {oi:,.0f} BTC")

    atr_pct = ind_summary.get("atr_percentile", 50.0)
    if atr_pct < 20.0:
        # Chop regime: shrink edge
        pred_weight = pred_weight * 0.7
        pred_factors.append(f"🥱 Volatility Regime: Low volatility chop (ATR {atr_pct:.1f}th percentile). Edges reduced.")
    elif atr_pct > 80.0:
        pred_factors.append(f"🌪️ Volatility Regime: High expansion (ATR {atr_pct:.1f}th percentile). Expected larger swings.")

    # Phase 3: Fear & Greed Index
    if fng_data:
        fng_val = fng_data.get("value", 50)
        
        if fng_val >= 80:
            pred_weight -= 6
            pred_factors.append(f"😱 Macro Sentiment: Extreme Greed ({fng_val}). Market overheated, mean-reversion risk.")
        elif fng_val <= 25:
            pred_weight += 6
            pred_factors.append(f"🥶 Macro Sentiment: Extreme Fear ({fng_val}). Over-sold, relief bounce likely.")
        else:
            pred_factors.append(f"🧭 Macro Sentiment: {fng_data.get('classification', 'Neutral')} ({fng_val}).")

    # Phase 3: Major Psychological Levels ($5k increments)
    nearest_5k = round(curr_price / 5000.0) * 5000.0
    dist_to_5k = curr_price - nearest_5k
    if abs(dist_to_5k) < 150: # Within $150 of a major $5k level (e.g. $70,000, $75,000)
        if dist_to_5k < 0:
            # Approaching from below, acts as heavy resistance
            pred_weight -= 10
            pred_factors.append(f"🧱 Psychological Level: Heavy resistance approaching ${nearest_5k:,.0f} wall.")
        else:
            # Sitting just above, acts as heavy support
            pred_weight += 10
            pred_factors.append(f"🛡️ Psychological Level: Heavy support resting on ${nearest_5k:,.0f} floor.")

    # -------------------------------------------------------------------------
    # Calibrated Probability Blending
    # -------------------------------------------------------------------------
    p_tech_shift = (pred_weight / 140.0) * 35.0
    decay_weight_factor = min(0.88, max(0.40, 1.0 - (minutes_remaining / 16.0)))
    
    # 1. Base rule-based probability
    p_rules = (decay_weight_factor * p_decay) + ((1.0 - decay_weight_factor) * (50.0 + p_tech_shift))

    # Phase 4: Machine Learning Overlay
    p_ml = 50.0
    try:
        from backend.btc.ml_engine import get_ml_engine
        import os
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        ml_engine = get_ml_engine(data_dir, trading_style="SNIPER", asset=asset)
        
        if not ml_engine.is_trained:
            logger.info("[Analyzer] ML Engine untrained. Auto-training on historical market data...")
            ml_engine.self_train_on_historical_market(df_ind)
        
        # Build live features to pass to ML via unified builder
        c_last = df_ind.iloc[-1] if len(df_ind) > 0 else None
        p_last = df_ind.iloc[-2] if len(df_ind) >= 2 else c_last
        current_raw_features = build_live_ml_features(
            df_ind=df_ind,
            c=c_last,
            p=p_last,
            target=active_target,
            kalshi_m=kalshi_m,
            futures_data=futures_data,
            fng_data=fng_data,
            cb_ob=cb_ob,
            minutes_remaining=minutes_remaining,
            heuristic_score=float(pred_weight),
        )
        
        ml_prob_raw = ml_engine.predict_probability(current_raw_features)
        p_ml = ml_prob_raw * 100.0
        
        if ml_engine.is_trained:
            if p_ml >= 55.0:
                pred_factors.append(f"🧠 ML Engine Overlay: AI Model favors UP ({p_ml:.1f}% Confidence based on historical trades)")
            elif p_ml <= 45.0:
                pred_factors.append(f"🧠 ML Engine Overlay: AI Model favors DOWN ({100.0 - p_ml:.1f}% Confidence based on historical trades)")
            else:
                pred_factors.append(f"🧠 ML Engine Overlay: AI Model is neutral ({p_ml:.1f}% Confidence)")
    except Exception as e:
        logger.error(f"[Analyzer] Failed to load or predict with ML Engine: {e}")

    # Blend Rules + ML with confidence-aware weighting (Task 2)
    try:
        raw_w = ml_engine.get_ml_confidence_weight(THRESHOLDS["analyze_ml_weight"])
        effective_ml_weight = float(raw_w) if isinstance(raw_w, (int, float)) else float(THRESHOLDS["analyze_ml_weight"])
    except (TypeError, ValueError, AttributeError):
        effective_ml_weight = float(THRESHOLDS["analyze_ml_weight"])
    effective_rules_weight = 1.0 - effective_ml_weight
    if p_ml != 50.0 and effective_ml_weight > 0.0:
        p_final = (p_rules * effective_rules_weight) + (p_ml * effective_ml_weight)
    else:
        p_final = p_rules

    # Streak & Mean Reversion Dampener
    if higher_count >= 4 and target_delta > 0:
        p_final = max(52, p_final - 5)
        pred_factors.append(f"⚠️ Streak Warning: {higher_count} consecutive UP closes (Pullback risk elevated)")
    elif lower_count >= 4 and target_delta < 0:
        p_final = min(48, p_final + 5)
        pred_factors.append(f"⚠️ Streak Warning: {lower_count} consecutive DOWN closes (Oversold bounce risk elevated)")

    pred_prob = int(round(max(5, min(95, p_final))))
    pred_outcome = "ABOVE TARGET (OVER)" if pred_prob >= 50 else "BELOW TARGET (UNDER)"
    # `pred_prob` represents the probability of an ABOVE close. Expose a
    # direction-aligned confidence for UI cards that display the chosen side.
    predicted_outcome_probability = pred_prob if pred_prob >= 50 else 100 - pred_prob

    if pred_prob >= 80 or pred_prob <= 20:
        conf_badge = "LOCKED RUNWAY"
    elif pred_prob >= 70 or pred_prob <= 30:
        conf_badge = "HIGH CONVICTION"
    elif pred_prob >= 60 or pred_prob <= 40:
        conf_badge = "MODERATE EDGE"
    else:
        conf_badge = "TIGHT PIVOT BATTLE"

    # -------------------------------------------------------------------------
    # 15M Prediction Accuracy Evaluator (Starts Counting Amount Right from 1)
    # -------------------------------------------------------------------------
    # Evaluate the most recently completed 15M interval
    last_cand = df_ind.iloc[-2] if n_rows >= 2 else df_ind.iloc[-1]
    prev_cand = df_ind.iloc[-3] if n_rows >= 3 else df_ind.iloc[-2] if n_rows >= 2 else df_ind.iloc[-1]
    
    # Autonomous Next 15M Contract Rollover Forecast Engine
    next_contract_forecast = evaluate_next_15m_contract(df_ind, target_price=active_target, patterns=patterns, structure=structure, kalshi_m=kalshi_m)

    # Extract Raw Features for ML Pipeline
    raw_features = {
        "rsi": ind_summary.get("rsi", 50),
        "macd_hist": ind_summary.get("macd_hist", 0.0),
        "atr_percentile": ind_summary.get("atr_percentile", 50.0),
        "volume_ratio": ind_summary.get("vol_ratio", 1.0),
        "funding_rate": futures_data.get("funding_rate", 0.0) if futures_data else 0.0,
        "fng_index": fng_data.get("value", 50) if fng_data else 50,
        "delta_to_target": target_delta_pct,
        "minutes_remaining": minutes_remaining,
        "cvd_value": float(df_ind["cvd"].iloc[-1]) if "cvd" in df_ind.columns else 0.0
    }

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
        "predicted_outcome_probability": predicted_outcome_probability,
        "confidence_badge": conf_badge,
        "decision_factors": pred_factors,
        "last_5_targets": last_5_targets,
        "streak_summary": f"{higher_count} Higher / {lower_count} Lower",
        "next_contract_forecast": next_contract_forecast,
        "raw_features": raw_features
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




def evaluate_next_15m_contract(df_ind: pd.DataFrame, target_price: float = None, patterns: list = None, structure: dict = None, kalshi_m: dict = None, trading_style: str = "SNIPER", asset: str = "BTC") -> dict:
    """
    Evaluates the just-finalized candle and pattern scanner to forecast
    the direction of the next 15m interval.
    If target_price is provided, it forecasts P(Close > target_price).
    """
    n = len(df_ind)
    if n < 5:
        return {
            "recommendation": "PASS / NO BID (CHOP)",
            "direction": "PASS",
            "action_type": "PASS",
            "probability_percent": 50,
            "predicted_probability": 0.5,
            "ml_prob": 0.5,
            "pre_gate_direction": "PASS",
            "pre_gate_prob": 50.0,
            "pre_gate_grade": "GRADE C / PASS",
            "conviction_grade": "GRADE C / PASS",
            "conviction_badge": "⚪ PASS (CHOP)",
            "target_settlement_zone": "--",
            "primary_edge": "Insufficient historical candles for contract evaluation",
            "catalysts": ["Waiting for interval data"]
        }

    # For mid-candle styles (MOMENTUM_SURFER, AMBUSH, BLEND), evaluate the live active candle.
    # For SNIPER (executed at rollover), evaluate the finalized candle at index -2.
    if trading_style in ["MOMENTUM_SURFER", "AMBUSH", "BLEND"]:
        c = df_ind.iloc[-1]
        p = df_ind.iloc[-2] if n >= 2 else df_ind.iloc[-1]
        p2 = df_ind.iloc[-3] if n >= 3 else df_ind.iloc[-2]
    else:
        c = df_ind.iloc[-2] if n >= 2 else df_ind.iloc[-1]
        p = df_ind.iloc[-3] if n >= 3 else df_ind.iloc[-2]
        p2 = df_ind.iloc[-4] if n >= 4 else df_ind.iloc[-3]
        
    active_cand = df_ind.iloc[-1]

    target = target_price if target_price is not None else float(active_cand["open"])
    c_open = float(c["open"])
    c_close = float(c["close"])
    c_high = float(c["high"])
    c_low = float(c["low"])
    rng = max(1e-5, c_high - c_low)

    lower_wick = (min(c_open, c_close) - c_low) / rng
    upper_wick = (c_high - max(c_open, c_close)) / rng
    range_closure = (c_close - c_low) / rng

    rsi = float(c.get("rsi", 50))
    bb_upper = float(c.get("bb_upper", c_high))
    bb_lower = float(c.get("bb_lower", c_low))
    ema_9 = float(c.get("ema_9", c_close))
    ema_21 = float(c.get("ema_21", c_close))
    ema_50 = float(c.get("ema_50", c_close))
    atr = float(c.get("atr", 120))

    # 0. Empirical Strike Pin / Dead-Zone Filter (Directly addresses 32.5% of historical losses)
    # When price is pinned within $15 of the strike and volatility is low (ATR <= $45),
    # the contract expiration second is an unpredictable coin-flip on single-tick noise.
    delta_dollars = abs(c_close - target)
    delta_to_target = float(((c_close - target) / max(target, 1e-9)) * 100)
    avg_vol_20 = float(df_ind["volume"].tail(20).mean()) if "volume" in df_ind.columns and len(df_ind) >= 20 else 1.0
    curr_vol = float(c.get("volume", 0.0) or 0.0)
    is_strong_breakout = (curr_vol > avg_vol_20 * 1.8) and (abs(c_close - c_open) > atr * 0.75)

    # ML Temporal & Volume Ratio Features
    try:
        c_time = int(c.get("time", time.time()))
        dt_ny = datetime.fromtimestamp(c_time, ZoneInfo("America/New_York"))
        is_weekend = 1.0 if dt_ny.weekday() >= 5 else 0.0
        hour_of_day = float(dt_ny.hour)
    except Exception:
        is_weekend = 0.0
        hour_of_day = 12.0
    
    try:
        avg_vol_3d = float(df_ind["volume"].tail(288).mean()) if "volume" in df_ind.columns and len(df_ind) >= 20 else 1.0
        volume_15m_ratio = curr_vol / max(avg_vol_3d, 1e-9)
    except Exception:
        volume_15m_ratio = 1.0

    

    # 1. Pre-fetch Microstructure, Derivatives & 1-Hour Trend Before ML Prediction
    cb_imbalance = 0.0
    try:
        from backend.btc.data_fetcher import get_coinbase_orderbook_imbalance
        cb_ob = get_coinbase_orderbook_imbalance()
        cb_imbalance = float(cb_ob.get("imbalance", 0.0))
    except Exception as _e:
        logger.debug(f"[Analyzer] Coinbase orderbook imbalance unavailable: {_e}")

    funding_rate = 0.0
    open_interest = 0.0
    try:
        from backend.btc.data_fetcher import get_binance_futures_data
        fut = get_binance_futures_data()
        if fut:
            funding_rate = float(fut.get("funding_rate", 0.0))
            open_interest = float(fut.get("open_interest", 0.0))
    except Exception as _e:
        logger.debug(f"[Analyzer] Futures data unavailable: {_e}")

    liquidation_data = {"net_imbalance_usd": 0.0, "short_liquidations_usd": 0.0, "long_liquidations_usd": 0.0}
    try:
        from backend.btc.liquidation_stream import get_liquidation_imbalance
        liquidation_data = get_liquidation_imbalance()
    except Exception as _e:
        logger.debug(f"[Analyzer] Liquidation data unavailable: {_e}")

    fng_value = 50.0
    try:
        from backend.btc.data_fetcher import get_fear_and_greed_index
        fng = get_fear_and_greed_index()
        if fng:
            fng_value = float(fng.get("value", 50.0))
    except Exception as _e:
        logger.debug(f"[Analyzer] Fear & Greed unavailable: {_e}")

    # Calculate real-time technical momentum score (matching ML training feature distribution)
    tech_score = (rsi - 50.0) * 0.8 + (10.0 if ema_9 >= ema_21 else -10.0)
    tech_score = max(-50.0, min(50.0, tech_score))
    cvd_val = float(df_ind["cvd"].iloc[-1]) if "cvd" in df_ind.columns else 0.0

    # 1-Hour Macro Trend Detection from in-memory 15m candle stream
    trend_1h = "NEUTRAL"
    try:
        if len(df_ind) >= 30:
            dt_col = df_ind["datetime"] if "datetime" in df_ind.columns else pd.to_datetime(df_ind["timestamp"], unit="s", utc=True)
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
    except Exception as _e_1h:
        logger.debug(f"[Analyzer] 1h trend computation: {_e_1h}")

    pred = None
    grade = "GRADE C / ML MODEL"
    badge = "🤖 ML MODEL"
    prob = 50
    catalysts = []

    now_epoch = int(time.time())
    seconds_remaining = max(10, 900 - (now_epoch % 900))
    minutes_remaining = max(0.15, seconds_remaining / 60.0)

    # 2. XGBoost Machine Learning Model Decision (fed with TRUE live features, not zeros)
    ml_prob = 0.50
    raw_ml_prob = 0.50
    ml_reasoning = ""
    try:
        from backend.btc.ml_engine import get_ml_engine
        import os
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        ml_engine = get_ml_engine(data_dir, trading_style=trading_style, asset=asset)
        
        if not ml_engine.is_trained:
            logger.info(f"[Analyzer] ML Engine untrained for {asset}_{trading_style}. Auto-training...")
            ml_engine.self_train_on_historical_market(df_ind)
            
        if ml_engine.is_trained:

            raw_feat = build_live_ml_features(
                df_ind=df_ind,
                c=c,
                p=p,
                target=target,
                kalshi_m=kalshi_m,
                futures_data=fut if "fut" in locals() and fut else None,
                fng_data=fng if "fng" in locals() and fng else None,
                cb_ob=cb_ob if "cb_ob" in locals() and cb_ob else None,
                minutes_remaining=minutes_remaining,
                heuristic_score=tech_score,
            )
            ml_prob, ml_reasoning = ml_engine.predict_with_reasoning(raw_feat)
            raw_ml_prob = float(ml_prob)
            

            
    except Exception as _e:
        logger.debug(f"[Analyzer] ML Predict error: {_e}")

    if ml_prob > 0.50:
        ml_pred = "BID YES (ABOVE TARGET)"
    elif ml_prob < 0.50:
        ml_pred = "BID NO (BELOW TARGET)"
    else:
        ml_pred = "PASS (NEUTRAL)"
        
    ml_prob_pct = max(51, int(ml_prob * 100)) if ml_prob > 0.50 else max(51, int((1.0 - ml_prob) * 100)) if ml_prob < 0.50 else 50
    ml_badge = f"🤖 ML MODEL ({ml_prob_pct}%)"
    ml_catalyst = f"Primary Driver: God-Tier PyTorch Ensemble predicts {'UP' if ml_prob >= 0.50 else 'DOWN'} ({ml_prob_pct}% Edge). {ml_reasoning}"


    # 1. Check Advanced Descending & Ascending Chart Patterns (Secondary Override/Confluence)
    if patterns:
        bearish_pats = [p for p in patterns if p.get("type") == "BEARISH"]
        bullish_pats = [p for p in patterns if p.get("type") == "BULLISH"]

        # Descending Pattern Priority (Bid NO)
        desc_triangle = next((p for p in bearish_pats if "Descending Triangle" in p.get("name", "")), None)
        head_shoulders = next((p for p in bearish_pats if "Head and Shoulders" in p.get("name", "")), None)
        bear_flag = next((p for p in bearish_pats if "Bear Flag" in p.get("name", "")), None)

        if desc_triangle:
            pred = "BID NO (BELOW TARGET)"
            grade = "GRADE A+ SETUP"
            badge = "🔥 5-STAR A+ (80%)"
            prob = 80
            catalysts.append(f"📉 Descending Triangle: {desc_triangle['description']}")
            catalysts.append("Breakdown Pressure: Multiple lower highs compressing horizontal support")

        elif head_shoulders:
            pred = "BID NO (BELOW TARGET)"
            grade = "GRADE A+ SETUP"
            badge = "🔥 5-STAR A+ (78%)"
            prob = 78
            catalysts.append(f"📉 Head & Shoulders Top: {head_shoulders['description']}")
            catalysts.append("Neckline Breach: Institutional distribution capping upside")

        elif bear_flag:
            pred = "BID NO (BELOW TARGET)"
            grade = "GRADE A SETUP"
            badge = "⚡ 4-STAR A (74%)"
            prob = 74
            catalysts.append(f"📉 Bear Flag: {bear_flag['description']}")
            catalysts.append("Trend Continuation: Weak flag consolidation into 15M downward thrust")

        # Ascending Pattern Priority (Bid YES)
        if not pred:
            asc_triangle = next((p for p in bullish_pats if "Ascending Triangle" in p.get("name", "")), None)
            bull_flag = next((p for p in bullish_pats if "Bull Flag" in p.get("name", "")), None)

            if asc_triangle:
                pred = "BID YES (ABOVE TARGET)"
                grade = "GRADE A+ SETUP"
                badge = "🔥 5-STAR A+ (80%)"
                prob = 80
                catalysts.append(f"📈 Ascending Triangle: {asc_triangle['description']}")
                catalysts.append("Breakout Pressure: Multiple higher lows pressing against ceiling")

            elif bull_flag:
                pred = "BID YES (ABOVE TARGET)"
                grade = "GRADE A SETUP"
                badge = "⚡ 4-STAR A (74%)"
                prob = 74
                catalysts.append(f"📈 Bull Flag: {bull_flag['description']}")
                catalysts.append("Trend Continuation: Shallow flag consolidation into 15M upward surge")

    # 1. GRADE A+ SETUPS (75% - 82% Historical Win Rate)
    if not pred:
        # A+ Setup 1: Bollinger Extreme Rejection Pin (Bid NO)
        if c_high >= bb_upper and upper_wick >= THRESHOLDS["bollinger_wick_min"] and rsi >= THRESHOLDS["bollinger_rsi_bear"]:
            pred = "BID NO (BELOW TARGET)"
            grade = "GRADE A+ SETUP"
            badge = "🔥 5-STAR A+ (78%)"
            prob = 78
            catalysts.append(f"Upper Bollinger Rejection: Heavy upper wick pin ({upper_wick*100:.0f}% of range)")
            catalysts.append(f"Overbought Exhaustion: RSI at {rsi:.1f} rejected off band ceiling")

        # A+ Setup 1: Bollinger Absorption Hammer (Bid YES)
        elif c_low <= bb_lower and lower_wick >= THRESHOLDS["bollinger_wick_min"] and rsi <= THRESHOLDS["bollinger_rsi_bull"]:
            pred = "BID YES (ABOVE TARGET)"
            grade = "GRADE A+ SETUP"
            badge = "🔥 5-STAR A+ (78%)"
            prob = 78
            catalysts.append(f"Lower Bollinger Absorption: Long lower wick hammer ({lower_wick*100:.0f}% of range)")
            catalysts.append(f"Oversold Spring: RSI at {rsi:.1f} reclaimed off band floor")

        # A+ Setup 2: Liquidity Sweep Rejection (Turtle Soup)
        else:
            low_4 = min(float(df_ind.iloc[j]["low"]) for j in range(max(0, n-6), n-2))
            high_4 = max(float(df_ind.iloc[j]["high"]) for j in range(max(0, n-6), n-2))

            if c_low < low_4 and c_close > low_4 and c_close >= c_open:
                pred = "BID YES (ABOVE TARGET)"
                grade = "GRADE A+ SETUP"
                badge = "🔥 5-STAR A+ (76%)"
                prob = 76
                catalysts.append(f"Bullish Liquidity Sweep: Reclaimed 4-bar low (${low_4:,.0f})")
                catalysts.append("Institutional Stop Hunt complete: Sellers trapped on dip")

            elif c_high > high_4 and c_close < high_4 and c_close <= c_open:
                pred = "BID NO (BELOW TARGET)"
                grade = "GRADE A+ SETUP"
                badge = "🔥 5-STAR A+ (76%)"
                prob = 76
                catalysts.append(f"Bearish Liquidity Sweep: Rejected 4-bar high (${high_4:,.0f})")
                catalysts.append("Overhead Capping complete: Buyers trapped on spike")

    # 2. GRADE A SETUPS (65% - 74% Historical Win Rate)
    # A Setup 1: 3-Candle Climax Exhaustion (only if no A+ pattern already set)
    if not pred:
        # A Setup 1: 3-Candle Climax Exhaustion (only if no A+ pattern already set)
        if float(c["close"]) > float(c["open"]) and float(p["close"]) > float(p["open"]) and float(p2["close"]) > float(p2["open"]):
            if trend_1h == "BULLISH":
                # Strong macro trend continuation - ride the momentum UP instead of fading it!
                grade = "GRADE A SETUP"
                badge = "⚡ 4-STAR A (74%)"
                prob = 74
                pred = "BID YES (ABOVE TARGET)"
                catalysts.append("Triple Green Trend Continuation: 3 consecutive bull bars aligned with 1H Bullish Macro")
                catalysts.append("Momentum Acceleration: Trend continuation riding high buying pressure")
            elif rsi >= THRESHOLDS["climax_rsi_bear"]:
                # Only fade the 3 green bars if macro trend is NOT strongly bullish (exhaustion pullback)
                grade = "GRADE A SETUP"
                badge = "⚡ 4-STAR A (72%)"
                prob = 72
                pred = "BID NO (BELOW TARGET)"
                catalysts.append("Triple Green Climax: 3 consecutive bull candles into resistance (Counter-trend/Range)")
                catalysts.append(f"Momentum Deceleration: RSI at {rsi:.1f} signals high pullback probability")

        elif float(c["close"]) < float(c["open"]) and float(p["close"]) < float(p["open"]) and float(p2["close"]) < float(p2["open"]):
            if trend_1h == "BEARISH":
                # Strong macro trend continuation - ride the momentum DOWN instead of catching a falling knife
                grade = "GRADE A SETUP"
                badge = "⚡ 4-STAR A (74%)"
                prob = 74
                pred = "BID NO (BELOW TARGET)"
                catalysts.append("Triple Red Trend Continuation: 3 consecutive bear bars aligned with 1H Bearish Macro")
                catalysts.append("Downward Acceleration: Trend continuation riding heavy selling pressure")
            elif rsi <= THRESHOLDS["climax_rsi_bull"]:
                grade = "GRADE A SETUP"
                badge = "⚡ 4-STAR A (72%)"
                prob = 72
                pred = "BID YES (ABOVE TARGET)"
                catalysts.append("Triple Red Climax: 3 consecutive bear candles deeply oversold (Counter-trend/Range)")
                catalysts.append(f"Exhaustion Spring: RSI at {rsi:.1f} signals strong mean-reversion bounce")

        # A Setup 2: EMA Ribbon Dynamic Pullback
        elif ema_9 > ema_21 > ema_50 and c_low <= ema_21 and c_close > ema_21 and lower_wick >= THRESHOLDS["ribbon_wick_min"]:
            grade = "GRADE A SETUP"
            badge = "⚡ 4-STAR A (70%)"
            prob = 70
            pred = "BID YES (ABOVE TARGET)"
            catalysts.append("Bullish Ribbon Trend: EMA 21 dynamic support held cleanly")
            catalysts.append("Dip Absorption: Buyers defended 15M moving average into close")

        elif ema_9 < ema_21 < ema_50 and c_high >= ema_21 and c_close < ema_21 and upper_wick >= THRESHOLDS["ribbon_wick_min"]:
            grade = "GRADE A SETUP"
            badge = "⚡ 4-STAR A (70%)"
            prob = 70
            pred = "BID NO (BELOW TARGET)"
            catalysts.append("Bearish Ribbon Trend: EMA 21 dynamic resistance capped rally")
            catalysts.append("Overhead Supply: Sellers rejected 15M moving average into close")

    # 3. GRADE B SETUPS (60% - 64% Historical Win Rate) — only if no A/A+ set
    if not pred:
        # B Setup 1: Dual Green/Red Reversion (Macro trend aware)
        if float(c["close"]) > float(c["open"]) and float(p["close"]) > float(p["open"]):
            if trend_1h == "BULLISH":
                grade = "GRADE B+ SETUP"
                badge = "⚠️ 3-STAR B+ (64%)"
                prob = 64
                pred = "BID YES (ABOVE TARGET)"
                catalysts.append("Dual Green Trend Alignment: Bullish continuation with 1H Macro")
            elif rsi >= THRESHOLDS["b_setup_rsi_bear"]:
                grade = "GRADE B+ SETUP"
                badge = "⚠️ 3-STAR B+ (63%)"
                prob = 63
                pred = "BID NO (BELOW TARGET)"
                catalysts.append("Dual Green Surge: Consecutive bullish closes approaching mean reversion")
        elif float(c["close"]) < float(c["open"]) and float(p["close"]) < float(p["open"]):
            if trend_1h == "BEARISH":
                grade = "GRADE B+ SETUP"
                badge = "⚠️ 3-STAR B+ (64%)"
                prob = 64
                pred = "BID NO (BELOW TARGET)"
                catalysts.append("Dual Red Trend Alignment: Bearish continuation with 1H Macro")
            elif rsi <= THRESHOLDS["b_setup_rsi_bull"]:
                grade = "GRADE B+ SETUP"
                badge = "⚠️ 3-STAR B+ (63%)"
                prob = 63
                pred = "BID YES (ABOVE TARGET)"
                catalysts.append("Dual Red Dip: Consecutive bearish closes approaching oversold rebound")

        # B Setup 2: Momentum Thrust
        elif range_closure >= THRESHOLDS["thrust_range_closure_bull"] and (abs(c_close - c_open) / rng) >= THRESHOLDS["thrust_body_range_min"] and ema_9 > ema_21:
            grade = "GRADE B SETUP"
            badge = "⚠️ 3-STAR B (62%)"
            prob = 62
            pred = "BID YES (ABOVE TARGET)"
            catalysts.append("Bullish Momentum Thrust: Upper 20% range close with positive EMA slope")
        elif range_closure <= THRESHOLDS["thrust_range_closure_bear"] and (abs(c_close - c_open) / rng) >= THRESHOLDS["thrust_body_range_min"] and ema_9 < ema_21:
            grade = "GRADE B SETUP"
            badge = "⚠️ 3-STAR B (62%)"
            prob = 62
            pred = "BID NO (BELOW TARGET)"

    # 4. GRADE A SETUPS — RSI + Bollinger secondary confirmation (upgrade only)
    # A Setup 1: Strong RSI Momentum Break (Bid YES) — upgrade grade if already has direction
    if pred and rsi >= THRESHOLDS["rsi_bb_momentum_bull"] and c_close > bb_upper * 0.999:
        if "YES" in pred or "ABOVE" in pred:
            if "GRADE A+" not in grade:
                grade = "GRADE A SETUP"
                badge = "⚡ 4-STAR A (72%)"
                prob = max(prob, 72)
            catalysts.append(f"Overbought Expansion: High RSI ({rsi:.1f}) riding upper BB limit")

    # A Setup 2: Strong RSI Flush Break (Bid NO) — upgrade grade only if already bearish
    elif pred and rsi <= THRESHOLDS["rsi_bb_flush_bear"] and c_close < bb_lower * 1.001:
        if "NO" in pred or "BELOW" in pred:
            if "GRADE A+" not in grade:
                grade = "GRADE A SETUP"
                badge = "⚡ 4-STAR A (72%)"
                prob = max(prob, 72)
            catalysts.append(f"Oversold Flush: Low RSI ({rsi:.1f}) pressing lower BB limit")

    # 3. KALSHI/RH MARKET STRUCTURE EDGE (60% - 66% Historical Win Rate)
    # Re-evaluate with Order Book Imbalance if no A+ or A setup exists
    if kalshi_m and "GRADE A" not in grade:
        k_yes = float(kalshi_m.get("yes_ask", 50) if kalshi_m.get("yes_ask") else 50)
        k_no = float(kalshi_m.get("no_ask", 50) if kalshi_m.get("no_ask") else 50)
        imbalance = float(kalshi_m.get("book_imbalance", 0.0) if kalshi_m.get("book_imbalance") else 0.0)

        if k_yes >= THRESHOLDS["kalshi_override_yes"] or imbalance >= THRESHOLDS["kalshi_imbalance_threshold"]:
            pred = "BID YES (ABOVE TARGET)"
            grade = "GRADE B+ SETUP"
            badge = "⚠️ 3-STAR B+ (64%)"
            prob = max(prob, 64) if "YES" in pred else 64
            catalysts.append(f"Market Implied Bullish Edge: Order book odds favor YES ({k_yes:.1f}%)")
            catalysts.append(f"Institutional Order Flow: Net bid depth imbalance (+{imbalance:.1f}%)")
        elif k_no >= THRESHOLDS["kalshi_override_no"] or imbalance <= -THRESHOLDS["kalshi_imbalance_threshold"]:
            pred = "BID NO (BELOW TARGET)"
            grade = "GRADE B+ SETUP"
            badge = "⚠️ 3-STAR B+ (64%)"
            prob = max(prob, 64) if "NO" in pred else 64
            catalysts.append(f"Market Implied Bearish Edge: Order book odds favor NO ({k_no:.1f}%)")
            catalysts.append(f"Institutional Order Flow: Net ask depth imbalance ({imbalance:.1f}%)")

    # Capture the heuristic weight before blending with ML to prevent data leakage in training history
    heuristic_score_for_training = float(prob) if pred else 0.0

    # -------------------------------------------------------------------
    # Blend heuristic setup probability with live ML model probability.
    # Heuristic setups still decide the initial candidate direction/grade
    # (they encode chart-pattern domain knowledge the model doesn't see
    # directly), but the FINAL probability used for sizing/decisions is a
    # weighted blend with the model, not a hardcoded historical win rate.
    # Blend weights come from backend/btc/backtest.py's calibration output —
    # see backend/data/backtest_report.json. Default until re-tuned: 0.6/0.4.
    # -------------------------------------------------------------------
    
    # Read signal isolation setting
    try:
        from backend.btc.auto_executor import auto_executor
        iso_setting = auto_executor.ai_settings.get("signalIsolation", "BLEND")
    except Exception:
        iso_setting = "BLEND"

    # --- STYLE-SPECIFIC OVERRIDES ---
    if trading_style == "CHOP":
        # Mean Reversion Logic: Fade the Bollinger Bands
        if c_close >= bb_upper:
            # Overbought sideways -> Buy NO
            pred = "PASS / BID NO (CHOP FADE)"
            prob = 100.0
            grade = "GRADE A SETUP"
            catalysts.insert(0, "🏓 Chop Mean-Reversion: Price hit Upper Bollinger Band in sideways regime. Fading the move (BID NO).")
        elif c_close <= bb_lower:
            # Oversold sideways -> Buy YES
            pred = "PASS / BID YES (CHOP FADE)"
            prob = 100.0
            grade = "GRADE A SETUP"
            catalysts.insert(0, "🏓 Chop Mean-Reversion: Price hit Lower Bollinger Band in sideways regime. Fading the move (BID YES).")

    # If CHART_ONLY is active, bypass ML completely
    if iso_setting == "CHART_ONLY":
        if pred:
            catalysts.append("📊 Signal Isolation: 100% Chart Setup active, ignoring ML model.")
        else:
            catalysts.append("📊 Signal Isolation: 100% Chart Setup active, but no chart setup fired.")
            pred = "PASS"
            prob = 0.0

    # If AI_ONLY is active, bypass heuristic setups completely
    elif iso_setting == "AI_ONLY":
        pred = ml_pred
        if "PASS" in ml_pred:
            prob = 50.0
        else:
            prob = ml_prob * 100.0 if ("YES" in ml_pred or "ABOVE" in ml_pred) else (1.0 - ml_prob) * 100.0
        if prob >= 75:
            grade = "GRADE A+ SETUP"
        elif prob >= 70:
            grade = "GRADE A SETUP"
        elif prob >= 65:
            grade = "GRADE B+ SETUP"
        else:
            grade = "GRADE B SETUP"
        catalysts = [f"🧠 Signal Isolation: 100% AI Prediction active. Raw Prob: {prob:.1f}%"]
        heuristic_score_for_training = 0.0

    elif pred:
        # Convert ml_prob (P(close >= target)) into "probability of pred's direction"
        ml_prob_for_pred_dir = (ml_prob * 100.0) if ("YES" in pred or "ABOVE" in pred) else ((1.0 - ml_prob) * 100.0)

        try:
            raw_w = ml_engine.get_ml_confidence_weight(THRESHOLDS["ml_weight"])
            effective_ml_weight = float(raw_w) if isinstance(raw_w, (int, float)) else float(THRESHOLDS["ml_weight"])
        except (TypeError, ValueError, AttributeError):
            effective_ml_weight = float(THRESHOLDS["ml_weight"])
        effective_heuristic_weight = 1.0 - effective_ml_weight
        disagreement = abs(prob - ml_prob_for_pred_dir)
        blended_prob = (prob * effective_heuristic_weight) + (ml_prob_for_pred_dir * effective_ml_weight)

        if ml_prob_for_pred_dir < 50.0 and disagreement >= THRESHOLDS["model_conflict_threshold"]:
            catalysts.append(f"⚠️ Model Conflict: Chart setup favors {pred} ({prob}%) but ML model disagrees ({ml_prob_for_pred_dir:.1f}% for this side) - confidence capped")
            blended_prob = min(blended_prob, THRESHOLDS["model_conflict_cap"])
            if "GRADE A+" in grade:
                grade = "GRADE A SETUP"
        else:
            catalysts.append(
                f"🧠 ML Confirmation: Model agrees with {pred} ({ml_prob_for_pred_dir:.1f}%), "
                f"blended confidence {blended_prob:.1f}%"
            )

        prob = blended_prob
    else:
        # No heuristic setup fired at all — fall back to pure ML, as before.
        pred = ml_pred
        prob = ml_prob_pct
        badge = ml_badge
        catalysts.append(ml_catalyst)

    # Calculate Target Settlement Zone based on ATR dispersion
    if "PASS" in str(pred):
        z_min = target - (atr * 0.15)
        z_max = target + (atr * 0.15)
        direction = "PASS"
        action = "PASS"
        prob = 50
    elif "YES" in pred or "ABOVE" in pred:
        z_min = target + (atr * 0.15)
        z_max = target + (atr * 0.90)
        direction = "YES"
        action = "BID YES"
    else:
        z_min = target - (atr * 0.90)
        z_max = target - (atr * 0.15)
        direction = "NO"
        action = "BID NO"

    zone_str = f"${z_min:,.0f} - ${z_max:,.0f}"
    prob = min(98, max(50, prob))
    if direction == "PASS":
        prob = 50

    # 4. Kalshi Market-Implied Order Flow Confluence
    try:
        if kalshi_m:
            yes_p = float(kalshi_m.get("yes_prob", 50.0) or 50.0)
            if yes_p >= THRESHOLDS["kalshi_whales_extreme_yes"]:
                prob = min(99, prob + 5)
                catalysts.append(f"Kalshi Whales Heavily Bullish ({yes_p:.0f}% YES)")
            elif yes_p <= THRESHOLDS["kalshi_whales_extreme_no"]:
                prob = min(99, prob + 5)
                catalysts.append(f"Kalshi Whales Heavily Bearish ({yes_p:.0f}% YES)")
    except Exception as _e_km:
        logger.debug(f"[Analyzer] Kalshi market parsing: {_e_km}")

    # Capture candidate direction and probability prior to any safety filter overrides
    if "PASS" in str(pred) or "PASS" in str(direction):
        pre_gate_direction = "PASS"
    else:
        pre_gate_direction = "ABOVE" if ("YES" in str(pred) or "ABOVE" in str(direction)) else "BELOW"
    pre_gate_prob = float(prob)
    pre_gate_grade = grade

    # 5. Higher-Timeframe (1-Hour) Trend Confirmation Gate (REMOVED BY USER REQUEST)
    # The trend gate logic has been removed to allow counter-trend trades on the 15m timeframe.
    pass

    # 6. Active Pre-Trade CVD & Order Book Flow Gate (Directly addresses historical losses)
    # Fetch dynamic CVD overrides if present
    try:
        from backend.btc.auto_executor import auto_executor
        _ai = auto_executor.ai_settings
    except Exception:
        _ai = {}
    cvd_bear_limit = float(_ai.get("cvdBearLimit", THRESHOLDS["cvd_gate_bear_limit"]))
    cvd_bull_limit = float(_ai.get("cvdBullLimit", THRESHOLDS["cvd_gate_bull_limit"]))
    cvd_override_conf = float(_ai.get("cvdOverrideConf", 75))

    if direction != "PASS":
        if "YES" in str(pred) or direction == "YES":
            if cvd_val < cvd_bear_limit:
                if prob < cvd_override_conf:
                    direction = "PASS"
                    pred = "PASS"
                    grade = "GRADE C / PASS"
                    badge = "⚪ PASS (CVD DIVERGENCE)"
                    prob = 50
                    catalysts.append(f"CVD Volume Divergence: Spot selling pressure ({cvd_val:+.1f} < limit {cvd_bear_limit}) opposes YES entry (historical loss pattern)")
            elif cb_imbalance <= THRESHOLDS["imbalance_gate_bear_wall"]:
                direction = "PASS"
                pred = "PASS"
                grade = "GRADE C / PASS"
                badge = "⚪ PASS (SPOT SELL WALL)"
                prob = 50
                catalysts.append(f"Orderbook Imbalance: Heavy ask wall ({cb_imbalance:.1f}%) blocks YES upside")
            elif liquidation_data["long_liquidations_usd"] > 2_000_000:
                direction = "PASS"
                pred = "PASS"
                grade = "GRADE C / PASS"
                badge = "⚪ PASS (LONG SQUEEZE)"
                prob = 50
                catalysts.append(f"Liquidation Cascade: ${liquidation_data['long_liquidations_usd']/1e6:.1f}M in longs liquidated. Downside momentum too risky to fade.")

        elif "NO" in str(pred) or direction == "NO":
            if cvd_val > cvd_bull_limit:
                if prob < cvd_override_conf:
                    direction = "PASS"
                    pred = "PASS"
                    grade = "GRADE C / PASS"
                    badge = "⚪ PASS (CVD DIVERGENCE)"
                    prob = 50
                    catalysts.append(f"CVD Volume Divergence: Spot buying pressure ({cvd_val:+.1f}) opposes NO entry (historical loss pattern)")
            elif cb_imbalance >= THRESHOLDS["imbalance_gate_bid_wall"]:
                direction = "PASS"
                pred = "PASS"
                grade = "GRADE C / PASS"
                badge = "⚪ PASS (SPOT BUY WALL)"
                prob = 50
                catalysts.append(f"Orderbook Imbalance: Heavy bid wall (+{cb_imbalance:.1f}%) blocks NO downside")
            elif liquidation_data["short_liquidations_usd"] > 2_000_000:
                direction = "PASS"
                pred = "PASS"
                grade = "GRADE C / PASS"
                badge = "⚪ PASS (SHORT SQUEEZE)"
                prob = 50
                catalysts.append(f"Liquidation Cascade: ${liquidation_data['short_liquidations_usd']/1e6:.1f}M in shorts liquidated. Upside momentum too risky to fade.")

    # Final Chop / Weak Edge check
    if grade == "GRADE C / ML MODEL" and 45 <= prob <= 55:
        direction = "PASS"
        pred = "PASS"
        grade = "GRADE C / PASS"
        badge = "⚪ PASS (CHOP)"
        prob = 50
        catalysts = ["Model edge too weak. Sitting out."]

    news_sentiment_val = 0.0
    try:
        from backend.btc.news_fetcher import get_news_sentiment_summary
        news_sentiment_val = float(get_news_sentiment_summary().get("sentiment_score", 0.0))
    except Exception:
        news_sentiment_val = 0.0

    # Comprehensive Feature Vector for Ledger and Future Model Self-Training
    raw_features = {
        "rsi": float(rsi),
        "bb_upper": float(bb_upper),
        "bb_lower": float(bb_lower),
        "ema_9": float(ema_9),
        "ema_21": float(ema_21),
        "ema_50": float(ema_50),
        "atr": float(atr),
        "price_vs_vwap": float(c_close - c.get("vwap")) if c.get("vwap") is not None and not pd.isna(c.get("vwap")) else 0.0,
        "cvd_value": cvd_val,
        "delta_to_target": delta_to_target,
        "heuristic_score": float(heuristic_score_for_training),
        "news_sentiment_score": news_sentiment_val,
        "fng_value": fng_value,
        "high_24h": float(df_ind["high"].max()) if len(df_ind) > 0 else c_close,
        "low_24h": float(df_ind["low"].min()) if len(df_ind) > 0 else c_close,
        "volume_24h": float(df_ind["volume"].tail(96).sum()) if len(df_ind) > 0 else 0.0,
        "orderbook_imbalance": cb_imbalance,
        "funding_rate": funding_rate,
        "open_interest": open_interest,
        "is_weekend": is_weekend,
        "hour_of_day": hour_of_day,
        "volume_15m_ratio": volume_15m_ratio,
        "upper_wick_ratio": float(upper_wick),
        "lower_wick_ratio": float(lower_wick),
        "body_to_range": float(abs(c_close - c_open) / rng),
        "range_24h_pos": float((c_close - (float(df_ind["low"].min()) if len(df_ind) > 0 else c_close)) / max(1.0, (float(df_ind["high"].max()) if len(df_ind) > 0 else c_close) - (float(df_ind["low"].min()) if len(df_ind) > 0 else c_close))),
        "trend_1h": trend_1h,
        "minutes_remaining": float(minutes_remaining),
        "kalshi_yes_prob": float(kalshi_m.get("yes_prob", 50.0)) if kalshi_m else 50.0,
        "kalshi_book_imbalance": float(kalshi_m.get("orderbook_imbalance", kalshi_m.get("book_imbalance", 0.0))) if kalshi_m else 0.0,
        "roc_15m": float(df_ind["roc_15m"].iloc[-1]) if "roc_15m" in df_ind.columns else 0.0,
        "roc_1h": float(df_ind["roc_1h"].iloc[-1]) if "roc_1h" in df_ind.columns else 0.0,
        "roc_4h": float(df_ind["roc_4h"].iloc[-1]) if "roc_4h" in df_ind.columns else 0.0,
        "cvd_divergence": cvd_val / (float(atr) + 1e-5),
        "vol_regime_percentile": float(
            (df_ind["atr"].dropna().tail(min(96, len(df_ind["atr"].dropna()))) <= float(atr)).mean()
        ) if "atr" in df_ind.columns and len(df_ind["atr"].dropna()) >= 10 else 0.5,
    }

    # C3 FIX: Compute and inject the 25 lag features the LSTM/Ensemble expects.
    # These were previously missing from the training ledger, causing the model to train on zeros.
    lag_source_features = ["bb_percent_b", "rsi", "volume_15m_ratio", "roc_15m", "cvd_divergence"]
    n_ind = len(df_ind)
    ref_idx = n_ind - 2 if n_ind >= 2 else n_ind - 1  # Same reference as candle 'c'
    for step in range(4, -1, -1):
        c_idx = ref_idx - step
        for feat in lag_source_features:
            key = f"{feat}_lag_{step}"
            val = 0.5  # safe default
            if 0 <= c_idx < n_ind:
                try:
                    if feat == "bb_percent_b":
                        row = df_ind.iloc[c_idx]
                        bb_u = float(row.get("bb_upper", 1.0))
                        bb_l = float(row.get("bb_lower", 0.0))
                        bb_range = bb_u - bb_l
                        val = float((float(row["close"]) - bb_l) / bb_range) if bb_range > 0 else 0.5
                    elif feat == "rsi":
                        val = float(df_ind.iloc[c_idx].get("rsi", 50.0)) / 100.0
                    elif feat == "volume_15m_ratio":
                        avg_vol = float(df_ind["volume"].tail(288).mean()) if len(df_ind) >= 20 else 1.0
                        val = float(df_ind.iloc[c_idx].get("volume", avg_vol)) / max(avg_vol, 1e-9)
                    elif feat == "roc_15m":
                        val = float(df_ind.iloc[c_idx].get("roc_15m", 0.0))
                    elif feat == "cvd_divergence":
                        cvd_v = float(df_ind.iloc[c_idx].get("cvd", 0.0)) if "cvd" in df_ind.columns else 0.0
                        atr_v = float(df_ind.iloc[c_idx].get("atr", 100.0))
                        val = cvd_v / (atr_v + 1e-5)
                except Exception:
                    pass
            raw_features[key] = val


    return {
        "recommendation": f"{grade} ({direction})",

        "direction": direction,
        "action_type": pred,
        "probability_percent": int(prob),
        "predicted_probability": round(float(prob) / 100.0, 4),
        "ml_prob": round(float(ml_prob), 4),
        "raw_ml_prob": round(float(raw_ml_prob), 4),
        "pre_gate_direction": pre_gate_direction,
        "pre_gate_prob": round(float(pre_gate_prob), 2),
        "pre_gate_grade": pre_gate_grade,
        "conviction_grade": grade,
        "conviction_badge": badge,
        "target_settlement_zone": "--",
        "primary_edge": "High Confluence Setup" if "GRADE A" in grade else "Moderate Confluence Setup",
        "catalysts": catalysts,
        "raw_features": raw_features
    }


def analyze_btc_15m(df: pd.DataFrame, asset: str = "BTC") -> dict:
    """Backwards-compatibility alias."""
    return analyze_btc(df, asset=asset, timeframe="15m")


if __name__ == "__main__":
    from data_fetcher import fetch_15m_candles
    df = fetch_15m_candles(limit=250)
    result = analyze_btc_15m(df)
    logger.info("=" * 60)
    logger.info(f"BTC 15-MINUTE ANALYSIS: {result['direction']}")
    logger.info(f"Current Price: ${result['price']:.2f}")
    logger.info(f"Confluence Score: {result['confluence_score']} / 100")
    logger.info(f"Confidence: {result['confidence_percent']}%")
    logger.info("=" * 60)
    logger.info("Bullish Factors:")
    for r in result["reasons_bullish"]:
        logger.info(f"  + {r}")
    logger.info("\nBearish Factors:")
    for r in result["reasons_bearish"]:
        logger.info(f"  - {r}")
    logger.info("\nTrade Setup:")
    for k, v in result["trade_setup"].items():
        logger.info(f"  {k}: {v}")
