"""

Gemini 15-Minute Contract Master Decision Engine & Candle-Transition Analyzer.



Architecture:

1. Local AI / Quant Pipeline acts as the Intelligence Gatherer:

   - Collects the last 3 closed 15m candles (OHLCV, body %, upper/lower wick %, volume)

   - Collects the first 35-65s opening drive of the new 15m contract vs. Kalshi strike

   - Collects all technical indicators (EMA 9/21/50, RSI, MACD, ADX, ATR, BB %B, Squeeze, 1H Trend)

   - Collects local ML & Voting Ensemble probabilities (XGBoost, LightGBM, CatBoost, RL)

   - Collects live Kalshi orderbook pricing (YES bid/ask, NO bid/ask) and catalysts

2. Gemini (`gemini-3.5-flash-lite` -> `gemini-3.6-flash` -> `gemini-3.5-flash`) acts as the Head Trader:

   - Evaluates the complete market intelligence dossier during the 65-second opening delay

   - Outputs the authoritative directional decision: "YES" (Up), "NO" (Down), or "PASS"

   - Caches the decision per (asset, interval_id) so execution at T+65s has 0.000ms latency.

"""



import json

import logging

import os

import threading

import time

from typing import Any, Dict, Optional



import requests



logger = logging.getLogger(__name__)



PRIMARY_GEMINI_KEYS = [
    "AQ.Ab8RN6KMwUtDidbZv16kUguJ2zMKa5ahzhlSwGb_HzjbXYcQkA",
    "AQ.Ab8RN6IT2dlcLG7nMA15vuTmrQ3fAz6hhrUnR08nNrM-lJmwzA",
]
_current_gemini_key_idx = 0
_gemini_key_lock = threading.Lock()
# Keys come from the repo .env (GEMINI_API_KEYS / GEMINI_API_KEY) so changing the key there is the only step needed.
# The hardcoded list above is only a last-resort default if .env has no key.
def _load_env_gemini_keys():
    try:
        from pathlib import Path
        from dotenv import dotenv_values
        vals = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    except Exception:
        vals = {}
    raw = os.environ.get("GEMINI_API_KEYS") or vals.get("GEMINI_API_KEYS") or os.environ.get("GEMINI_API_KEY") or vals.get("GEMINI_API_KEY") or ""
    return [k.strip() for k in raw.split(",") if k.strip()]

_env_gemini_keys = _load_env_gemini_keys()
if _env_gemini_keys:
    PRIMARY_GEMINI_KEYS = _env_gemini_keys
DEFAULT_GEMINI_KEY = PRIMARY_GEMINI_KEYS[0]



# Verified working models prioritized by live 200-OK response & high reasoning capability

VERIFIED_GEMINI_MODELS = [
    "gemini-3.5-flash",          # Active Model: Gemini 3.5 Flash (no fallback)
]



# Forensic calibration: Gemini calls >= 74% conf in opening window achieved 85.7% WR (6W-1L),

# whereas < 72% conf calls went 14.3% WR (1W-6L).

MIN_GEMINI_MASTER_CONFIDENCE = 74.0

# Maximum age (seconds) a cached YES/NO decision remains actionable.
# Set to 900.0s (full 15m contract interval) so duplicate Gemini API calls within the same 15m candle are strictly impossible.
MAX_DECISION_AGE_SEC = 900.0



# Per-model cooldown tracker (model_name -> unix timestamp when eligible again)

_MODEL_COOLDOWN_UNTIL: Dict[str, float] = {}



# Cache for Master Decisions: (asset, interval_id) -> dict decision

_MASTER_CACHE: Dict[tuple, Dict[str, Any]] = {}

_MASTER_INFLIGHT: set = set()

_KEY_LOCKS: Dict[tuple, threading.Lock] = {}



# Legacy per-side cache for backward compatibility

_VERDICT_CACHE: Dict[tuple, Dict[str, Any]] = {}

_INFLIGHT_KEYS: set = set()

_CACHE_LOCK = threading.Lock()





def get_gemini_api_key() -> str:
    global _current_gemini_key_idx
    with _gemini_key_lock:
        return PRIMARY_GEMINI_KEYS[_current_gemini_key_idx % len(PRIMARY_GEMINI_KEYS)]

def rotate_gemini_api_key(failed_key: Optional[str] = None) -> str:
    global _current_gemini_key_idx
    with _gemini_key_lock:
        curr = PRIMARY_GEMINI_KEYS[_current_gemini_key_idx % len(PRIMARY_GEMINI_KEYS)]
        if failed_key and failed_key != curr:
            return curr
        _current_gemini_key_idx = (_current_gemini_key_idx + 1) % len(PRIMARY_GEMINI_KEYS)
        new_k = PRIMARY_GEMINI_KEYS[_current_gemini_key_idx % len(PRIMARY_GEMINI_KEYS)]
        logger.warning(f"[GeminiGate] Rotated Gemini API key to {new_k[:12]}...")
        return new_k





def _extract_candle_summary(df_ind) -> Dict[str, Any]:

    """Extracts last 2 closed 15m candles + current opening candle + technical indicators."""

    try:

        if df_ind is None or len(df_ind) < 3:

            return {}

        curr = df_ind.iloc[-1]

        prev = df_ind.iloc[-2]

        prev2 = df_ind.iloc[-3]



        def _candle_stats(row) -> Dict[str, Any]:

            o = float(row.get("open", 0.0) or 0.0)

            h = float(row.get("high", 0.0) or 0.0)

            l = float(row.get("low", 0.0) or 0.0)

            c = float(row.get("close", 0.0) or 0.0)

            v = float(row.get("volume", 0.0) or 0.0)

            rng = max(h - l, 1e-9)

            body = c - o

            upper_wick = h - max(o, c)

            lower_wick = min(o, c) - l

            return {

                "open": round(o, 6),

                "high": round(h, 6),

                "low": round(l, 6),

                "close": round(c, 6),

                "volume": round(v, 2),

                "signed_body": round(body, 6),

                "body_pct_of_range": round(abs(body) / rng * 100.0, 1),

                "upper_wick_pct": round(upper_wick / rng * 100.0, 1),

                "lower_wick_pct": round(lower_wick / rng * 100.0, 1),

                "direction": "BULLISH" if c >= o else "BEARISH",

            }



        return {

            "prev_closed_15m": _candle_stats(prev),

            "prior_15m_2bars_ago": _candle_stats(prev2),

            "current_opening_candle": _candle_stats(curr),

            "indicators": {

                "rsi": round(float(curr.get("rsi", 50.0) or 50.0), 1),

                "macd": round(float(curr.get("macd", 0.0) or 0.0), 5),

                "macd_hist": round(float(curr.get("macd_hist", 0.0) or 0.0), 5),

                "adx": round(float(curr.get("adx", 20.0) or 20.0), 1),

                "atr": round(float(curr.get("atr", 0.0) or 0.0), 6),

                "ema_9": round(float(curr.get("ema_9", 0.0) or 0.0), 6),

                "ema_21": round(float(curr.get("ema_21", 0.0) or 0.0), 6),

                "ema_50": round(float(curr.get("ema_50", 0.0) or 0.0), 6),

                "bb_pct_b": round(float(curr.get("bb_pct_b", 0.5) or 0.5), 2),

                "bb_squeeze": bool(curr.get("bb_squeeze", False)),

                "trend_1h": str(curr.get("trend_1h", "NEUTRAL")),

            },

        }

    except Exception as e:

        logger.debug(f"[Gemini15MGate] Error extracting candle summary: {e}")

        return {}





def _fetch_live_kalshi_tape_telemetry(ticker: str) -> Dict[str, Any]:

    """

    Fetches real-time Kalshi contract trade tape (/trade-api/v2/markets/trades)

    and public social tape (/v1/social/trades) for the active 15m contract to measure:

      - Aggressive YES vs NO taker volume ($ and contracts)

      - Whale block sweeps (>= 50 contracts per fill)

      - Volume-Weighted Average Price (VWAP) vs latest tape price drift

      - Named public trader activity on this contract

    """

    t_str = str(ticker or "").strip()

    if not t_str or t_str.endswith("_SYNTH") or "TEST" in t_str:

        return {"status": "unavailable_or_synthetic"}



    yes_contracts = 0.0

    no_contracts = 0.0

    yes_dollars = 0.0

    no_dollars = 0.0

    whale_yes_blocks = 0

    whale_no_blocks = 0

    largest_fill = {"side": "NONE", "contracts": 0.0, "price": 0.0}

    yes_price_weighted_sum = 0.0

    total_contracts = 0.0

    latest_yes_price = None

    oldest_yes_price = None

    sample_count = 0



    try:

        r_v2 = requests.get(

            "https://api.elections.kalshi.com/trade-api/v2/markets/trades",

            params={"ticker": t_str, "limit": 80},

            timeout=1.8,

        )

        if r_v2.status_code == 200:

            trades = r_v2.json().get("trades") or []

            sample_count = len(trades)

            for idx, tr in enumerate(trades):

                cnt = float(tr.get("count_fp") or tr.get("count") or 0.0)

                if cnt <= 0:

                    continue

                y_p = float(tr.get("yes_price_dollars") or (float(tr.get("yes_price") or 50) / 100.0))

                n_p = float(tr.get("no_price_dollars") or (1.0 - y_p))

                t_side = str(tr.get("taker_side") or "").lower()



                if idx == 0:

                    latest_yes_price = y_p

                oldest_yes_price = y_p



                total_contracts += cnt

                yes_price_weighted_sum += cnt * y_p



                if t_side == "yes":

                    yes_contracts += cnt

                    yes_dollars += cnt * y_p

                    if cnt >= 50.0:

                        whale_yes_blocks += 1

                    if cnt > largest_fill["contracts"]:

                        largest_fill = {"side": "YES", "contracts": round(cnt, 1), "price": round(y_p, 2)}

                elif t_side == "no":

                    no_contracts += cnt

                    no_dollars += cnt * n_p

                    if cnt >= 50.0:

                        whale_no_blocks += 1

                    if cnt > largest_fill["contracts"]:

                        largest_fill = {"side": "NO", "contracts": round(cnt, 1), "price": round(n_p, 2)}

    except Exception as e:

        logger.debug(f"[GeminiMaster] Kalshi v2 tape fetch skipped for {t_str}: {e}")



    named_traders = []

    try:

        r_soc = requests.get(

            "https://api.elections.kalshi.com/v1/social/trades",

            params={"page_size": 80},

            timeout=1.2,

        )

        if r_soc.status_code == 200:

            for st in (r_soc.json().get("trades") or []):

                if st.get("ticker") != t_str:

                    continue

                m_nick = str(st.get("maker_nickname") or "").strip()

                t_nick = str(st.get("taker_nickname") or "").strip()

                if m_nick or t_nick:

                    named_traders.append({

                        "taker": t_nick or "anon",

                        "maker": m_nick or "anon",

                        "taker_action": st.get("taker_action"),

                        "taker_side": str(st.get("taker_side") or "").upper(),

                        "contracts": float(st.get("count_fp") or st.get("count") or 0.0),

                        "price": float(st.get("price_dollars") or 0.50),

                    })

                    if len(named_traders) >= 5:

                        break

    except Exception:

        pass



    tot_dollars = yes_dollars + no_dollars

    net_flow_ratio = ((yes_dollars - no_dollars) / tot_dollars) if tot_dollars > 0 else 0.0

    vwap_yes = (yes_price_weighted_sum / total_contracts) if total_contracts > 0 else 0.50

    tape_drift = (latest_yes_price - oldest_yes_price) if (latest_yes_price is not None and oldest_yes_price is not None) else 0.0



    if net_flow_ratio >= 0.35 and whale_yes_blocks > whale_no_blocks:

        verdict = "STRONG_YES_WHALE_SWEEP"

    elif net_flow_ratio >= 0.18:

        verdict = "MODERATE_YES_TAKER_FLOW"

    elif net_flow_ratio <= -0.35 and whale_no_blocks > whale_yes_blocks:

        verdict = "STRONG_NO_WHALE_SWEEP"

    elif net_flow_ratio <= -0.18:

        verdict = "MODERATE_NO_TAKER_FLOW"

    else:

        verdict = "BALANCED_TWO_WAY_FLOW"



    return {

        "sample_fills_count": sample_count,

        "yes_taker_contracts": round(yes_contracts, 1),

        "no_taker_contracts": round(no_contracts, 1),

        "yes_taker_dollars": round(yes_dollars, 2),

        "no_taker_dollars": round(no_dollars, 2),

        "net_taker_flow_ratio_minus1_to_plus1": round(net_flow_ratio, 3),

        "whale_blocks_50plus_yes": whale_yes_blocks,

        "whale_blocks_50plus_no": whale_no_blocks,

        "largest_single_fill": largest_fill,

        "vwap_yes_price": round(vwap_yes, 3),

        "latest_yes_tape_price": round(latest_yes_price, 3) if latest_yes_price is not None else None,

        "yes_tape_price_drift": round(tape_drift, 3),

        "named_public_fills": named_traders,

        "tape_orderflow_verdict": verdict,

    }





def _fetch_kalshi_l2_oi_and_hourly_skew(

    asset: str,

    ticker: str,

    strike: float,

    spot: float,

    candle_summary: Dict[str, Any],

) -> Dict[str, Any]:

    """

    Collects the 4 institutional Kalshi v2 microstructure signals:

      1. 60-Second TWAP Settlement / Strike-Lag Dislocation (prev_15m_close vs 60s BRTI averaged strike)

      2. Full Level-2 Orderbook Near-Touch Depth & Liquidity Walls (/markets/{ticker}/orderbook)

      3. Native 1-Minute Contract Candlesticks & Open Interest (OI) Delta (/series/.../candlesticks)

      4. Simultaneous Parent Hourly Strike Ladder Skew (KXBTCD / KXETHD)

    """

    a_up = str(asset or "BTC").upper()

    t_str = str(ticker or "").strip()



    # 1. 60-Second TWAP Strike-Lag Dislocation

    prev_15m = (

        candle_summary.get("prev_closed_15m")

        or candle_summary.get("prev_15m_closed_candle")

        or {}

    )

    prev_close = float(prev_15m.get("close") or strike)

    strike_lag_dislocation = round(prev_close - strike, 6)

    twap_head_start = (

        "BULLISH_YES_HEADSTART"

        if strike_lag_dislocation > 0 and spot > strike

        else "BEARISH_NO_HEADSTART"

        if strike_lag_dislocation < 0 and spot < strike

        else "NEUTRAL"

    )



    if not t_str or t_str.endswith("_SYNTH") or "TEST" in t_str:

        return {

            "twap_60s_strike_dislocation": {

                "prev_15m_close_minus_60s_twap_strike": strike_lag_dislocation,

                "opening_twap_regime": twap_head_start,

            },

            "status": "synthetic_or_test_ticker",

        }



    # 2. Level-2 Orderbook Near-Touch Depth (top 5 resting bid levels on YES vs NO)

    l2_summary: Dict[str, Any] = {}

    try:

        r_ob = requests.get(

            f"https://api.elections.kalshi.com/trade-api/v2/markets/{t_str}/orderbook",

            timeout=1.6,

        )

        if r_ob.status_code == 200:

            ob_fp = r_ob.json().get("orderbook_fp") or {}

            yes_lvls = ob_fp.get("yes_dollars") or []

            no_lvls = ob_fp.get("no_dollars") or []



            top5_yes = yes_lvls[-5:] if yes_lvls else []

            top5_no = no_lvls[-5:] if no_lvls else []



            yes_depth_contracts = sum(float(x[1]) for x in top5_yes)

            no_depth_contracts = sum(float(x[1]) for x in top5_no)

            yes_depth_dollars = sum(float(x[0]) * float(x[1]) for x in top5_yes)

            no_depth_dollars = sum(float(x[0]) * float(x[1]) for x in top5_no)



            max_yes_wall = max((float(x[1]) for x in top5_yes), default=0.0)

            max_no_wall = max((float(x[1]) for x in top5_no), default=0.0)

            tot_depth = yes_depth_contracts + no_depth_contracts

            l2_imb = ((yes_depth_contracts - no_depth_contracts) / tot_depth) if tot_depth > 0 else 0.0



            l2_summary = {

                "near_touch_top5_yes_bid_contracts": round(yes_depth_contracts, 1),

                "near_touch_top5_no_bid_contracts": round(no_depth_contracts, 1),

                "near_touch_top5_yes_bid_dollars": round(yes_depth_dollars, 2),

                "near_touch_top5_no_bid_dollars": round(no_depth_dollars, 2),

                "largest_near_touch_yes_bid_wall": round(max_yes_wall, 1),

                "largest_near_touch_no_bid_wall": round(max_no_wall, 1),

                "l2_book_imbalance_minus1_to_plus1": round(l2_imb, 3),

                "l2_wall_bias": (

                    "HEAVY_YES_BID_SUPPORT"

                    if l2_imb >= 0.22

                    else "HEAVY_NO_BID_SUPPORT"

                    if l2_imb <= -0.22

                    else "BALANCED_BOOK"

                ),

            }

    except Exception as e:

        logger.debug(f"[GeminiMaster] L2 orderbook fetch skipped for {t_str}: {e}")



    # 3. Native 1-Minute Contract Candlesticks & Open Interest (OI) Delta

    oi_summary: Dict[str, Any] = {}

    try:

        series_ticker = t_str.split("-")[0] if "-" in t_str else f"KX{a_up}15M"

        now_ts = int(time.time())

        r_cdl = requests.get(

            f"https://api.elections.kalshi.com/trade-api/v2/series/{series_ticker}/markets/{t_str}/candlesticks",

            params={"start_ts": now_ts - 900, "end_ts": now_ts + 60, "period_interval": 1},

            timeout=1.6,

        )

        if r_cdl.status_code == 200:

            bars = r_cdl.json().get("candlesticks") or []

            if bars:

                first_oi = float(bars[0].get("open_interest_fp") or 0.0)

                last_oi = float(bars[-1].get("open_interest_fp") or 0.0)

                oi_delta = last_oi - first_oi

                oi_pct = ((oi_delta / first_oi) * 100.0) if first_oi > 0 else 0.0

                cum_vol = sum(float(b.get("volume_fp") or 0.0) for b in bars)



                first_mean = float((bars[0].get("price") or {}).get("mean_dollars") or 0.50)

                last_mean = float((bars[-1].get("price") or {}).get("mean_dollars") or 0.50)

                last_close = float((bars[-1].get("price") or {}).get("close_dollars") or last_mean)

                vwap_change = last_mean - first_mean



                oi_summary = {

                    "bars_1m_count": len(bars),

                    "initial_open_interest_contracts": round(first_oi, 1),

                    "current_open_interest_contracts": round(last_oi, 1),

                    "open_interest_delta_contracts": round(oi_delta, 1),

                    "open_interest_growth_pct": round(oi_pct, 1),

                    "cumulative_contract_volume": round(cum_vol, 1),

                    "first_1m_vwap_yes_price": round(first_mean, 3),

                    "latest_1m_vwap_yes_price": round(last_mean, 3),

                    "latest_1m_close_yes_price": round(last_close, 3),

                    "contract_vwap_drift": round(vwap_change, 3),

                    "oi_conviction_regime": (

                        "FRESH_BULLISH_YES_OI_BUILDUP"

                        if (oi_delta > 500 and vwap_change >= 0.02)

                        else "FRESH_BEARISH_NO_OI_BUILDUP"

                        if (oi_delta > 500 and vwap_change <= -0.02)

                        else "POSITION_UNWIND_OR_NEUTRAL_OI"

                    ),

                }

    except Exception as e:

        logger.debug(f"[GeminiMaster] 1m contract candlesticks fetch skipped for {t_str}: {e}")



    # 4. Multi-Interval Kalshi Term Structure (Next Upcoming 15M Contract + Hourly Ladder)

    next_15m_summary: Dict[str, Any] = {}

    try:

        series_15m = f"KX{a_up}15M"

        r_next = requests.get(

            "https://api.elections.kalshi.com/trade-api/v2/markets",

            params={"series_ticker": series_15m, "status": "open", "limit": 10},

            timeout=1.2,

        )

        if r_next.status_code == 200:

            m_list = r_next.json().get("markets") or []

            other_15m = [m for m in m_list if m.get("ticker") != t_str and m.get("status") in ("active", "open")]

            if other_15m:

                next_m = other_15m[0]

                nyb = float(next_m.get("yes_bid_dollars") or next_m.get("yes_bid") or 0.0)

                nya = float(next_m.get("yes_ask_dollars") or next_m.get("yes_ask") or 0.0)

                if nyb > 1.0: nyb /= 100.0

                if nya > 1.0: nya /= 100.0

                next_15m_summary = {

                    "next_ticker": next_m.get("ticker"),

                    "next_close_time": next_m.get("close_time"),

                    "next_yes_bid": round(nyb, 3),

                    "next_yes_ask": round(nya, 3),

                    "next_yes_mid_prob": round((nyb + nya) / 2.0, 3) if (nyb > 0 and nya > 0) else round(nya, 3),

                }

    except Exception as e:

        logger.debug(f"[GeminiMaster] Next 15m term structure query skipped: {e}")



    # 4b. Simultaneous Hourly Strike Ladder Skew (e.g. KXBTCD, KXETHD)

    hourly_summary: Dict[str, Any] = {}

    if a_up in ("BTC", "ETH", "SOL", "DOGE"):

        try:

            hr_series = f"KX{a_up}D"

            r_hr = requests.get(

                "https://api.elections.kalshi.com/trade-api/v2/markets",

                params={"series_ticker": hr_series, "status": "open", "limit": 30},

                timeout=1.5,

            )

            if r_hr.status_code == 200:

                hr_mkts = r_hr.json().get("markets") or []

                valid_hr = [m for m in hr_mkts if m.get("floor_strike") is not None]

                if valid_hr:

                    nearest = min(valid_hr, key=lambda x: abs(float(x.get("floor_strike") or 0.0) - strike))

                    h_strike = float(nearest.get("floor_strike") or 0.0)

                    h_y_bid = float(nearest.get("yes_bid_dollars") or 0.0)

                    h_y_ask = float(nearest.get("yes_ask_dollars") or 0.0)

                    h_mid = round((h_y_bid + h_y_ask) / 2.0, 3) if (h_y_bid > 0 and h_y_ask > 0) else h_y_ask

                    hourly_summary = {

                        "hourly_ticker": nearest.get("ticker"),

                        "nearest_hourly_floor_strike": h_strike,

                        "hourly_yes_bid": h_y_bid,

                        "hourly_yes_ask": h_y_ask,

                        "hourly_yes_mid_prob": h_mid,

                        "hourly_volume_contracts": float(nearest.get("volume_fp") or 0.0),

                    }

        except Exception:

            pass



    return {

        "twap_60s_strike_dislocation": {

            "prev_15m_close_minus_60s_twap_strike": strike_lag_dislocation,

            "opening_twap_regime": twap_head_start,

        },

        "level2_orderbook_depth": l2_summary,

        "contract_1m_candlesticks_and_open_interest": oi_summary,

        "parent_hourly_strike_ladder": hourly_summary,

        "next_upcoming_15m_contract": next_15m_summary,

    }





def _extract_opening_micro_and_btc_lead(asset: str, spot: float, strike: float) -> Dict[str, Any]:

    """

    Computes:

      1. Intrabar 1m opening micro-trajectory (higher-lows vs lower-highs & 3m velocity).

      2. Cross-asset BTC 15m Lead-Lag impulse when trading ETH, SOL, or DOGE.

    """

    a_up = str(asset or "BTC").upper()

    micro_1m: Dict[str, Any] = {"trajectory": "NEUTRAL"}

    btc_lead: Dict[str, Any] = {"applicable": a_up in ("ETH", "SOL", "DOGE")}



    try:

        from backend.engine.multi_asset_fetcher import fetch_asset_candles



        df_1m = fetch_asset_candles(a_up, "1m", limit=5)

        if df_1m is not None and len(df_1m) >= 3:

            c1 = df_1m.iloc[-1]

            c2 = df_1m.iloc[-2]

            c3 = df_1m.iloc[-3]

            lows = [float(c3.get("low", 0)), float(c2.get("low", 0)), float(c1.get("low", 0))]

            highs = [float(c3.get("high", 0)), float(c2.get("high", 0)), float(c1.get("high", 0))]

            open_3m = float(c3.get("open", 0) or spot)

            close_now = float(c1.get("close", 0) or spot)

            vel_pct = ((close_now - open_3m) / open_3m * 100.0) if open_3m > 0 else 0.0

            higher_lows = lows[2] >= lows[1] >= lows[0] and close_now >= open_3m

            lower_highs = highs[2] <= highs[1] <= highs[0] and close_now <= open_3m

            if higher_lows and vel_pct > 0.02:

                traj = "BULLISH_HIGHER_LOWS_DRIVE"

            elif lower_highs and vel_pct < -0.02:

                traj = "BEARISH_LOWER_HIGHS_FLUSH"

            elif close_now > strike and open_3m < strike:

                traj = "BULLISH_STRIKE_RECLAIM"

            elif close_now < strike and open_3m > strike:

                traj = "BEARISH_STRIKE_BREAKDOWN"

            else:

                traj = "TWO_WAY_ROTATION"

            micro_1m = {

                "last_3m_velocity_pct": round(vel_pct, 4),

                "higher_lows_sequence": bool(higher_lows),

                "lower_highs_sequence": bool(lower_highs),

                "trajectory": traj,

            }



        if a_up in ("ETH", "SOL", "DOGE"):

            df_btc = fetch_asset_candles("BTC", "15m", limit=3)

            if df_btc is not None and len(df_btc) >= 2:

                b_curr = df_btc.iloc[-1]

                b_open = float(b_curr.get("open", 0) or 0.0)

                b_close = float(b_curr.get("close", 0) or 0.0)

                b_imp_pct = ((b_close - b_open) / b_open * 100.0) if b_open > 0 else 0.0

                btc_lead = {

                    "applicable": True,

                    "btc_current_15m_open": round(b_open, 2),

                    "btc_current_spot": round(b_close, 2),

                    "btc_15m_impulse_pct": round(b_imp_pct, 4),

                    "btc_macro_regime": (

                        "STRONG_BTC_TAILWIND_UP"

                        if b_imp_pct >= 0.18

                        else "STRONG_BTC_HEADWIND_DOWN"

                        if b_imp_pct <= -0.18

                        else "NEUTRAL_BTC_DRIFT"

                    ),

                }

    except Exception as e:

        logger.debug(f"[GeminiMaster] 1m micro / BTC lead-lag extraction skipped for {a_up}: {e}")



    return {"opening_1m_micro_trend": micro_1m, "btc_lead_lag_context": btc_lead}





def _build_intelligence_dossier(

    asset: str,

    interval_id: str,

    strike: float,

    spot: float,

    sec_elapsed: float,

    active_m: Dict[str, Any],

    forecast: Dict[str, Any],

    df_ind: Any,

) -> Dict[str, Any]:

    """Packages all available local AI, chart, orderbook, live Kalshi tape, L2 depth, OI delta, loss memory, and sub-model stats into one JSON dossier."""

    candle_summary = _extract_candle_summary(df_ind)

    kalshi_tape = _fetch_live_kalshi_tape_telemetry(interval_id)

    kalshi_micro = _fetch_kalshi_l2_oi_and_hourly_skew(

        asset=asset,

        ticker=interval_id,

        strike=strike,

        spot=spot,

        candle_summary=candle_summary,

    )

    micro_and_lead = _extract_opening_micro_and_btc_lead(asset=asset, spot=spot, strike=strike)

    

    # Ingest sub-second spot streaming, stale quote sniping, few-shot feedback & settlement locks
    from backend.btc.spot_streamer import get_live_spot_tick, get_live_spot_price
    from backend.btc.stale_quote_sniper import evaluate_stale_quote_snipe
    from backend.btc.exhaustion_detector import compute_exhaustion_metrics
    from backend.engine.macro_calendar import check_macro_event_horizon
    from backend.btc.liquidation_feed import fetch_perp_liquidation_and_funding
    from backend.btc.macro_beta_flow import fetch_cross_asset_macro_beta
    from backend.btc.few_shot_feedback import get_recent_execution_feedback
    from backend.btc.cf_synthetic_settler import evaluate_synthetic_settlement_lock, record_spot_sample

    live_tick = get_live_spot_tick(asset)
    if live_tick and live_tick.get("price", 0) > 0:
        spot = float(live_tick["price"])

    # Record sample for 60s synthetic settlement index
    record_spot_sample(asset, spot)
    settlement_lock = evaluate_synthetic_settlement_lock(asset, strike, 900.0 - sec_elapsed)
    few_shot_memory = get_recent_execution_feedback(asset, limit=3)

    yes_ask_f = float(active_m.get("yes_ask") or 0.0)
    yes_bid_f = float(active_m.get("yes_bid") or 0.0)
    no_ask_f = float(active_m.get("no_ask") or 0.0)
    no_bid_f = float(active_m.get("no_bid") or 0.0)

    # Compute Cumulative Volume Delta (CVD) orderflow and divergence
    cvd_telemetry = {"cvd_trend": "NEUTRAL", "whale_absorption": "BALANCED", "divergence": "NONE"}
    try:
        if df_ind is not None and len(df_ind) >= 10:
            from backend.btc.indicators import compute_cvd_proxy, detect_cvd_divergences
            df_calc = df_ind.copy()
            if "cvd" not in df_calc.columns:
                df_calc["cvd"] = compute_cvd_proxy(df_calc)
            cvd_diff = df_calc["cvd"].diff().iloc[-3:].sum()
            price_diff = df_calc["close"].diff().iloc[-3:].sum()
            cvd_divs = detect_cvd_divergences(df_calc)
            
            trend = "BULLISH_CVD" if cvd_diff > 0 else "BEARISH_CVD"
            absorption = "BULLISH_ABSORPTION" if (cvd_diff > 0 and price_diff <= 0) else ("BEARISH_ABSORPTION" if (cvd_diff < 0 and price_diff >= 0) else "BALANCED")
            div_type = cvd_divs[0].get("type", "NONE") if cvd_divs else "NONE"
            
            cvd_telemetry = {
                "cvd_trend": trend,
                "whale_absorption": absorption,
                "divergence": div_type,
                "cvd_3bar_delta": round(float(cvd_diff), 2)
            }
    except Exception as e:
        logger.debug(f"CVD extraction note: {e}")

    stale_snipe_signal = evaluate_stale_quote_snipe(
        asset=asset,
        ticker=interval_id,
        strike=strike,
        current_spot=spot,
        sec_elapsed=sec_elapsed,
        yes_ask=yes_ask_f,
        yes_bid=yes_bid_f,
        no_ask=no_ask_f,
        no_bid=no_bid_f,
    )



    exhaustion_metrics = compute_exhaustion_metrics(df_ind, spot, strike)

    macro_event_horizon = check_macro_event_horizon()

    perp_liquidation_data = fetch_perp_liquidation_and_funding(asset)

    cross_asset_beta = fetch_cross_asset_macro_beta(asset)



    active_loss_vetoes = []

    try:

        from backend.btc.loss_analyzer import loss_analyzer



        active_loss_vetoes = loss_analyzer.get_loss_regime_vetoes(asset)

    except Exception:

        pass



    yes_ask = float(active_m.get("yes_ask") or 0.0)

    yes_bid = float(active_m.get("yes_bid") or 0.0)

    no_ask = float(active_m.get("no_ask") or 0.0)

    no_bid = float(active_m.get("no_bid") or 0.0)



    ml_prob_up = float(forecast.get("ml_prob", 0.50) or 0.50) * 100.0

    pre_gate_dir = str(forecast.get("pre_gate_direction", "PASS"))

    pre_gate_prob = float(forecast.get("pre_gate_prob", 50.0) or 50.0)

    local_rule_dir = str(forecast.get("direction", "PASS"))

    local_rule_prob = float(forecast.get("probability_percent", 50.0) or 50.0)

    consensus = forecast.get("consensus") or {}

    catalysts = [str(c) for c in (forecast.get("catalysts") or [])[:8]]



    # Deadzone reference for asset

    a_up = str(asset).upper()

    if a_up == "BTC":

        deadzone_tol = 15.0

    elif a_up == "ETH":

        deadzone_tol = 1.10

    elif a_up == "SOL":

        deadzone_tol = 0.08

    elif a_up == "DOGE":

        deadzone_tol = 0.0001

    elif a_up in ("EURUSD", "GBPUSD", "AUDUSD"):

        deadzone_tol = 0.00008

    elif a_up == "USDJPY":

        deadzone_tol = 0.015

    else:

        deadzone_tol = max(strike * 0.00025, 0.0001)



    return {

        "contract": {

            "asset": a_up,

            "ticker": interval_id,

            "seconds_elapsed_in_15m_candle": round(sec_elapsed, 1),

            "seconds_remaining": round(900.0 - sec_elapsed, 1),

            "strike_price": strike,

            "current_spot_price": spot,

            "spot_minus_strike": round(spot - strike, 6),

            "strike_pin_deadzone_threshold": deadzone_tol,

            "is_outside_deadzone": abs(spot - strike) > deadzone_tol,

        },

        "kalshi_orderbook": {

            "yes_ask": yes_ask,

            "yes_bid": yes_bid,

            "no_ask": no_ask,

            "no_bid": no_bid,

            "yes_spread": round(max(0.0, yes_ask - yes_bid), 4) if (yes_ask > 0 and yes_bid > 0) else 0.99,

            "no_spread": round(max(0.0, no_ask - no_bid), 4) if (no_ask > 0 and no_bid > 0) else 0.99,

            "yes_in_valid_corridor_46_to_68c": 0.46 <= yes_ask <= 0.68,

            "no_in_valid_corridor_46_to_68c": 0.46 <= no_ask <= 0.68,

        },

        "live_kalshi_tape_and_whale_flow": kalshi_tape,

        "kalshi_microstructure_l2_oi_twap": kalshi_micro,

        "opening_1m_micro_trend": micro_and_lead.get("opening_1m_micro_trend", {}),

        "btc_lead_lag_context": micro_and_lead.get("btc_lead_lag_context", {}),

        "stale_quote_arbitrage_opportunity": stale_snipe_signal,
        "recent_few_shot_execution_feedback": few_shot_memory,
        "synthetic_60s_settlement_lock": settlement_lock,
        "synthetic_settlement_index_and_lock": settlement_lock,
        "cvd_orderflow_delta": cvd_telemetry,
        "subsecond_spot_stream": live_tick or {"source": "rest_fallback", "price": spot},
        "exhaustion_and_stretch_metrics": exhaustion_metrics,

        "macro_economic_event_horizon": macro_event_horizon,

        "perp_liquidations_and_funding": perp_liquidation_data,

        "cross_asset_macro_beta_flow": cross_asset_beta,

        "recent_loss_regime_warnings": active_loss_vetoes,

        "local_ai_models": {

            "ml_ensemble_prob_above_strike_pct": round(ml_prob_up, 1),

            "ml_ensemble_prob_below_strike_pct": round(100.0 - ml_prob_up, 1),

            "pre_gate_raw_direction": pre_gate_dir,

            "pre_gate_raw_confidence_pct": round(pre_gate_prob, 1),

            "local_technical_gate_direction": local_rule_dir,

            "local_technical_gate_confidence_pct": round(local_rule_prob, 1),

            "voting_ensemble_consensus": consensus,

            "detected_catalysts_and_structure": catalysts,

            "primary_edge_summary": str(forecast.get("primary_edge", "")),

        },

        "price_action_and_indicators": candle_summary,

    }





def _call_gemini_master_decision(dossier: Dict[str, Any], allow_pass: bool = True) -> Dict[str, Any]:

    """

    Sends the full market intelligence dossier to Gemini and returns the authoritative

    directional call: YES (Up/Above Strike), NO (Down/Below Strike), or PASS.

    If allow_pass is False, strictly forces an authoritative binary choice (YES or NO).

    """

    api_key = get_gemini_api_key()

    contract = dossier.get("contract", {})

    asset = contract.get("asset", "BTC")

    ticker = contract.get("ticker", "")



    pass_instruction = (
        'Choose "PASS" if the market is locked in a strike-pin deadzone with compressed volatility, or if signals are genuinely 50/50 contradictory chop.'
        if allow_pass
        else 'DO NOT CHOOSE PASS. The only permitted outputs are "YES" or "NO". PASS is not an option. A trade MUST be entered on this interval. Break any 50/50 tie by weighing micro-momentum (opening 1m candle, higher-lows vs lower-highs, whale tape, and positive asymmetric payoff).'
    )
    direction_schema = '"YES" or "NO" or "PASS"' if allow_pass else '"YES" or "NO"'
    decision_header = 'YOUR MANDATE: MAKE THE UP (YES), DOWN (NO), OR PASS DECISION:' if allow_pass else 'YOUR MANDATE: MAKE THE UP (YES) OR DOWN (NO) DECISION (PASS IS STRICTLY PROHIBITED):'
    macro_instruction = 'Choose PASS (or demand >= 85% conviction if forced).' if allow_pass else 'Demand >= 85% conviction before picking the winning side.'

    prompt = f"""You are the Chief Quantitative Portfolio Manager for an institutional 15-minute binary options desk on Kalshi.
We are {contract.get('seconds_elapsed_in_15m_candle')}s into a new 15-minute {asset} contract ({ticker}) after waiting for the opening shakeout.
Our local AI pipeline has gathered all price action, candle transition structure, technical indicators, ML ensemble probabilities, Kalshi L2 orderbook depth, 1m Open Interest (OI) delta, 60s BRTI TWAP strike dislocation, and live Kalshi whale tape orderflow below.

COMPLETE MARKET INTELLIGENCE DOSSIER:
{json.dumps(dossier, indent=2)}

{decision_header}
0. Check Stale Quote Arbitrage, Synthetic Settlement Locks, & Recent Execution Lessons FIRST:
   - Check `stale_quote_arbitrage_opportunity`: if `is_snipe_opportunity` is true, an exploitable latency dislocation exists between real-time CF constituent spot and Kalshi's sluggish orderbook! Spot has already crossed strike by >= 0.14%, but contracts are still offered at 48¢–54¢. PRIORITIZE following the `recommended_side` with high conviction (>= 85%) to capture the lag before market makers re-quote!
   - Check `synthetic_60s_settlement_lock`: if `math_locked_outcome` is 'LOCKED_YES' or 'LOCKED_NO', the 60-second CF Benchmarks settlement average is mathematically locked! Follow this outcome with maximum confidence (>= 90%).
   - Review `recent_few_shot_execution_feedback`: inspect recent trades and post-mortem lessons on this asset. If recent trades on this asset were stopped out or lost due to false breakouts, chopped corridors, or late exhaustion, SELF-CORRECT and do NOT repeat the identical failure pattern!
   - Check `macro_economic_event_horizon`: if `volatility_freeze_recommended` is true (within 10m of major FOMC/CPI release), DO NOT take high-risk directional bets. {macro_instruction}
   - Check `exhaustion_and_stretch_metrics`: if `actionable_guard` indicates `VETO_YES_BUY_BREAKOUT` (RSI >= 70, BB %b >= 0.88, VWAP >= +2.5 sigma, or Bearish Divergence) without ADX >= 28 trend support, DO NOT buy YES into the exhaustion top! Likewise, if `VETO_NO_BUY_BREAKDOWN` (RSI <= 30, BB %b <= 0.12, or Bullish Divergence), DO NOT short into the bottom!
   - Check `perp_liquidations_and_funding`: if `short_squeeze_risk` is HIGH or `funding_rate_bias` is extreme short-crowded, do NOT bet NO against an ongoing short squeeze cascade.
   - Check `cross_asset_macro_beta_flow`: verify whether broader crypto market momentum (`macro_risk_sentiment`) confirms or contradicts the local 15m move.

1. Analyze the Just-Closed 15m Candle + 1m Micro-Trajectory + 60s TWAP Strike Dislocation:
   - Did the previous 15m candle close with strong directional displacement, or did it leave a heavy counter-wick rejection (>50% wick) signaling reversal?
   - Check `twap_60s_strike_dislocation`: because Kalshi's strike is the 60-second average of the prior candle's final minute, a late spike/dump gives the new contract an immediate structural head start (`BULLISH_YES_HEADSTART` or `BEARISH_NO_HEADSTART`).
   - Check `opening_1m_micro_trend`: is the 1-minute intrabar structure making higher-lows (`BULLISH_HIGHER_LOWS_DRIVE`) or lower-highs (`BEARISH_LOWER_HIGHS_FLUSH`)?

2. Weigh the Local AI Models + Technical Indicators + Mean-Reversion Exhaustion:
   - Consider `ml_ensemble_prob_above_strike_pct`, `voting_ensemble_consensus`, `ema_9` vs `ema_21`, `rsi`, `macd_hist`, `adx`, `bb_pct_b`, and `trend_1h`.
   - Avoid chasing late exhaustion: do NOT buy `NO` into extreme oversold exhaustion (`rsi < 34` and `bb_pct_b < 0.12`) or `YES` into extreme overbought exhaustion (`rsi > 66` and `bb_pct_b > 0.88`) UNLESS trend strength is explosive (`adx >= 28` and `ema_9 > ema_21`). When ADX >= 28 and EMA_9 > EMA_21, high RSI is a hallmark of explosive MOMENTUM EXPANSION; DO NOT fade high-ADX bull trends with a NO call!
   - Respect `recent_loss_regime_warnings` and `btc_lead_lag_context` (for ETH/SOL/DOGE, never fight a strong >= 0.18% opposing BTC 15m impulse).

3. Weigh Kalshi L2 Book Depth, 1m Open Interest (OI) Delta, & Whale Tape (`live_kalshi_tape_and_whale_flow` + `kalshi_microstructure_l2_oi_twap`):
   - Inspect `l2_book_imbalance_minus1_to_plus1` (top 5 resting YES vs NO bid levels), `oi_conviction_regime` (rising Open Interest + VWAP drift = fresh institutional conviction positions opening), `parent_hourly_strike_ladder`, and `tape_orderflow_verdict`.
   - If spot is slightly above strike (`YES`), but whales/L2 book/OI are heavily building `NO` (`STRONG_NO_WHALE_SWEEP` or `FRESH_BEARISH_NO_OI_BUILDUP`), recognize the absorption/bull-trap and flip. When L2 depth, OI buildup, and whale flow align with spot and technicals, boost conviction.

4. Enforce Strict Price & Microstructure Discipline:
   - To choose "YES", `yes_ask` should ideally be in the tradable corridor ($0.46 to $0.74) and spot should support finishing ABOVE strike.
   - To choose "NO", `no_ask` should ideally be in the tradable corridor ($0.46 to $0.74) and spot should support finishing BELOW strike.
   - {pass_instruction}

Return ONLY valid JSON matching this exact schema:
{{"direction": {direction_schema}, "confidence": 50-95, "reason": "concise 1-sentence synthesis of why decision was chosen"}}"""



    gen_config = {

        "temperature": 0.1,

        "maxOutputTokens": 600,

        "responseMimeType": "application/json",

    }

    payload = {

        "contents": [{"parts": [{"text": prompt}]}],

        "generationConfig": gen_config,

    }



    env_model = os.environ.get("GEMINI_MODEL", "").strip()

    models_to_try = []

    if env_model and env_model not in ("gemini-2.5-flash", "gemini-1.5-flash"):

        models_to_try.append(env_model)

    for m in VERIFIED_GEMINI_MODELS:

        if m not in models_to_try:

            models_to_try.append(m)



    now_ts = time.time()

    for model_name in models_to_try:

        cooldown_until = _MODEL_COOLDOWN_UNTIL.get(model_name, 0.0)

        if now_ts < cooldown_until:

            continue



        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

        req_payload = dict(payload)

        req_gen_cfg = dict(gen_config)

        # Enable CoT thinking budget for Gen 3.7+ reasoning models

        if any(m in model_name for m in ("gemini-3.8", "gemini-3.7")):

            req_gen_cfg["thinkingConfig"] = {"thinkingBudget": 256}

        if "gemma" in model_name.lower():

            req_gen_cfg = {"temperature": 0.1, "maxOutputTokens": 220}

        req_payload["generationConfig"] = req_gen_cfg

        try:

            t0 = time.time()

            resp = requests.post(url, json=req_payload, timeout=8.0)

            dt = time.time() - t0

            if resp.status_code != 200:

                if resp.status_code == 429:

                    _MODEL_COOLDOWN_UNTIL[model_name] = time.time() + 900.0

                elif resp.status_code in (503, 500, 404):

                    _MODEL_COOLDOWN_UNTIL[model_name] = time.time() + 45.0

                logger.debug(f"[GeminiMaster] Model {model_name} HTTP {resp.status_code}: {resp.text[:120]}")

                continue



            raw = resp.json()

            text = (

                raw.get("candidates", [{}])[0]

                .get("content", {})

                .get("parts", [{}])[0]

                .get("text", "")

                .strip()

            )

            if "{" in text and "}" in text:

                text = text[text.find("{") : text.rfind("}") + 1]

            parsed = json.loads(text.strip())

            direction = str(parsed.get("direction", "PASS" if allow_pass else "YES")).upper().strip()

            if direction in ("ABOVE", "UP", "BUY YES"):

                direction = "YES"

            elif direction in ("BELOW", "DOWN", "BUY NO"):

                direction = "NO"

            elif not allow_pass:

                # When Every-Interval Trading is on, strictly calculate YES or NO
                ml_prob_val = float((dossier.get("local_ai_models") or {}).get("ml_ensemble_prob_above_strike_pct", 50.0) or 50.0)
                direction = "YES" if ml_prob_val >= 50.0 else "NO"

            elif direction not in ("YES", "NO", "PASS"):

                direction = "PASS"



            conf = float(parsed.get("confidence", 68.0) or 68.0)

            conf = max(50.0, min(95.0, conf))

            reason = str(parsed.get("reason", "Gemini master synthesis"))[:180]



            # ── HARD POST-DECISION QUANTITATIVE SAFEGUARDS ─────────────────────────

            spot_val = float(contract.get("current_spot_price") or 0.0)

            strike_val = float(contract.get("strike_price") or 0.0)

            deadzone_tol = float(contract.get("strike_pin_deadzone_threshold") or 0.0)

            is_outside_dz = bool(contract.get("is_outside_deadzone", True))



            ind = (dossier.get("price_action_and_indicators") or {}).get("indicators") or {}

            rsi_val = float(ind.get("rsi", 50.0) or 50.0)

            bb_pct_b = float(ind.get("bb_pct_b", 0.5) or 0.5)

            adx_val = float(ind.get("adx", 20.0) or 20.0)



            btc_lead = dossier.get("btc_lead_lag_context") or {}

            btc_imp = float(btc_lead.get("btc_15m_impulse_pct", 0.0) or 0.0) if btc_lead.get("applicable") else 0.0



            local_ai = dossier.get("local_ai_models") or {}

            ml_up = float(local_ai.get("ml_ensemble_prob_above_strike_pct", 50.0) or 50.0)

            tape_verdict = str((dossier.get("live_kalshi_tape_and_whale_flow") or {}).get("tape_orderflow_verdict", "NEUTRAL"))

            micro = dossier.get("kalshi_microstructure_l2_oi_twap") or {}

            l2_imb = float((micro.get("level2_orderbook_depth") or {}).get("l2_book_imbalance_minus1_to_plus1", 0.0) or 0.0)

            loss_warnings = dossier.get("recent_loss_regime_warnings") or []

            ob = dossier.get("kalshi_orderbook") or {}

            yes_ask_v = float(ob.get("yes_ask") or 0.0)

            yes_bid_v = float(ob.get("yes_bid") or 0.0)

            no_ask_v = float(ob.get("no_ask") or 0.0)

            no_bid_v = float(ob.get("no_bid") or 0.0)

            cats_list = [str(c) for c in (local_ai.get("detected_catalysts_and_structure") or [])]

            has_neg_ev_block = False  # EV veto removed: Gemini's call is not overridden by an EV hurdle



            if direction in ("YES", "NO") and allow_pass:

                # 0. Orderbook Bid-Ask Spread & Liquidity Veto (prevents instant stop-loss on wide/empty orderbooks like AUDUSD/GOLD)

                if direction == "YES" and yes_ask_v > 0 and (yes_bid_v < 0.15 or (yes_ask_v - yes_bid_v) > 0.12):

                    reason = (

                        f"[Illiquid Spread Veto: YES bid ${yes_bid_v:.2f} / ask ${yes_ask_v:.2f} (spread ${yes_ask_v - yes_bid_v:.2f} > $0.12 max)] {reason}"

                    )[:220]

                    direction = "PASS"

                elif direction == "NO" and no_ask_v > 0 and (no_bid_v < 0.15 or (no_ask_v - no_bid_v) > 0.12):

                    reason = (

                        f"[Illiquid Spread Veto: NO bid ${no_bid_v:.2f} / ask ${no_ask_v:.2f} (spread ${no_ask_v - no_bid_v:.2f} > $0.12 max)] {reason}"

                    )[:220]

                    direction = "PASS"

                # 0b. Negative EV Block Veto (respects local ML/Ask negative EV block unless extreme >=85% conviction)

                elif has_neg_ev_block and conf < 85.0:

                    reason = f"[Negative EV Veto: local ML probability fails ask + 5% fee hurdle] {reason}"[:220]

                    direction = "PASS"

                # 1. Strike-Pin Deadzone Veto (prevents 50/50 coin-flip entries within $15 BTC / $1.10 ETH of strike)

                elif not is_outside_dz and strike_val > 0 and spot_val > 0:

                    reason = (

                        f"[Deadzone Veto: |spot-strike|=${abs(spot_val - strike_val):.4f} <= ${deadzone_tol:.4f}] {reason}"

                    )[:220]

                    direction = "PASS"

                # 2. Physical Spot-vs-Strike Alignment Veto (prevents buying YES below strike or NO above strike)

                elif direction == "YES" and spot_val < strike_val and strike_val > 0:

                    reason = (

                        f"[Spot-Strike Alignment Veto: YES blocked while spot ${spot_val:.2f} < strike ${strike_val:.2f}] {reason}"

                    )[:220]

                    direction = "PASS"

                elif direction == "NO" and spot_val > strike_val and strike_val > 0:

                    reason = (

                        f"[Spot-Strike Alignment Veto: NO blocked while spot ${spot_val:.2f} > strike ${strike_val:.2f}] {reason}"

                    )[:220]

                    direction = "PASS"

                # 3. Minimum Confidence Floor (>= 74.0% where live WR is 85.7% vs 14.3% below 72%)

                elif conf < MIN_GEMINI_MASTER_CONFIDENCE:

                    reason = (

                        f"[Low-Conviction Veto: {conf:.0f}% < {MIN_GEMINI_MASTER_CONFIDENCE:.0f}% required floor] {reason}"

                    )[:220]

                    direction = "PASS"

                # 4. Mean-Reversion Exhaustion Veto (prevents buying NO at oversold bottom or YES at overbought top in low-ADX chop)

                elif direction == "NO" and rsi_val < 34.0 and bb_pct_b < 0.12 and adx_val < 28.0:

                    reason = (

                        f"[Oversold Exhaustion Veto: NO blocked at RSI={rsi_val:.1f}, BB%B={bb_pct_b:.2f}, ADX={adx_val:.1f}] {reason}"

                    )[:220]

                    direction = "PASS"

                elif direction == "YES" and rsi_val > 66.0 and bb_pct_b > 0.88 and adx_val < 28.0 and not (c_ema9 > c_ema21 and adx_val >= 28.0):

                    reason = (

                        f"[Overbought Exhaustion Veto: YES blocked at RSI={rsi_val:.1f}, BB%B={bb_pct_b:.2f}, ADX={adx_val:.1f}] {reason}"

                    )[:220]

                    direction = "PASS"

                # 5. Cross-Asset BTC Lead-Lag Veto (prevents altcoin trades fighting a strong >= 0.18% BTC 15m impulse)

                elif direction == "YES" and btc_lead.get("applicable") and btc_imp <= -0.18:

                    reason = (

                        f"[BTC Lead-Lag Veto: {asset} YES blocked against BTC {btc_imp:+.2f}% 15m dump] {reason}"

                    )[:220]

                    direction = "PASS"

                elif direction == "NO" and btc_lead.get("applicable") and btc_imp >= 0.18:

                    reason = (

                        f"[BTC Lead-Lag Veto: {asset} NO blocked against BTC {btc_imp:+.2f}% 15m surge] {reason}"

                    )[:220]

                    direction = "PASS"

                # 6. Closed-Loop Loss Memory Veto (enforces active LossAnalyzer regime vetoes)

                else:

                    for lw in loss_warnings:

                        v_side = str(lw.get("blocked_side", "")).upper()

                        r_thresh = float(lw.get("rsi_threshold", 50.0) or 50.0)

                        if v_side == "NO" and direction == "NO" and rsi_val < r_thresh:

                            reason = f"[{lw.get('reason', 'Loss Guard Veto')}] {reason}"[:220]

                            direction = "PASS"

                            break

                        if v_side == "YES" and direction == "YES" and rsi_val > r_thresh:

                            if adx_val >= 28.0 and c_ema9 > c_ema21:

                                # High momentum continuation: do not veto bullish entry on overbought RSI

                                logger.info(f"[GeminiMaster] Overbought Loss Guard Veto bypassed: explosive trend active (ADX={adx_val:.1f} >= 28, EMA9 > EMA21).")

                            else:

                                reason = f"[{lw.get('reason', 'Loss Guard Veto')}] {reason}"[:220]

                                direction = "PASS"

                                break



                # 7. Borderline Conviction (74-78%) Multi-Model Confluence Gate

                if direction in ("YES", "NO") and 74.0 <= conf < 79.0:

                    if direction == "YES":

                        has_ml_support = ml_up >= 51.5

                        has_flow_support = l2_imb >= 0.08 or "YES" in tape_verdict

                        if not (has_ml_support or has_flow_support):

                            reason = (

                                f"[Borderline Confluence Veto: {conf:.0f}% YES lacks ML ({ml_up:.1f}%) & L2/tape ({l2_imb:+.2f}/{tape_verdict}) support] {reason}"

                            )[:220]

                            direction = "PASS"

                    elif direction == "NO":

                        has_ml_support = ml_up <= 48.5

                        has_flow_support = l2_imb <= -0.08 or "NO" in tape_verdict

                        if not (has_ml_support or has_flow_support):

                            reason = (

                                f"[Borderline Confluence Veto: {conf:.0f}% NO lacks ML ({100.0 - ml_up:.1f}% down) & L2/tape ({l2_imb:+.2f}/{tape_verdict}) support] {reason}"

                            )[:220]

                            direction = "PASS"



            result = {

                "direction": direction,

                "decision": "APPROVE" if direction in ("YES", "NO") else "VETO",

                "confidence": conf,

                "reason": reason,

                "model": model_name,

                "latency_s": round(dt, 2),

                "timestamp": time.time(),

            }

            logger.info(

                f"[GeminiMaster] 🧠 {asset} {ticker} -> Direction={direction} "

                f"(conf={conf:.0f}%) via {model_name} in {dt:.2f}s | {reason}"

            )

            return result

        except Exception as e:

            logger.debug(f"[GeminiMaster] Model {model_name} error: {e}")

            continue



    if not allow_pass:
        ml_prob_val = float((dossier.get("local_ai_models") or {}).get("ml_ensemble_prob_above_strike_pct", 50.0) or 50.0)
        fb_direction = "YES" if ml_prob_val >= 50.0 else "NO"
        logger.warning(
            f"[GeminiMaster] ⚠️ All Gemini LLM endpoints unreachable for {asset} {ticker}; "
            f"every-interval mode calculating {fb_direction} via ML baseline."
        )
        return {
            "direction": fb_direction,
            "decision": "APPROVE",
            "confidence": 50.0,
            "reason": f"Gemini LLM unreachable/rate-limited — every-interval resolution ({fb_direction})",
            "model": "llm_unavailable_every_interval_fallback",
            "fallback": False,
            "latency_s": 0.0,
            "timestamp": time.time(),
        }

    logger.warning(

        f"[GeminiMaster] ⚠️ All Gemini LLM endpoints unreachable for {asset} {ticker}; "

        f"fail-safeing to PASS (capital preservation)."

    )

    return {

        "direction": "PASS",

        "decision": "VETO",

        "confidence": 50.0,

        "reason": "Gemini LLM unreachable/rate-limited — fail-safe PASS (synthetic fallback trades disabled)",

        "model": "llm_unavailable_failsafe",

        "fallback": False,

        "latency_s": 0.0,

        "timestamp": time.time(),

    }





def _get_key_lock(cache_key: tuple) -> threading.Lock:

    with _CACHE_LOCK:

        lk = _KEY_LOCKS.get(cache_key)

        if lk is None:

            lk = threading.Lock()

            _KEY_LOCKS[cache_key] = lk

            if len(_KEY_LOCKS) > 300:

                for old_k in list(_KEY_LOCKS.keys())[:100]:

                    if old_k != cache_key:

                        _KEY_LOCKS.pop(old_k, None)

        return lk





def _is_cached_decision_valid(cached: Optional[Dict[str, Any]], sec_elapsed: float) -> bool:

    if cached is None:

        return False

    age = time.time() - float(cached.get("timestamp", 0.0) or 0.0)

    if cached.get("model") in ("local_fallback", "llm_unavailable_failsafe") or cached.get("fallback"):

        return age <= 25.0

    # A directional YES/NO decision prefetched during the opening window expires after MAX_DECISION_AGE_SEC

    # or once the opening entry window (195s) has closed so stale T+35s calls never execute at T+8m.

    if str(cached.get("direction", "PASS")).upper() in ("YES", "NO"):

        if age > MAX_DECISION_AGE_SEC or sec_elapsed > 195.0:

            return False

    return True





def _with_panel(res: Dict[str, Any], dossier: Dict[str, Any], asset: str, interval_id: str) -> Dict[str, Any]:
    """Attach the dashboard card's dossier summary to a decision and log the call."""
    try:
        from backend.btc.gemini_panel import panel_summary, record_call
        res = dict(res)
        res["panel"] = panel_summary(dossier)
        record_call(asset, interval_id, res.get("direction"), res.get("confidence"))
    except Exception as e:
        logger.debug(f"[Gemini15mGate] panel summary skipped: {e}")
    return res


def prefetch_master_decision_async(

    asset: str,

    interval_id: str,

    strike: float,

    spot: float,

    sec_elapsed: float,

    active_m: Dict[str, Any],

    forecast: Dict[str, Any],

    df_ind: Any,
    allow_pass: bool = True,
) -> None:
    """
    Prefetches Gemini's authoritative YES/NO/PASS decision in a background thread
    during the 35s-65s opening window so it is ready at T+65s with 0ms latency.
    When allow_pass is False, mandates a binary YES/NO decision.
    """
    if sec_elapsed > 195.0 and allow_pass:
        return

    cache_key = (str(asset).upper(), str(interval_id), bool(allow_pass))
    with _CACHE_LOCK:
        cached = _MASTER_CACHE.get(cache_key)
        if _is_cached_decision_valid(cached, sec_elapsed) or cache_key in _MASTER_INFLIGHT:
            return
        _MASTER_INFLIGHT.add(cache_key)

    def _worker():
        key_lock = _get_key_lock(cache_key)
        with key_lock:
            try:
                with _CACHE_LOCK:
                    cached_now = _MASTER_CACHE.get(cache_key)
                    if _is_cached_decision_valid(cached_now, sec_elapsed):
                        return
                dossier = _build_intelligence_dossier(
                    asset=asset,
                    interval_id=interval_id,
                    strike=strike,
                    spot=spot,
                    sec_elapsed=sec_elapsed,
                    active_m=active_m,
                    forecast=forecast,
                    df_ind=df_ind,
                )
                try:
                    from backend.btc.dual_model_debate import run_dual_model_debate
                    from backend.btc.chart_snapshot_renderer import render_gemini_chart_snapshot
                    chart_snap = render_gemini_chart_snapshot(
                        asset=asset, ticker=interval_id, strike=strike, spot=spot,
                        sec_elapsed=sec_elapsed, df_15m=df_ind
                    )
                    api_key = get_gemini_api_key()
                    debate_res = run_dual_model_debate(dossier, api_key=api_key, allow_pass=allow_pass, chart_snapshot=chart_snap)
                    res = {
                        "direction": debate_res.get("consensus_direction", "PASS" if allow_pass else "YES"),
                        "decision": "EXECUTE" if debate_res.get("consensus_direction") in ("YES", "NO") else "VETO",
                        "confidence": float(debate_res.get("confidence", 50.0)),
                        "reason": str(debate_res.get("combined_reasoning", "")),
                        "model": str(debate_res.get("model_pair", "gemini-3.8-flash")),
                        "is_unanimous": bool(debate_res.get("is_unanimous", True)),
                        "primary_call": debate_res.get("primary_call"),
                        "auditor_call": debate_res.get("auditor_call"),
                        "debate_status": debate_res.get("debate_status"),
                        "latency_s": 0.0,
                        "timestamp": time.time(),
                    }
                except Exception as e:
                    logger.debug(f"[Gemini15mGate] Dual model debate worker fallback: {e}")
                    res = _call_gemini_master_decision(dossier, allow_pass=allow_pass)
                res = _with_panel(res, dossier, asset, interval_id)

                with _CACHE_LOCK:
                    _MASTER_CACHE[cache_key] = res
                    if len(_MASTER_CACHE) > 200:
                        oldest = sorted(_MASTER_CACHE.items(), key=lambda x: x[1].get("timestamp", 0))[:50]
                        for k, _ in oldest:
                            _MASTER_CACHE.pop(k, None)
            finally:
                with _CACHE_LOCK:
                    _MASTER_INFLIGHT.discard(cache_key)



    t = threading.Thread(target=_worker, daemon=True, name=f"GeminiMaster-{asset}")

    t.start()





def get_or_create_master_decision(

    asset: str,

    interval_id: str,

    strike: float,

    spot: float,

    sec_elapsed: float,

    active_m: Dict[str, Any],

    forecast: Dict[str, Any],

    df_ind: Any,

    sync_if_missing: bool = True,

    allow_pass: bool = True,

) -> Optional[Dict[str, Any]]:

    """

    Returns Gemini's cached Master Decision ("YES", "NO", or "PASS") for (asset, interval_id).

    Enforces strict opening-window freshness so stale T+35s prefetches never execute late in the candle.

    When allow_pass is False (Every-Interval Force Mode), mandates a binary YES/NO decision.

    """

    if "ADV-" in str(interval_id) or "TEST" in str(interval_id) or str(interval_id).endswith("_SYNTH") or (active_m and active_m.get("is_synthetic")):

        return None

    if sec_elapsed > 195.0 and allow_pass:

        return {

            "direction": "PASS",

            "decision": "VETO",

            "confidence": 50.0,

            "reason": f"Late-candle entry cutoff active ({sec_elapsed:.0f}s elapsed > 195s opening window limit)",

            "model": "opening_window_guard",

            "latency_s": 0.0,

            "timestamp": time.time(),

        }



    cache_key = (str(asset).upper(), str(interval_id), bool(allow_pass))

    with _CACHE_LOCK:

        cached = _MASTER_CACHE.get(cache_key)

        if _is_cached_decision_valid(cached, sec_elapsed):

            return cached



    if not sync_if_missing:
        prefetch_master_decision_async(
            asset, interval_id, strike, spot, sec_elapsed, active_m, forecast, df_ind, allow_pass=allow_pass
        )
        return None



    key_lock = _get_key_lock(cache_key)

    with key_lock:

        with _CACHE_LOCK:

            cached = _MASTER_CACHE.get(cache_key)

            if _is_cached_decision_valid(cached, sec_elapsed):

                return cached



        dossier = _build_intelligence_dossier(

            asset=asset,

            interval_id=interval_id,

            strike=strike,

            spot=spot,

            sec_elapsed=sec_elapsed,

            active_m=active_m,

            forecast=forecast,

            df_ind=df_ind,

        )

        try:
            from backend.btc.dual_model_debate import run_dual_model_debate
            from backend.btc.chart_snapshot_renderer import render_gemini_chart_snapshot
            chart_snap = render_gemini_chart_snapshot(
                asset=asset, ticker=interval_id, strike=strike, spot=spot,
                sec_elapsed=sec_elapsed, df_15m=df_ind
            )
            api_key = get_gemini_api_key()
            debate_res = run_dual_model_debate(dossier, api_key=api_key, allow_pass=allow_pass, chart_snapshot=chart_snap)
            res = {
                "direction": debate_res.get("consensus_direction", "PASS"),
                "decision": "EXECUTE" if debate_res.get("consensus_direction") in ("YES", "NO") else "VETO",
                "confidence": float(debate_res.get("confidence", 50.0)),
                "reason": str(debate_res.get("combined_reasoning", "")),
                "model": str(debate_res.get("model_pair", "gemini-3.8-flash")),
                "is_unanimous": bool(debate_res.get("is_unanimous", True)),
                "primary_call": debate_res.get("primary_call"),
                "auditor_call": debate_res.get("auditor_call"),
                "debate_status": debate_res.get("debate_status"),
                "latency_s": 0.0,
                "timestamp": time.time(),
            }
        except Exception as e:
            logger.debug(f"[Gemini15mGate] Dual model debate sync fallback: {e}")
            res = _call_gemini_master_decision(dossier, allow_pass=allow_pass)
        res = _with_panel(res, dossier, asset, interval_id)

        with _CACHE_LOCK:

            _MASTER_CACHE[cache_key] = res

        return res



def prefetch_transition_verdict_async(

    asset: str,

    interval_id: str,

    side: str,

    strike: float,

    spot: float,

    sec_elapsed: float,

    model_prob: float,

    ask_price: float,

    df_ind: Any,

) -> None:

    active_m = {"yes_ask": ask_price if str(side).upper() == "YES" else 1.0 - ask_price,

                "no_ask": ask_price if str(side).upper() == "NO" else 1.0 - ask_price}

    forecast = {"direction": str(side).upper(), "probability_percent": model_prob, "ml_prob": model_prob / 100.0 if str(side).upper() == "YES" else 1.0 - (model_prob / 100.0)}

    prefetch_master_decision_async(asset, interval_id, strike, spot, sec_elapsed, active_m, forecast, df_ind)





def evaluate_or_get_cached_verdict(

    asset: str,

    interval_id: str,

    side: str,

    strike: float,

    spot: float,

    sec_elapsed: float,

    model_prob: float,

    ask_price: float,

    df_ind: Any,

    sync_if_missing: bool = True,

) -> Optional[Dict[str, Any]]:

    active_m = {"yes_ask": ask_price if str(side).upper() == "YES" else 1.0 - ask_price,

                "no_ask": ask_price if str(side).upper() == "NO" else 1.0 - ask_price}

    forecast = {"direction": str(side).upper(), "probability_percent": model_prob, "ml_prob": model_prob / 100.0 if str(side).upper() == "YES" else 1.0 - (model_prob / 100.0)}

    res = get_or_create_master_decision(

        asset, interval_id, strike, spot, sec_elapsed, active_m, forecast, df_ind, sync_if_missing=sync_if_missing

    )

    if not res:

        return None

    chosen = res.get("direction", "PASS")

    side_up = str(side).upper()

    return {

        "decision": "APPROVE" if chosen == side_up else "VETO",

        "direction": chosen,

        "confidence": res.get("confidence", 68.0),

        "reason": res.get("reason", ""),

        "model": res.get("model", ""),

        "latency_s": res.get("latency_s", 0.0),

        "timestamp": res.get("timestamp", time.time()),

    }

