import json
import logging
import sqlite3

import requests.exceptions
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Main imports

from backend.btc.indicators import add_all_indicators
from backend.btc.rl_agent import get_rl_agent
from backend.engine.multi_asset_fetcher import fetch_asset_candles
from backend.forex.analyzer import analyze_forex_pair
from backend.forex.auto_executor import get_forex_status
from backend.forex.data_fetcher import get_forex_ticker
from backend.forex.paper_trader import get_balance as get_forex_balance
from backend.forex.paper_trader import \
    get_open_positions as get_forex_positions
from backend.forex.paper_trader import get_trade_history as get_forex_history

router = APIRouter()

@router.get("/api/forex/trade/status")
def api_forex_status():
    return JSONResponse({
        "status": get_forex_status(),
        "balance": get_forex_balance(),
        "positions": get_forex_positions(),
        "history": get_forex_history()
    })

@router.get("/api/forex/analysis/{pair}")
def api_forex_analysis(pair: str):
    ticker = get_forex_ticker(pair)
    analysis = analyze_forex_pair(pair)
    return JSONResponse({
        "pair": pair,
        "ticker": ticker,
        "analysis": analysis
    })

@router.get("/api/market-regime")
def api_market_regime():


    try:
        df_15m = fetch_asset_candles('BTC', '15m', limit=100)
        if df_15m is not None and not df_15m.empty:
            df_ind = add_all_indicators(df_15m)
            latest = df_ind.iloc[-1]
            
            c = float(latest.get('close', 0))
            atr = float(latest.get('atr', 0))
            atr_pct = float(latest.get('atr_percentile', 50.0))
            rsi = float(latest.get('rsi', 50.0))
            bb_u = float(latest.get('bb_upper', c * 1.01))
            bb_l = float(latest.get('bb_lower', c * 0.99))
            bb_w = ((bb_u - bb_l) / c * 100.0) if c > 0 else 0
            bb_spread = abs(bb_u - bb_l)
            vol_surge = bool(latest.get('vol_surge', False))
            
            if atr_pct < 20 or bb_w < 0.20:
                regime = 'CHOP / DEADZONE'
                best_style = 'CHOP'
                reason = 'Volatility is extremely low. Bollinger Bands are tightly constricted, making this a pure mean-reversion environment.'
            elif rsi > 65 or rsi < 35:
                regime = 'MEAN REVERSION'
                best_style = 'AMBUSH'
                reason = 'RSI is showing exhaustion. The market is overextended and ripe for fading fake-outs.'
            elif vol_surge or atr_pct > 70:
                regime = 'HIGH VOLATILITY TREND'
                best_style = 'MOMENTUM_SURFER'
                reason = 'Volume is surging and volatility is high. The market is trending aggressively.'
            else:
                regime = 'STANDARD / NEUTRAL'
                best_style = 'SNIPER'
                reason = 'The market is floating in a completely neutral, average-volatility regime. Wait for high-conviction candlestick patterns at the interval close.'

            # Descriptive commentary for each indicator
            if 45 <= rsi <= 55:
                rsi_note = f"{rsi:.1f} (Dead neutral, no exhaustion)"
            elif rsi > 70:
                rsi_note = f"{rsi:.1f} (Severely overbought exhaustion wick territory)"
            elif rsi > 60:
                rsi_note = f"{rsi:.1f} (Moderately bullish bias, monitoring for reversal)"
            elif rsi < 30:
                rsi_note = f"{rsi:.1f} (Severely oversold exhaustion wick territory)"
            elif rsi < 40:
                rsi_note = f"{rsi:.1f} (Moderately bearish bias, monitoring for reversal)"
            else:
                rsi_note = f"{rsi:.1f} (Normal baseline range, no exhaustion)"

            if bb_w < 0.25:
                bb_note = f"{bb_w:.2f}% (Extreme contraction, ultra-tight squeeze)"
            elif bb_w < 0.70:
                bb_note = f"{bb_w:.2f}% (Average contraction, not overly tight, not expanding)"
            else:
                bb_note = f"{bb_w:.2f}% (Expanding volatility band, momentum forming)"

            vol_note = "True (Surge detected above 2.0x volume threshold)" if vol_surge else "False (Normal baseline volume)"
            atr_note = f"~${atr:.0f} ({atr_pct:.0f}th percentile)"

            # Style breakdown rationale matching quantitative regime criteria
            if vol_surge or atr_pct > 70:
                why_momentum = "Volume is surging and volatility is high. The market is trending aggressively, making this an ideal setup to surf momentum candles."
            else:
                why_momentum = "There is no volume surge and volatility is only average. Surfing momentum right now will likely result in getting chopped up by random 1-minute noise."

            if bb_w < 0.25 and atr_pct < 20:
                why_chop = f"Bollinger Bands are ultra-tight ({bb_w:.2f}%) with flat volatility. Ideal for pure mean-reversion trading between bands."
            else:
                why_chop = f"The Bollinger Bands are at {bb_w:.2f}% width, which means there is a roughly ${bb_spread:.0f} spread between the upper and lower bands. That's too wide for pure mean-reversion. Chop works best when the BB width is incredibly tight (< 0.20%) and price is ping-ponging inside a tiny range."

            if rsi > 65 or rsi < 35:
                why_ambush = f"RSI is stretched at {rsi:.1f}. High probability of fading exhaustion wicks as price reverts back towards median."
            else:
                why_ambush = f"RSI is centered at {rsi:.1f}. There are no deeply overbought/oversold exhaustion wicks to fade right now."

            if best_style == 'SNIPER':
                why_sniper = "Because the market is floating in a completely neutral, average-volatility regime, you should use SNIPER. It patiently waits for high-conviction candlestick trigger setups without forcing trades in noise."
            else:
                why_sniper = "Sniper is in standby while specialized regime conditions are actively prioritized."

            executive_summary = "Because the market is floating in a completely neutral, average-volatility regime, you should use SNIPER." if best_style == 'SNIPER' else f"Because {reason.lower()}, you should use {best_style} (or AUTO)."

            rl = get_rl_agent()
            rl_stats = {
                "epsilon": round(getattr(rl, 'epsilon', 0), 3),
                "memory_size": len(getattr(rl, 'memory', [])),
                "mode": "Exploitation (Live)" if getattr(rl, 'epsilon', 1) < 0.1 else "Exploration (Training)"
            }

            return {
                "success": True,
                "price": c,
                "rsi": rsi,
                "rsi_note": rsi_note,
                "bb_width": bb_w,
                "bb_spread": bb_spread,
                "bb_note": bb_note,
                "vol_surge": vol_surge,
                "vol_note": vol_note,
                "atr": atr,
                "atr_percentile": atr_pct,
                "atr_note": atr_note,
                "regime": regime,
                "best_style": best_style,
                "reason": reason,
                "executive_summary": executive_summary,
                "rl_stats": rl_stats,
                "explanations": {
                    "why_momentum": why_momentum,
                    "why_chop": why_chop,
                    "why_ambush": why_ambush,
                    "why_sniper": why_sniper
                }
            }
        return {"success": False, "error": "No candle data"}
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        return {"success": False, "error": str(e)}
