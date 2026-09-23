import pandas as pd
import logging
from datetime import datetime
import pytz
from backend.btc.indicators import add_all_indicators, extract_indicator_summary
from backend.forex.data_fetcher import fetch_forex_candles

logger = logging.getLogger(__name__)

def get_current_session() -> str:
    now_est = datetime.now(pytz.timezone("America/New_York"))
    h = now_est.hour
    if 17 <= h or h < 3:
        return "ASIAN"
    elif 3 <= h < 8:
        return "LONDON"
    elif 8 <= h < 12:
        return "LONDON_NY_OVERLAP"
    else:
        return "NY_AFTERNOON"

def analyze_forex_pair(pair: str, timeframe: str = "15m") -> dict:
    """
    Session-aware Forex analyzer using SMC and Mean Reversion.
    """
    try:
        df = fetch_forex_candles(pair, timeframe, limit=300)
        
        if df.empty or len(df) < 200:
            return {"signal": "HOLD", "reason": "Not enough data"}
            
        df = add_all_indicators(df)
        summary = extract_indicator_summary(df)
        
        price = summary["price"]
        ema9 = summary["ema_9"]
        ema21 = summary["ema_21"]
        ema50 = summary["ema_50"]
        ema200 = summary["ema_200"]
        rsi = summary["rsi"]
        atr = summary["atr"]
        bb_upper = summary["bb_upper"]
        bb_lower = summary["bb_lower"]
        fvgs = summary.get("fvgs", [])
        
        session = get_current_session()
        signal = "HOLD"
        reasons = [f"Session: {session}"]
        
        macro_bull = price > ema200 if ema200 else False
        macro_bear = price < ema200 if ema200 else False
        bullish_momentum = ema9 > ema21 and ema21 > ema50
        bearish_momentum = ema9 < ema21 and ema21 < ema50
        
        if session == "ASIAN":
            # Mean Reversion Strategy
            if price <= bb_lower and rsi < 35:
                signal = "BUY"
                reasons.append(f"Mean Reversion: Price pierced lower BB at {bb_lower:.4f}. RSI oversold ({rsi:.1f}).")
            elif price >= bb_upper and rsi > 65:
                signal = "SELL"
                reasons.append(f"Mean Reversion: Price pierced upper BB at {bb_upper:.4f}. RSI overbought ({rsi:.1f}).")
                
            # Tighter stops for mean reversion (1x ATR for SL, 1.5x for TP)
            sl_distance = atr * 1.0
            tp_distance = atr * 1.5
            
        else:
            # Momentum / Breakout Strategy for London/NY
            # Smart Money Concept (SMC) Requirement: We need a recent FVG in our direction.
            has_bullish_fvg = any(fvg["type"] == "BULLISH_FVG" for fvg in fvgs[-3:]) # Recent 3 FVGs
            has_bearish_fvg = any(fvg["type"] == "BEARISH_FVG" for fvg in fvgs[-3:])
            
            if macro_bull and bullish_momentum and has_bullish_fvg and rsi < 70:
                signal = "BUY"
                reasons.append("SMC Momentum: Bullish trend + Recent Bullish FVG confirmed.")
            elif macro_bear and bearish_momentum and has_bearish_fvg and rsi > 30:
                signal = "SELL"
                reasons.append("SMC Momentum: Bearish trend + Recent Bearish FVG confirmed.")
                
            # Wider trend-following stops (1.5x SL, 3x TP)
            sl_distance = atr * 1.5
            tp_distance = atr * 3.0
            
        sl = round(price - sl_distance if signal == "BUY" else price + sl_distance, 5)
        tp = round(price + tp_distance if signal == "BUY" else price - tp_distance, 5)
        
        # ML Engine Probability Gate
        ml_prob = 0.5
        if signal != "HOLD":
            from backend.forex.ml_engine import predict_forex_probability
            ml_prob = predict_forex_probability(summary)
            
            # If ML predicts low chance of success, veto the trade
            if (signal == "BUY" and ml_prob < 0.45) or (signal == "SELL" and ml_prob > 0.55):
                reasons.append(f"ML Veto: Low confidence ({ml_prob*100:.1f}%).")
                signal = "HOLD"
            else:
                reasons.append(f"ML Approval: Edge Confirmed ({ml_prob*100:.1f}%).")
        
        return {
            "pair": pair,
            "timeframe": timeframe,
            "session": session,
            "signal": signal,
            "price": price,
            "sl": sl,
            "tp": tp,
            "atr": atr,
            "ml_probability": ml_prob,
            "reasons": reasons,
            "indicators": summary
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze {pair}: {e}")
        return {"signal": "ERROR", "reason": str(e)}

if __name__ == "__main__":
    res = analyze_forex_pair("EURUSD")
    import json
    # Just print the high level fields to avoid console flood
    print(json.dumps({k:v for k,v in res.items() if k != 'indicators'}, indent=2))
