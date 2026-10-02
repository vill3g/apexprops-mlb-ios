from backend.btc.data_fetcher import get_candle_countdown
from enum import Enum

from fastapi import (APIRouter, BackgroundTasks, Depends, HTTPException, Query,
                     Request)


class DirectionEnum(str, Enum):
    ABOVE = "ABOVE"
    BELOW = "BELOW"
    BUY = "BUY"
    SELL = "SELL"
    AI_START = "AI_START"
    YES = "YES"
    NO = "NO"
    AI_FORCE = "AI_FORCE"
    ai_force = "ai_force"

import json
import logging
import os
import sqlite3
import time
from typing import Optional

import requests.exceptions
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

import traceback
_fx_cache = {}
import threading
_fx_cache_lock = threading.Lock()
def _cached_analyze_forex_pair(asset, tf):
    key = (asset, tf)
    now = time.time()
    with _fx_cache_lock:
        if key not in _fx_cache or now - _fx_cache[key][0] > 10:
            _fx_cache[key] = (now, analyze_forex_pair(asset, tf))
        return _fx_cache[key][1]

import pandas as pd

import backend.forex.auto_executor as _forex_exec  # read _is_running live, not a stale copy
# Main imports
from backend.auth.dependencies import (STATIC_DIR, _get_guest_id, caller_has_owner_access, require_auth,
                                       require_bot_control, require_owner)
from backend.btc.analysis_cache import (get_cached_btc_analysis,
                                        sanitize_btc_json)
from backend.btc.auto_executor import invalidate_saas_users_cache
from backend.btc.data_fetcher import (format_volume_series,
                                      
                                      get_live_15m_target_data)
from backend.btc.indicators import add_all_indicators
from backend.btc.kalshi_client import get_kalshi_15m_market, get_recent_trades
from backend.btc.kalshi_trader import kalshi_trader as _kt
from backend.btc.paper_balance import load_balance, reset_balance
from backend.btc.pattern_detector import detect_candlestick_patterns
from backend.core.registry import get_auto_executor
from backend.database.models import (enrich_trade_metadata, get_user_by_id,
                                     reset_user_paper_balance_and_pnl,
                                     update_user_ai_enabled,
                                     update_user_config)
from backend.engine.multi_asset_fetcher import get_asset_ticker
from backend.forex.analyzer import analyze_forex_pair
from backend.forex.auto_executor import (ACTIVE_PAIRS, start_forex_executor, stop_forex_executor)
from backend.forex.data_fetcher import fetch_forex_candles, get_forex_ticker
from backend.forex.paper_trader import (calculate_pip_value, close_position, get_balance, get_open_positions, get_trade_history, open_position)
from backend.core.registry import SUPPORTED_ASSETS
from backend.engine.multi_asset_fetcher import fetch_asset_candles



def _validate_asset(request: Request):
    """Reject unknown /{asset} path values with 404 instead of a 500."""
    asset = str(request.path_params.get("asset", "") or "").upper().strip()
    if asset and asset not in SUPPORTED_ASSETS and asset not in ACTIVE_PAIRS:
        raise HTTPException(status_code=404, detail=f"Unknown asset '{asset}'")

router = APIRouter(dependencies=[Depends(_validate_asset)])

# Standalone root route (no asset param, so must be declared outside the dependency router)
_engine_root_router = APIRouter()

@_engine_root_router.get("/api/engine/")
def engine_root():
    """Health and capabilities endpoint for the trading engine."""
    return {"status": "ok", "assets": list(SUPPORTED_ASSETS)}


@router.get("/api/engine/{asset}/analyze")

def api_btc_analyze(asset: str, timeframe: str = "15m"):
    """Returns comprehensive directional analysis, score, and trade setup for selected timeframe."""

    if asset in ACTIVE_PAIRS:

        analysis = _cached_analyze_forex_pair(asset, timeframe)
        # Adapt keys to match UI expectations
        price = analysis.get("price", 1.0)
        signal = analysis.get("signal", "HOLD")
        tp = analysis.get("tp") or price
        sl = analysis.get("sl") or price
        dir_ui = "ABOVE" if signal == "BUY" else ("BELOW" if signal == "SELL" else "HOLD")
        bias = "UP" if signal == "BUY" else ("DOWN" if signal == "SELL" else "NEUTRAL")
        prob_pct = int(analysis.get("ml_probability", 0.5) * 100)

        forex_dict = {
            "price": price,
            "direction": dir_ui,
            "primary_bias": bias,
            "predicted_probability": analysis.get("ml_probability", 0.5),
            "confidence_percent": prob_pct,
            "confluence_score": 75 if signal in ["BUY", "SELL"] else 50,
            "conviction_grade": "A" if signal in ["BUY", "SELL"] else "NEUTRAL",
            "catalysts": analysis.get("reasons", []),
            "reasons_bullish": analysis.get("reasons", []) if signal == "BUY" else [],
            "reasons_bearish": analysis.get("reasons", []) if signal == "SELL" else [],
            "trade_setup": {
                "entry_price": price,
                "entry_zone": price,
                "stop_loss": sl,
                "take_profit_1": tp
            },
            "ticker": {"price": price},
            "indicators": analysis.get("indicators", {}),
            "market_structure": {},
            "target_benchmark": {
                "current_price": price,
                "target_price": tp,
                "distance_pct": round(((price - tp) / tp) * 100, 4) if tp else 0.0,
                "time_remaining_str": "FOREX",
                "next_contract_forecast": {
                    "direction": dir_ui,
                    "recommendation": f"Session: {analysis.get('session', 'N/A')} ({signal})",
                    "probability_percent": prob_pct,
                    "conviction_badge": "ML GATE",
                    "conviction_grade": "A",
                    "primary_edge": f"SMC / {analysis.get('session', 'N/A')}",
                    "target_settlement_zone": f"SL: {sl:.5f} | TP: {tp:.5f}",
                    "catalysts": analysis.get("reasons", [])
                }
            }
        }
        return JSONResponse(sanitize_btc_json(forex_dict))

    try:
        _, analysis = get_cached_btc_analysis(asset=asset, timeframe=timeframe)
        return JSONResponse(sanitize_btc_json(analysis))
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        static_backup = os.path.join(STATIC_DIR, "data", "btc_analysis.json")
        if os.path.exists(static_backup):
            try:
                with open(static_backup, "r", encoding="utf-8") as f:
                    return JSONResponse(json.load(f))
            except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
                logger.warning(f"Failed to load static backup: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/api/engine/{asset}/prediction/accuracy/reset", dependencies=[Depends(require_auth), Depends(require_owner)])
def api_btc_prediction_accuracy_reset(asset: str):
    """Reset prediction accuracy tracker by marking past trades ineligible."""
    try:
        get_auto_executor(asset).reset_prediction_accuracy()
        return JSONResponse({"status": "ok"})
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        logger.error(f"[API] Error resetting prediction accuracy: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@router.get("/api/engine/{asset}/prediction/accuracy")
def api_btc_prediction_accuracy(asset: str):
    """Return accuracy based only on settled automated Kalshi predictions."""
    try:

        trades = get_auto_executor(asset).get_trades_history()
        get_auto_executor(asset).check_settlements(trades)
        accuracy = get_auto_executor(asset).get_prediction_accuracy(trades)
        latest = accuracy.get("recent_outcomes", [])[-1] if accuracy.get("recent_outcomes") else None
        return JSONResponse({
            "accuracy": accuracy,
            "forecast": {
                "direction": latest.get("predicted"),
                "generated_at": latest.get("time"),
                "conviction_grade": latest.get("conviction_grade"),
                "confidence": latest.get("confidence"),
            } if latest else None,
            "trade": latest,
            "correct": bool(latest.get("correct")) if latest else False,
        })
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        logger.error(f"[API] Error in prediction accuracy endpoint: {e}")
        return JSONResponse({
            "accuracy": {"total_evaluated": 0, "correct_picks": 0, "ratio_text": "0 of 0 Correct", "recent_outcomes": []},
            "forecast": None,
            "trade": None,
            "correct": False,
            "error": str(e)
        }, status_code=500)

@router.get("/api/engine/{asset}/live")
def api_btc_live(asset: str):
    """
    Ultra-low latency endpoint returning live price, 15m target benchmark,
    spread delta, 5-target trend box, and candle countdown for 1s polling.
    Autonomous rollover execution is handled in a dedicated background worker.
    """
    try:

        if asset.upper() in ACTIVE_PAIRS:



            
            ticker = get_forex_ticker(asset.upper())
            curr_price = float(ticker.get("price", 1.0))
            analysis = _cached_analyze_forex_pair(asset.upper(), "15m")
            tp = float(analysis.get("tp") or curr_price)
            delta = round(curr_price - tp, 5)
            delta_pct = round((delta / tp) * 100, 4) if tp else 0.0
            cd = get_candle_countdown("15m")
            
            data = {
                "price": curr_price,
                "target_price": tp,
                "target_source": f"Forex {analysis.get('session', 'NY')}",
                "delta": delta,
                "delta_pct": delta_pct,
                "status": "ABOVE" if delta >= 0 else "BELOW",
                "seconds_left": cd["seconds_left"],
                "formatted_countdown": cd["formatted"],
                "last_5_targets": [tp],
                "streak_summary": f"Forex AI {analysis.get('signal', 'HOLD')}",
                "volume_24h": float(ticker.get("volume_24h", 0)),
                "kalshi": {
                    "is_synthetic": False,
                    "source": "Forex Spot Engine",
                    "yes_prob": int(analysis.get("ml_probability", 0.5) * 100),
                    "no_prob": 100 - int(analysis.get("ml_probability", 0.5) * 100),
                    "volume_24h": 0
                }
            }
            return JSONResponse(sanitize_btc_json(data))

        data = get_live_15m_target_data(asset.upper())
        return JSONResponse(sanitize_btc_json(data))
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        return JSONResponse({
            "price": 0.0,
            "target_price": 0.0,
            "target_source": "--",
            "delta": 0.0,
            "delta_pct": 0.0,
            "status": "NEUTRAL",
            "seconds_left": 0,
            "formatted_countdown": "--:--",
            "last_5_targets": [],
            "streak_summary": "--",
            "error": str(e)
        }, status_code=500)

@router.get("/api/engine/{asset}/ticker")
def api_btc_ticker(asset: str):
    """Returns live 24h ticker info."""
    try:

        if asset.upper() in ACTIVE_PAIRS:

            return JSONResponse(sanitize_btc_json(get_forex_ticker(asset.upper())))
        ticker = get_asset_ticker(asset.upper())
        return JSONResponse(sanitize_btc_json(ticker))
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        static_backup = os.path.join(STATIC_DIR, "data", "btc_ticker.json")
        if os.path.exists(static_backup):
            try:
                with open(static_backup, "r", encoding="utf-8") as f:
                    return JSONResponse(json.load(f))
            except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
                logger.warning(f"Failed to load static backup: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/api/engine/{asset}/countdown")
def api_btc_countdown(asset: str, timeframe: str = "15m"):
    """Returns countdown to current candle close for selected timeframe."""
    try:
        return JSONResponse(sanitize_btc_json(get_candle_countdown(timeframe=timeframe)))
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        logger.error(f"Error in countdown: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/api/engine/{asset}/kalshi")
def api_btc_kalshi(asset: str):
    """Returns active Kalshi 15M target strike and market odds."""
    try:

        if asset.upper() in ACTIVE_PAIRS:


            ticker = get_forex_ticker(asset.upper())
            p = float(ticker.get("price", 1.0))
            analysis = _cached_analyze_forex_pair(asset.upper(), "15m")
            tp = float(analysis.get("tp") or p)
            sl = float(analysis.get("sl") or p)
            ml_p = float(analysis.get("ml_probability", 0.5))
            buy_prob = int(round(ml_p * 100))
            sell_prob = 100 - buy_prob
            pair_fmt = f"{asset.upper()[:3]}/{asset.upper()[3:]}"
            return JSONResponse({
                "status": "active",
                "ticker": f"{pair_fmt} · SPOT FX",
                "target_price": tp,
                "entry_price": p,
                "sl_price": sl,
                "tp_price": tp,
                "yes_prob": buy_prob,
                "no_prob": sell_prob,
                "is_synthetic": False,
                "source": "Forex Spot Engine"
            })

        data = get_kalshi_15m_market(series_ticker=f"KX{asset.upper()}15M")
        if not data:
            return JSONResponse({"status": "unavailable", "target_price": None, "is_synthetic": True})
        data = dict(data)
        data["is_synthetic"] = (data.get("status") == "synthetic") or (data.get("source") == "Kalshi Synthetic")
        try:
            _, analysis = get_cached_btc_analysis(asset=asset, timeframe="15m")
            tb = analysis.get("target_benchmark", {}).get("next_contract_forecast", {})
            pred_prob = tb.get("probability_percent")
            if pred_prob is not None:
                try:
                    pred_prob = float(pred_prob) / 100.0
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing probability: {e}")
                    pred_prob = None
            cats = tb.get("catalysts") or []
            summary_str = ""
            if cats:
                summary_str = " | ".join(str(c) for c in cats[:2])
            elif tb.get("primary_edge"):
                summary_str = str(tb.get("primary_edge"))
            elif tb.get("recommendation"):
                summary_str = str(tb.get("recommendation"))

            bias_val = tb.get("direction") or analysis.get("primary_bias") or analysis.get("direction") or "NEUTRAL"
            conf_val = int(tb.get("probability_percent") or analysis.get("confidence_percent") or 50)
            grade_val = tb.get("conviction_grade") or analysis.get("conviction_grade") or "PASS"

            data["ml_reasoning"] = {
                "primary_bias": str(bias_val),
                "confidence_percent": conf_val,
                "predicted_probability": pred_prob,
                "summary": summary_str,
                "conviction_grade": str(grade_val)
            }
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as _ml_err:
            logger.debug(f"[Ticker] ml_reasoning enrichment skipped: {_ml_err}")
        return JSONResponse(data)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        return JSONResponse({"error": str(e), "target_price": None, "is_synthetic": True}, status_code=500)

_chart_cache = {}
_chart_cache_lock = threading.Lock()
_CHART_TTL_SEC = 2.0
_CHART_TIMEFRAMES = {"1m", "5m", "15m", "1h", "1d"}


@router.get("/api/engine/{asset}/chart")
def api_chart_candles(asset: str, timeframe: str = "1m", limit: int = 300):
    """Plain OHLCV candles + volume for the users' Lightweight Charts price chart.
    Cached for 2 s so many open dashboards cost one exchange call."""

    tf = str(timeframe).lower()
    if tf not in _CHART_TIMEFRAMES:
        raise HTTPException(status_code=400, detail="timeframe must be 1m, 5m, 15m or 1h")
    limit = max(2, min(int(limit), 500))
    key = (asset.upper(), tf, 500 if limit > 10 else 10)
    with _chart_cache_lock:
        hit = _chart_cache.get(key)
    now = time.time()
    if not hit or now - hit[0] > _CHART_TTL_SEC:
        try:
            df = fetch_asset_candles(asset.upper(), tf, limit=key[2])
        except Exception as e:
            logger.warning(f"[Chart] candle fetch failed for {asset} {tf}: {e}")
            df = None
        if df is None or getattr(df, "empty", True):
            if hit:
                hit = (hit[0], hit[1])      # serve the last good data
            else:
                return JSONResponse({"candles": [], "volume": []}, status_code=200)
        else:
            df = df.tail(key[2])
            seen_ts = set()
            clean_candles = []
            import math
            for r in df.itertuples():
                try:
                    t = int(r.time)
                    if t in seen_ts or t <= 0:
                        continue
                    seen_ts.add(t)
                    o = float(r.open)
                    h = float(r.high)
                    l = float(r.low)
                    c = float(r.close)
                    if not (math.isfinite(o) and math.isfinite(h) and math.isfinite(l) and math.isfinite(c)):
                        continue
                    if o <= 0 or c <= 0:
                        continue
                    max_p = max(o, c, h, l)
                    min_p = min(o, c, h, l)
                    clean_candles.append({
                        "time": t,
                        "open": o,
                        "high": max_p,
                        "low": max(0.0001, min_p),
                        "close": c
                    })
                except Exception:
                    continue
            clean_candles.sort(key=lambda x: x["time"])
            hit = (now, {"candles": clean_candles, "volume": format_volume_series(df)})
            with _chart_cache_lock:
                _chart_cache[key] = hit
    data = hit[1]
    return JSONResponse({"candles": data["candles"][-limit:], "volume": data["volume"][-limit:]})


@router.get("/api/engine/{asset}/kalshi/trades")
def api_kalshi_live_trades(asset: str, since: float = 0.0):
    """Live public trades on the current 15-minute market (for the floating trade
    bubbles on the chart). `since` = unix time of the newest trade already shown."""
    market = get_kalshi_15m_market(series_ticker=f"KX{asset.upper()}15M")
    ticker = (market or {}).get("ticker", "")
    if not market or market.get("status") == "synthetic" or "SYNTH" in str(ticker).upper():
        return JSONResponse({"ticker": ticker, "trades": []})
    trades = [t for t in get_recent_trades(ticker) if t["ts"] > float(since or 0)]
    return JSONResponse({"ticker": ticker, "trades": trades[:30]})


@router.get("/api/engine/{asset}/kalshi/orderbook")
@router.get("/api/engine/{asset}/kalshi/pricebook")
def api_btc_kalshi_orderbook(asset: str):
    """Returns top-of-book market depth, spread, bid/ask sizes and order imbalance."""
    try:

        data = get_kalshi_15m_market(series_ticker=f"KX{asset.upper()}15M")
        if not data:
            return JSONResponse({"status": "unavailable", "bids": [], "asks": [], "is_synthetic": True})
        
        is_synthetic = (data.get("status") == "synthetic") or (data.get("source") == "Kalshi Synthetic")
        yes_bid = data.get("yes_bid", 0.0)
        yes_ask = data.get("yes_ask", 0.0)
        no_bid = data.get("no_bid", 0.0)
        no_ask = data.get("no_ask", 0.0)
        spread = data.get("spread", 0.04)
        yes_bid_size = data.get("yes_bid_size", 0)
        yes_ask_size = data.get("yes_ask_size", 0)
        imbalance = data.get("orderbook_imbalance", 0.0)
        bias = data.get("market_bias", "NEUTRAL")

        return JSONResponse({
            "ticker": data.get("ticker", ""),
            "target_price": data.get("target_price", 0.0),
            "yes_prob": data.get("yes_prob", 50.0),
            "no_prob": data.get("no_prob", 50.0),
            "is_synthetic": is_synthetic,
            "top_of_book": {
                "yes_bid": yes_bid,
                "yes_ask": yes_ask,
                "no_bid": no_bid,
                "no_ask": no_ask,
                "yes_bid_size": yes_bid_size,
                "yes_ask_size": yes_ask_size,
                "spread": spread,
                "spread_cents": round(spread * 100, 1),
                "orderbook_imbalance_percent": imbalance,
                "market_bias": bias,
                "is_synthetic": is_synthetic
            },
            "bids": [{"side": "YES", "price": yes_bid, "size": yes_bid_size}, {"side": "NO", "price": no_bid, "size": 0}],
            "asks": [{"side": "YES", "price": yes_ask, "size": yes_ask_size}, {"side": "NO", "price": no_ask, "size": 0}],
            "timestamp": int(time.time())
        })
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        return JSONResponse({"error": str(e), "is_synthetic": True}, status_code=500)

@router.get("/api/engine/{asset}/trade/status", dependencies=[Depends(require_auth)])
def api_btc_trade_status(asset: str, request: Request):
    """Returns full status of the automated trading engine."""
    try:

        if asset.upper() in ACTIVE_PAIRS:



            
            balance = get_balance()
            open_pos = get_open_positions()
            history = get_trade_history()
            
            ticker = get_forex_ticker(asset.upper())
            curr_price = float(ticker.get("price", 1.0))
            pip_decimal = 0.01 if "JPY" in asset.upper() else 0.0001
            
            open_pnl = 0.0
            annotated_open = []
            for p in open_pos:
                pos = dict(p)
                entry = float(pos.get("entry_price", curr_price))
                size = int(pos.get("size", 10000))
                pips = ((curr_price - entry) if pos.get("side") == "BUY" else (entry - curr_price)) / pip_decimal
                pip_val = calculate_pip_value(pos.get("pair", asset.upper()), size, curr_price)
                live_pnl = round(pips * (pip_val / pip_decimal) * pip_decimal, 2)
                pos["live_pnl"] = live_pnl
                pos["pips"] = round(pips, 1)
                pos["current_price"] = curr_price
                pos["mode"] = "PAPER"
                open_pnl += live_pnl
                annotated_open.append(pos)
                
            wins = sum(1 for t in history if float(t.get("realized_pnl", 0)) > 0)
            losses = sum(1 for t in history if float(t.get("realized_pnl", 0)) < 0)
            total_closed = len(history)
            win_rate = round((wins / total_closed) * 100, 1) if total_closed > 0 else 0.0
            total_pnl = round(sum(float(t.get("realized_pnl", 0)) for t in history), 2)
            
            formatted_trades = []
            for t in annotated_open:
                formatted_trades.append({
                    "id": t.get("id"),
                    "mode": "PAPER",
                    "ticker": f"{t.get('pair')} SPOT",
                    "recommendation": f"{t.get('side')} {(t.get('size', 10000)/100000):.2f} Lots",
                    "side": t.get("side"),
                    "status": "OPEN",
                    "result": "OPEN",
                    "entry_price": t.get("entry_price"),
                    "count": f"{(t.get('size', 10000)/100000):.2f} Lots",
                    "lots": round(t.get('size', 10000)/100000, 2),
                    "pnl": t.get("live_pnl", 0.0),
                    "live_pnl": t.get("live_pnl", 0.0),
                    "pips": t.get("pips", 0.0),
                    "created_at": t.get("opened_at", "")
                })
            for t in history[:10]:
                is_win = float(t.get("realized_pnl", 0)) > 0
                formatted_trades.append({
                    "id": t.get("id"),
                    "mode": "PAPER",
                    "ticker": f"{t.get('pair')} SPOT",
                    "recommendation": f"{t.get('side')} {(t.get('size', 10000)/100000):.2f} Lots",
                    "side": t.get("side"),
                    "status": "CLOSED",
                    "result": "WIN" if is_win else "LOSS",
                    "entry_price": t.get("entry_price"),
                    "count": f"{(t.get('size', 10000)/100000):.2f} Lots",
                    "lots": round(t.get('size', 10000)/100000, 2),
                    "pnl": t.get("realized_pnl", 0.0),
                    "live_pnl": t.get("realized_pnl", 0.0),
                    "created_at": t.get("closed_at", "")
                })

            pair_fmt = f"{asset.upper()[:3]}/{asset.upper()[3:]}"
            return JSONResponse({
                "enabled": _forex_exec._is_running,
                "mode": "PAPER",
                "asset": asset.upper(),
                "balance_dollars": balance,
                "balance": balance,
                "equity": round(balance + open_pnl, 2),
                "open_pnl_dollars": round(open_pnl, 2),
                "total_pnl_dollars": total_pnl,
                "win_rate_pct": win_rate,
                "wins": wins,
                "losses": losses,
                "trades_count": total_closed,
                "open_trades": annotated_open,
                "recent_trades": formatted_trades,
                "active_market": {
                    "ticker": f"{pair_fmt} · SPOT FX",
                    "yes_bid": 1.0,
                    "no_bid": 1.0
                },
                "market_type": "SPOT"
            })

        is_owner = getattr(request.state, "is_owner", False) or caller_has_owner_access(request)
        guest_id = None if is_owner else _get_guest_id(request)
        status = get_auto_executor(asset, guest_id=guest_id).get_status()
        if guest_id:
            status["is_guest"] = True
            status["mode"] = "PAPER"
        else:
            user_id = getattr(request.state, "user_id", None)
            if user_id:
                from backend.database.models import get_user_by_id
                u = get_user_by_id(user_id)
                if u:
                    u_mode = str(u.get("trading_mode", "")).upper()
                    if u_mode in ["PAPER", "LIVE"]:
                        status["mode"] = u_mode
        return JSONResponse(sanitize_btc_json(status))
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        return JSONResponse({"error": str(e), "enabled": False, "mode": "PAPER"}, status_code=500)

@router.post("/api/engine/{asset}/trade/toggle", dependencies=[Depends(require_auth)])
def api_btc_trade_toggle(asset: str, enabled: bool = Query(...), request: Request = None):
    """Toggle auto-trading execution ON or OFF."""
    try:

        if asset.upper() in ACTIVE_PAIRS:

            if enabled:
                start_forex_executor()
            else:
                stop_forex_executor()
            return JSONResponse({"status": "ok", "enabled": enabled})

        is_owner = getattr(request.state, "is_owner", False) or (request and caller_has_owner_access(request))
        guest_id = None if is_owner else (_get_guest_id(request) if request else None)
        user_id = getattr(request.state, "user_id", None) if request else None
        
        target_id = guest_id if guest_id else None
        res = get_auto_executor(asset, guest_id=target_id).set_enabled(enabled)
        
        if user_id:
            update_user_ai_enabled(user_id, enabled)
            
        return JSONResponse(res)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        return JSONResponse({"success": False, "error": f"Toggle error: {str(e)}"}, status_code=500)

@router.post("/api/engine/{asset}/trade/mode", dependencies=[Depends(require_auth), Depends(require_bot_control)])
def api_btc_trade_mode(asset: str, mode: str = Query(...), request: Request = None):
    """Switch trading mode between PAPER (simulation) and LIVE (real money)."""
    is_owner = getattr(request.state, "is_owner", False) or (request and caller_has_owner_access(request))
    guest_id = None if is_owner else (_get_guest_id(request) if request else None)
    user_id = getattr(request.state, "user_id", None) if request else None

    if guest_id:
        if str(mode).upper() == "LIVE":
            raise HTTPException(status_code=403, detail="Guest users cannot switch to LIVE trading mode.")
        res = get_auto_executor(asset, guest_id=guest_id).set_mode("PAPER")
        return JSONResponse(res)

    mode_clean = str(mode).upper().strip()
    if mode_clean not in ["PAPER", "LIVE"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Choose PAPER or LIVE.")

    if mode_clean == "LIVE":
        has_keys = _kt.is_authenticated()
        if not has_keys and user_id:
            from backend.database.models import get_user_by_id
            u = get_user_by_id(user_id)
            if u and u.get("kalshi_key_id") and u.get("kalshi_priv_key_encrypted"):
                has_keys = True
        if not has_keys:
            raise HTTPException(
                status_code=403,
                detail="Kalshi API credentials must be configured before switching to LIVE trading."
            )

    res = get_auto_executor(asset).set_mode(mode_clean)
    if user_id:
        from backend.database.models import update_user_trading_mode
        update_user_trading_mode(user_id, mode_clean)
        invalidate_saas_users_cache(user_id)
    return JSONResponse(res)

@router.post("/api/engine/{asset}/trade/prediction_mode", dependencies=[Depends(require_auth), Depends(require_bot_control)])
def api_btc_trade_prediction_mode(asset: str, enabled: bool = Query(...), request: Request = None):
    """Toggle prediction mode ON or OFF."""
    is_owner = getattr(request.state, "is_owner", False) or (request and caller_has_owner_access(request))
    guest_id = None if is_owner else (_get_guest_id(request) if request else None)

    get_auto_executor(asset, guest_id=guest_id).prediction_mode = enabled
    get_auto_executor(asset, guest_id=guest_id)._save_config()
    return JSONResponse({"status": "ok", "prediction_mode": enabled})

@router.post("/api/engine/{asset}/trade/threshold", dependencies=[Depends(require_auth), Depends(require_bot_control)])
def api_btc_trade_threshold(asset: str, threshold: str = Query(...), request: Request = None):
    """Set minimum conviction threshold (e.g. 'A+' or 'A')."""
    is_owner = getattr(request.state, "is_owner", False) or (request and caller_has_owner_access(request))
    guest_id = None if is_owner else (_get_guest_id(request) if request else None)

    res = get_auto_executor(asset, guest_id=guest_id).set_conviction_threshold(threshold)
    return JSONResponse(res)

@router.post("/api/engine/{asset}/trade/contracts", dependencies=[Depends(require_auth), Depends(require_bot_control)])
def api_btc_trade_contracts(asset: str, count: int = Query(...), request: Request = None):
    """Set number of contracts per trade."""
    is_owner = getattr(request.state, "is_owner", False) or (request and caller_has_owner_access(request))
    guest_id = None if is_owner else (_get_guest_id(request) if request else None)

    res = get_auto_executor(asset, guest_id=guest_id).set_max_contracts(count)
    return JSONResponse(res)

@router.get("/api/engine/{asset}/trade/config", dependencies=[Depends(require_auth)])
def api_btc_trade_config_get(asset: str, request: Request = None):
    """Retrieve the full current configuration from the server (source of truth)."""
    user_id = getattr(request.state, "user_id", None) if request else None
    is_owner = getattr(request.state, "is_owner", False) or (request and caller_has_owner_access(request))
    guest_id = None if is_owner else (_get_guest_id(request) if request else None)

    ex = get_auto_executor(asset, guest_id=guest_id)

    user_mode = ex.mode
    user_enabled = ex.enabled
    if user_id:
        try:

            u = get_user_by_id(user_id)
            if u:
                user_mode = u.get("trading_mode", ex.mode)
                user_enabled = bool(u.get("ai_enabled", 1))
        except sqlite3.OperationalError as e:
            logger.warning(f"DB Operational Error getting user: {e}")
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
            logger.warning(f"Error getting user: {e}")

    return JSONResponse({
        "mode": "PAPER" if guest_id else user_mode,
        "prediction_mode": ex.prediction_mode,
        "max_daily_risk": ex.max_daily_risk,
        "max_daily_trades": ex.max_daily_trades,
        "min_conviction": ex.min_conviction,
        "max_contracts": ex.max_contracts,
        "enabled": user_enabled,
        "ai_settings": ex.ai_settings,
        "is_guest": bool(guest_id),
    })

@router.post("/api/engine/{asset}/trade/config", dependencies=[Depends(require_auth)])
async def api_btc_trade_config_post(asset: str, request: Request, background_tasks: BackgroundTasks):
    """Save user configuration immediately, supporting SaaS users, guests, and owner."""
    try:
        user_id = getattr(request.state, "user_id", None)
        guest_id = _get_guest_id(request) if request else None
        data = await request.json()
        
        if user_id:


            update_user_config(
                user_id=user_id,
                trade_size_dollars=float(data.get("trade_size_dollars", 5.0)),
                paper_trade_size_dollars=float(data.get("paper_trade_size_dollars", 50.0)),
                stop_loss_pct=float(data.get("stop_loss_pct", 50.0)),
                one_click_trade=bool(data.get("one_click_trade", False)),
                auto_force_trade=bool(data.get("auto_force_trade", False)),
                trading_style=str(data.get("trading_style", "AUTO")),
                signal_source=str(data.get("signal_source", "RL_DQN")),
                take_profit_pct=float(data.get("take_profit_pct", 50.0)),
                take_profit_enabled=bool(data.get("take_profit_enabled", True)),
                notify_trade_results=bool(data.get("notify_trade_results", True)),
                notify_market_trends=bool(data.get("notify_market_trends", True)),
                max_daily_trades=int(data.get("max_daily_trades", 10)),
                max_daily_risk=float(data.get("max_daily_risk", 50.0)),
                trailing_stop_enabled=bool(data.get("trailing_stop_enabled", False)),
                trailing_stop_activation_pct=float(data.get("trailing_stop_activation_pct", 35.0)),
                trailing_stop_distance_pct=float(data.get("trailing_stop_distance_pct", 6.0)),
                second_entry_enabled=bool(data.get("second_entry_enabled", False)),
                second_entry_max_ask=float(data.get("second_entry_max_ask", 0.75)),
                reentry_after_stop_loss=bool(data.get("reentry_after_stop_loss", False)),
                model_choice=str(data.get("model_choice", "RL_DQN")),
                train_window=int(data.get("train_window", 4000)),
                regularization_c=float(data.get("regularization_c", 0.5)),
                class_weight=str(data.get("class_weight", "balanced")),
                xgb_estimators=int(data.get("xgb_estimators", 300)),
                xgb_max_depth=int(data.get("xgb_max_depth", 5)),
                xgb_learning_rate=float(data.get("xgb_learning_rate", 0.1)),
                ignore_pass_technical=bool(data.get("ignore_pass_technical", False)),
                one_shot_ai=bool(data.get("one_shot_ai", False)),
                use_kelly_criterion=bool(data.get("use_kelly_criterion", False))
            )
            invalidate_saas_users_cache(user_id)

            # Sync with in-memory executor and isolated trading_config.json
            ex = get_auto_executor(asset, guest_id=str(user_id))
            if "ai_settings" in data:
                ex.set_ai_settings(data["ai_settings"])
            elif isinstance(data, dict):
                ex.set_ai_settings(data)
            return JSONResponse({"status": "ok", "success": True, "saved": "user_db"})
        
        target_id = guest_id
        ex = get_auto_executor(asset, guest_id=target_id)
        if "ai_settings" in data:
            ex.set_ai_settings(data["ai_settings"])
        else:
            ex.set_ai_settings(data)
        return JSONResponse({"status": "ok", "success": True, "saved": "executor"})
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        logger.error(f"[Config Save Error] {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@router.get("/api/engine/{asset}/trade/ai_settings", dependencies=[Depends(require_auth)])
def api_btc_trade_ai_settings_get(asset: str, request: Request = None):
    """Retrieve the current AI settings from the server (source of truth)."""
    user_id = getattr(request.state, "user_id", None) if request else None
    guest_id = _get_guest_id(request) if request else None
    target_id = str(user_id) if user_id else guest_id

    return JSONResponse(get_auto_executor(asset, guest_id=target_id).ai_settings)

def _retrain_ml_engines(data: dict):
    try:
        from backend.btc.ml_engine import get_ml_engine
        for st in ["SNIPER", "MOMENTUM_SURFER", "AMBUSH", "CHOP"]:
            eng = get_ml_engine(trading_style=st)
            eng.apply_settings(data)
            try:
                from backend.btc.data_fetcher import fetch_15m_candles_history
                hist_df = fetch_15m_candles_history(days=60)
                if hist_df is not None and not hist_df.empty:
                    df_ind = add_all_indicators(hist_df)
                    eng.self_train_on_historical_market(df_ind)
            except Exception as e:
                logger.warning(f"Failed to self-train {st}: {e}")
    except Exception as e:
        logger.warning(f"Failed to apply settings and retrain ML engines: {e}")

@router.post("/api/engine/{asset}/trade/ai_settings", dependencies=[Depends(require_auth)])
async def api_btc_trade_ai_settings(asset: str, request: Request, background_tasks: BackgroundTasks):

    try:
        user_id = getattr(request.state, "user_id", None) if request else None
        guest_id = _get_guest_id(request) if request else None
        target_id = str(user_id) if user_id else guest_id
        data = await request.json()
        get_auto_executor(asset, guest_id=target_id).set_ai_settings(data)
        if not target_id:
            # Only retrain ML engines for owner, not tenants/guests
            background_tasks.add_task(_retrain_ml_engines, data)
        return JSONResponse({"status": "ok", "settings": data})
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        return JSONResponse({"status": "error", "message": str(e)})

@router.post("/api/engine/{asset}/trade/risk_limits", dependencies=[Depends(require_auth), Depends(require_bot_control)])
def api_btc_trade_risk_limits(asset: str, 
    max_daily_risk: Optional[float] = Query(None),
    max_daily_trades: Optional[int] = Query(None),
    request: Request = None
):
    """Set maximum daily risk ($) and maximum daily trades."""
    guest_id = _get_guest_id(request) if request else None

    res = get_auto_executor(asset, guest_id=guest_id).set_risk_limits(max_daily_risk=max_daily_risk, max_daily_trades=max_daily_trades)
    return JSONResponse(res)

@router.post("/api/engine/{asset}/trade/manual", dependencies=[Depends(require_auth), Depends(require_bot_control)])
def api_btc_trade_manual(asset: str, direction: DirectionEnum = Query(...), lots: Optional[float] = Query(None), request: Request = None):
    """1-Click manual execution for Spot BUY/SELL or Binary ABOVE/BELOW."""
    try:

        if asset.upper() in ACTIVE_PAIRS:



            
            side = "BUY" if direction.value in ["BUY", "ABOVE"] else "SELL"
            ticker = get_forex_ticker(asset.upper())
            curr_price = float(ticker.get("price", 1.0))
            analysis = _cached_analyze_forex_pair(asset.upper(), "15m")
            sl = analysis.get("sl")
            tp = analysis.get("tp")
            size_units = int(round(lots * 100_000)) if lots and lots > 0 else 10000
            lots_fmt = size_units / 100_000
            open_position(asset.upper(), side, size_units, curr_price, sl, tp)
            return JSONResponse({
                "success": True,
                "trade": {
                    "recommendation": f"{side} {lots_fmt:.2f} Lots {asset.upper()}",
                    "side": side,
                    "price": curr_price,
                    "sl": sl,
                    "tp": tp,
                    "lots": lots_fmt
                }
            })

        guest_id = _get_guest_id(request) if request else None

        res = get_auto_executor(asset, guest_id=guest_id).execute_manual_trade(direction.value)
        return JSONResponse(sanitize_btc_json(res))
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        return JSONResponse({"success": False, "error": f"Manual trade error: {str(e)}"}, status_code=500)

@router.post("/api/engine/{asset}/trade/reverse", dependencies=[Depends(require_auth), Depends(require_bot_control)])
def api_btc_trade_reverse(asset: str, request: Request = None):
    """1-Click manual reverse of open position."""
    try:

        if asset.upper() in ACTIVE_PAIRS:



            ticker = get_forex_ticker(asset.upper())
            curr_price = float(ticker.get("price", 1.0))
            open_pos = [p for p in get_open_positions() if p["pair"] == asset.upper()]
            if not open_pos:
                return JSONResponse({"success": False, "error": f"No open positions for {asset.upper()} to reverse."})
            last_pos = open_pos[-1]
            old_side = last_pos["side"]
            new_side = "SELL" if old_side == "BUY" else "BUY"
            close_position(last_pos["id"], curr_price, "REVERSE")
            analysis = _cached_analyze_forex_pair(asset.upper(), "15m")
            new_pos = open_position(asset.upper(), new_side, last_pos.get("size", 10000), curr_price, analysis.get("sl"), analysis.get("tp"))
            return JSONResponse({"success": True, "trade": new_pos})

        guest_id = _get_guest_id(request) if request else None

        executor = get_auto_executor(asset, guest_id=guest_id)
        trades = executor.get_trades_history()
        open_trades = [t for t in trades if t.get("status") == "OPEN"]
        if not open_trades:
            return JSONResponse({"success": False, "error": "No open trades to reverse."})
        
        trade = open_trades[-1]
        side = trade.get("side", "").upper()
        opposite_dir = "ABOVE" if side == "NO" else "BELOW"
        
        risk_blocked_reason = executor.check_risk_budget()
        if risk_blocked_reason:
            return JSONResponse({"success": False, "error": f"Reversal blocked: {risk_blocked_reason}"})
        
        close_res = executor.close_open_trades()
        if not close_res.get("success") and "No open trades" not in str(close_res.get("error", "")):
            return JSONResponse({"success": False, "error": f"Failed to close current trade: {close_res.get('error')}"})
            
        if close_res.get("partial_count", 0) > 0 or close_res.get("failures"):
            return JSONResponse({"success": False, "error": "Reversal aborted: existing position could not be fully closed."})
            
        res = executor.execute_manual_trade(opposite_dir, is_reversal=True)
        return JSONResponse(sanitize_btc_json(res))
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:

        error_msg = f"Reverse Error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return JSONResponse({"success": False, "error": f"Server Error: {str(e)}"})

@router.post("/api/engine/{asset}/trade/close", dependencies=[Depends(require_auth), Depends(require_bot_control)])
def api_btc_trade_close(asset: str, request: Request = None):
    """1-Click manual close of all open trades."""
    try:

        if asset.upper() in ACTIVE_PAIRS:


            ticker = get_forex_ticker(asset.upper())
            curr_price = float(ticker.get("price", 1.0))
            open_pos = [p for p in get_open_positions() if p["pair"] == asset.upper()]
            closed = []
            for p in open_pos:
                c = close_position(p["id"], curr_price, "MANUAL_CLOSE")
                if c: closed.append(c)
            return JSONResponse({"success": True, "closed_count": len(closed)})

        guest_id = _get_guest_id(request) if request else None

        res = get_auto_executor(asset, guest_id=guest_id).close_open_trades()
        return JSONResponse(sanitize_btc_json(res))
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        return JSONResponse({"success": False, "error": f"Close trade error: {str(e)}"}, status_code=500)

@router.get("/api/engine/{asset}/trade/history", dependencies=[Depends(require_auth)])
def api_btc_trade_history(asset: str, mode: Optional[str] = None, request: Request = None):
    """Returns list of all historical trades and P&L results."""

    if asset.upper() in ACTIVE_PAIRS:

        history = get_trade_history()
        pair_trades = [t for t in history if t.get("pair") == asset.upper()]
        res = []
        for t in pair_trades:
            is_win = float(t.get("realized_pnl", 0)) > 0
            size_units = int(t.get("size", 10000))
            lots = size_units / 100000
            res.append({
                "id": t.get("id"),
                "ticker": f"{t.get('pair')} SPOT",
                "side": t.get("side"),
                "direction": t.get("side"),
                "count": f"{lots:.2f} Lots",
                "entry_price": t.get("entry_price"),
                "exit_price": t.get("close_price"),
                "pnl": t.get("realized_pnl", 0.0),
                "result": "WIN" if is_win else "LOSS",
                "status": "CLOSED",
                "mode": "PAPER",
                "timestamp": t.get("opened_at"),
                "settled_at": t.get("closed_at"),
                "exit_reason": t.get("close_reason", "MANUAL"),
                "recommendation": f"{t.get('side')} {lots:.2f} Lots {t.get('pair')}",
                "conviction_grade": "FOREX AI",
                "conviction_badge": "SPOT FX",
                "catalysts": [f"SL: {t.get('sl', 'N/A')}", f"TP: {t.get('tp', 'N/A')}"]
            })
        return JSONResponse(res)

    # Check if a specific registered user is targeted (via ?user=, ?user_id=, numeric ?guest=, or request.state.target_user_id)
    target_user_id = getattr(request.state, "target_user_id", None) if request else None

    if target_user_id:

        try:
            from backend.database.trade_store import TradeStore
            user_history = TradeStore.get_recent_trades(target_user_id, limit=200)
            if mode:
                user_history = [t for t in user_history if str(t.get("mode", "PAPER")).upper() == mode.upper()]
            u = get_user_by_id(target_user_id) or {}
            u_style = u.get("trading_style", "AUTO")
            u_source = u.get("signal_source", "RL_DQN")
            u_model = u.get("model_choice", "RL_DQN")
            enriched_user_hist = [
                enrich_trade_metadata(dict(t), default_style=u_style, default_source=u_source, default_model=u_model)
                for t in user_history
            ]
            return JSONResponse(sanitize_btc_json(enriched_user_hist[::-1]))
        except Exception as e:
            logger.warning(f"Unexpected error parsing history: {e}")

    guest_id = _get_guest_id(request) if request else None


    history = get_auto_executor(asset, guest_id=guest_id).get_trades_history()
    if mode:
        history = [t for t in history if t.get("mode") == mode.upper()]
    enriched_hist = [enrich_trade_metadata(dict(t)) for t in history]
    return JSONResponse(sanitize_btc_json(enriched_hist[::-1]))

@router.get("/api/engine/{asset}/calibration/drift")
def api_btc_calibration_drift(asset: str, min_samples: int = 40, window: int = 100):
    res = get_auto_executor(asset).check_live_calibration_drift(min_samples=min_samples, window=window)
    return JSONResponse(sanitize_btc_json(res))

@router.get("/api/engine/{asset}/mode", dependencies=[Depends(require_auth)])
def api_btc_mode(asset: str, request: Request = None):
    guest_id = _get_guest_id(request) if request else None

    if guest_id:
        return JSONResponse({"mode": "PAPER"})
    return JSONResponse({"mode": get_auto_executor(asset).mode})

@router.get("/api/engine/{asset}/paper/balance", dependencies=[Depends(require_auth)])
def api_btc_paper_balance(asset: str, request: Request = None):

    guest_id = _get_guest_id(request) if request else None

    return JSONResponse({"balance": load_balance(guest_id=guest_id)})

@router.post("/api/engine/{asset}/paper/balance/reset", dependencies=[Depends(require_auth)])
def api_btc_paper_balance_reset(asset: str, request: Request = None):



    target_user_id = None
    if request:
        req_uid = getattr(request.state, "user_id", None)
        if req_uid:
            target_user_id = req_uid
        else:
            guest_id = _get_guest_id(request)
            if guest_id and str(guest_id).isdigit():
                target_user_id = int(guest_id)

    if target_user_id:
        reset_user_paper_balance_and_pnl(int(target_user_id), balance=500.0)
        return JSONResponse({"balance": 500.0, "pnl": 0.0, "status": "reset"})

    guest_id = _get_guest_id(request) if request else None
    new_bal = reset_balance(guest_id=guest_id)
    return JSONResponse({"balance": new_bal, "pnl": 0.0})

@router.get("/api/engine/{asset}/candles")
def api_btc_candles(asset: str, timeframe: str = "15m"):
    """
    Returns formatted candlestick data + indicators + pattern markers + volume series
    for TradingView Lightweight Charts for the selected timeframe.
    """

    
    try:
        is_fx = asset in ACTIVE_PAIRS
        prec = 5 if is_fx else 2

        if is_fx:



            df = fetch_forex_candles(asset, timeframe)
            df_ind = add_all_indicators(df)
            fx_analysis = _cached_analyze_forex_pair(asset, timeframe)
            analysis = {
                "trade_setup": {
                    "entry_price": fx_analysis.get("price"),
                    "stop_loss": fx_analysis.get("sl"),
                    "take_profit_1": fx_analysis.get("tp")
                },
                "target_benchmark": {
                    "target_price": fx_analysis.get("tp") or fx_analysis.get("price")
                }
            }
        else:
            df, analysis = get_cached_btc_analysis(asset=asset, timeframe=timeframe)
            df_ind = add_all_indicators(df)

        candles = []
        ema9_data = []
        ema21_data = []
        ema50_data = []
        ema200_data = []
        markers = []

        for i, row in df_ind.iterrows():
            t = int(row["time"])
            candles.append({
                "time": t,
                "open": round(float(row["open"]), prec),
                "high": round(float(row["high"]), prec),
                "low": round(float(row["low"]), prec),
                "close": round(float(row["close"]), prec),
            })

            if not pd.isna(row.get("ema_9", None)):
                ema9_data.append({"time": t, "value": round(float(row["ema_9"]), prec)})
            if not pd.isna(row.get("ema_21", None)):
                ema21_data.append({"time": t, "value": round(float(row["ema_21"]), prec)})
            if not pd.isna(row.get("ema_50", None)):
                ema50_data.append({"time": t, "value": round(float(row["ema_50"]), prec)})
            if not pd.isna(row.get("ema_200", None)):
                ema200_data.append({"time": t, "value": round(float(row["ema_200"]), prec)})

        for j in range(max(0, len(df_ind) - 20), len(df_ind)):
            sub = df_ind.iloc[: j + 1]
            pats = detect_candlestick_patterns(sub)
            if pats:
                p = pats[-1]
                t_pat = int(df_ind.iloc[j]["time"])
                markers.append({
                    "time": t_pat,
                    "position": "belowBar" if p["type"] == "BULLISH" else "aboveBar",
                    "color": "#00e676" if p["type"] == "BULLISH" else "#ff3d57",
                    "shape": "arrowUp" if p["type"] == "BULLISH" else "arrowDown",
                    "text": p["name"],
                })

        if asset in ACTIVE_PAIRS:

            ticker = get_forex_ticker(asset)
        else:
            ticker = get_asset_ticker(asset)
            
        volume_series = format_volume_series(df_ind)
        target_benchmark = analysis.get("target_benchmark", {})

        return JSONResponse(sanitize_btc_json({
            "candles": candles,
            "volume": volume_series,
            "ema9": ema9_data,
            "ema21": ema21_data,
            "ema50": ema50_data,
            "ema200": ema200_data,
            "markers": markers,
            "ticker": ticker,
            "target_price": target_benchmark.get("target_price"),
            "trade_setup": analysis.get("trade_setup"),
            "target_benchmark": target_benchmark
        }))
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError, sqlite3.OperationalError) as e:
        static_backup = os.path.join(STATIC_DIR, "data", "btc_candles.json")
        if os.path.exists(static_backup):
            try:
                with open(static_backup, "r", encoding="utf-8") as f:
                    return JSONResponse(json.load(f))
            except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
                logger.warning(f"Failed to load static backup: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
