
import logging

logger = logging.getLogger(__name__)
import json
import math
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests.exceptions

try:
    from backend.btc.data_fetcher import (get_binance_futures_data,
                                          get_coinbase_orderbook_imbalance,
                                          get_fear_and_greed_index)
    from backend.btc.indicators import (add_all_indicators, compute_ema,
                                        extract_indicator_summary)
    from backend.btc.kalshi_client import get_kalshi_15m_market
    from backend.btc.ml_engine import build_live_ml_features, get_ml_engine
    from backend.btc.news_fetcher import get_news_sentiment_summary
    from backend.btc.pattern_detector import (analyze_market_structure,
                                              analyze_wick_absorption,
                                              detect_candlestick_patterns,
                                              detect_fair_value_gaps,
                                              detect_liquidity_sweeps,
                                              detect_order_blocks)
    from backend.btc.trend_boxes import (compute_last_5_targets,
                                         enrich_targets_with_ml)
    from backend.engine.multi_asset_fetcher import \
        fetch_asset_candles as fetch_candles
except ImportError:
    from indicators import add_all_indicators, extract_indicator_summary, compute_ema
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
        enrich_targets_with_ml
    )
    from ml_engine import build_live_ml_features, get_ml_engine
    from data_fetcher import get_coinbase_orderbook_imbalance, get_binance_futures_data, get_fear_and_greed_index

from .config import THRESHOLDS
from .contract_eval import evaluate_next_15m_contract

_ANALYZER_EXECUTOR = None

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
        df_1h = fetch_candles(asset, "1h", limit=50)
        df_4h = fetch_candles(asset, "4h", limit=50)
        if df_1h is not None and not df_1h.empty:
            ema50_1h = compute_ema(df_1h["close"], 50).iloc[-1]
            macro_trend_1h = "BULLISH" if float(df_1h.iloc[-1]["close"]) > float(ema50_1h) else "BEARISH"
        if df_4h is not None and not df_4h.empty:
            ema50_4h = compute_ema(df_4h["close"], 50).iloc[-1]
            macro_trend_4h = "BULLISH" if float(df_4h.iloc[-1]["close"]) > float(ema50_4h) else "BEARISH"
    except Exception as e:
        logger.warning(f"MTF Macro Alignment Fetching failed: {e}")

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
                bullish_reasons.append("Volume Profile: Perfect rejection bounce off POC Support (+10)")
        elif curr_price < poc:
            score -= 8
            bearish_reasons.append(f"Volume Profile: Trading below 24H Point of Control (${poc:.1f}) (-8)")
            if curr_price >= poc * 0.998:
                score -= 10
                bearish_reasons.append("Volume Profile: Perfect rejection fade off POC Resistance (-10)")

    # CVD Acceleration (Trapped Trader Logic)
    cvd_accel = ind_summary.get("cvd_acceleration", 0.0)
    if cvd_accel > 0 and ind_summary.get("vol_surge"):
        score += 10
        bullish_reasons.append("CVD Acceleration: Fresh aggressive market buying detected (+10)")
    elif cvd_accel < 0 and ind_summary.get("vol_surge"):
        score -= 10
        bearish_reasons.append("CVD Acceleration: Aggressive market selling into volume surge (-10)")
    elif df_ind.iloc[-1]["close"] > df_ind.iloc[-1]["open"] and cvd_accel < 0:
        score -= 5
        bearish_reasons.append("TRAP DETECTED: Green candle with negative CVD (Short covering / Limit Selling absorption) (-5)")
    elif df_ind.iloc[-1]["close"] < df_ind.iloc[-1]["open"] and cvd_accel > 0:
        score += 5
        bullish_reasons.append("TRAP DETECTED: Red candle with positive CVD (Long liquidation / Limit Buying absorption) (+5)")

    # Clamp score to [-100, 100]
    

    # --- F. Derivatives & Market Microstructure (Weight: up to +-40) ---
    cb_ob = {}
    try:
        cb_ob = get_coinbase_orderbook_imbalance() or {}
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
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as _e:
        logger.warning(f"[Analyzer] Orderbook imbalance fetch failed: {_e}")

    try:
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
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as _e:
        logger.warning(f"[Analyzer] Kalshi market fetch failed: {_e}")

    try:
        futures = get_binance_futures_data()
        if futures:
            fr = futures.get('funding_rate', 0.0)
            if fr > 0.015:
                score -= 10
                bearish_reasons.append(f"Retail Over-leveraged Long (High Funding {fr:.4f}%) - Liquidation risk (-10)")
            elif fr < -0.015:
                score += 10
                bullish_reasons.append(f"Retail Heavily Short (Negative Funding {fr:.4f}%) - Short squeeze risk (+10)")
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as _e:
        logger.warning(f"[Analyzer] Binance futures fetch failed: {_e}")

    try:
        news_summary = get_news_sentiment_summary()
        n_score = news_summary.get("sentiment_score", 0.0)
        
        if n_score >= 0.15:
            score += int(n_score * 15)
            bullish_reasons.append(f"📰 Breaking News: Bullish sentiment (+{n_score:.2f}) (+{int(n_score * 15)})")
        elif n_score <= -0.15:
            score -= int(abs(n_score) * 15)
            bearish_reasons.append(f"📰 Breaking News: Bearish sentiment ({n_score:.2f}) (-{int(abs(n_score) * 15)})")
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as _e:
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

    from concurrent.futures import ThreadPoolExecutor
    try:
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
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
        logger.error(f"Error fetching auxiliary datasets in analyzer: {e}")

    last_5_targets = compute_last_5_targets(df_ind)
    try:
        import os
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        ml_engine = get_ml_engine(data_dir, trading_style="SNIPER", asset=asset)
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        logger.warning(f"ML engine init failed: {e}")
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
        # 1H Trend (compare current close vs close 4 bars ago, i.e., 1h ago)
    try:
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
    except (ValueError, TypeError, IndexError) as e:
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
    # Dynamic decay factor: allow technical momentum to drive the trade early (minutes 10-15),
    # gradually scaling up strike distance/theta lock in the final 5 minutes.
    decay_weight_factor = min(0.88, max(0.12, 1.0 - (minutes_remaining / 15.0)))
    
    # 1. Base rule-based probability
    p_rules = (decay_weight_factor * p_decay) + ((1.0 - decay_weight_factor) * (50.0 + p_tech_shift))

    # Phase 4: Machine Learning Overlay
    p_ml = 50.0
    try:
        import os
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        ml_engine = get_ml_engine(data_dir, trading_style="SNIPER", asset=asset)
        model_age = time.time() - getattr(ml_engine, "last_trained_mtime", 0.0)
        if not ml_engine.is_trained or model_age > 7 * 86400:
            logger.info(f"[Analyzer] ML Engine untrained or rolling retrain due ({model_age/86400:.1f}d old). Auto-training on historical market data...")
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
    except (json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError) as e:
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

    # Autonomous Next 15M Contract Rollover Forecast Engine
    next_contract_forecast = evaluate_next_15m_contract(df_ind, target_price=active_target, patterns=patterns, structure=structure, kalshi_m=kalshi_m, fvgs=fvgs, obs=obs, sweeps=sweeps, wicks=wicks)

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
        "target_benchmark": target_benchmark,
        "ml_prob": float(p_final / 100.0),
        "ml_probability": float(p_final / 100.0)
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

