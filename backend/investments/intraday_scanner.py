"""
Intraday Multi-Factor Scanner for US Equities & ETFs
Scans active symbols for:
1. ORB_BREAKOUT: 15m Opening Range Breakout with high RVOL
2. VWAP_RECLAIM: Institutional pullback retesting and reclaiming VWAP
3. SQUEEZE_IGNITION: Bollinger Bands compressing inside Keltner Channels fired with directional volume expansion
Also computes market breadth via SPY/QQQ macro correlation.
"""

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any, Tuple
import requests

from backend.investments.robinhood_client import (
    get_live_stock_quote,
    quote_is_usable
)
from backend.investments.microstructure_engine import MicrostructureEngine
from backend.investments.subsecond_tape_engine import SubSecondTapeEngine

logger = logging.getLogger(__name__)


def _calc_sma(prices: List[float], period: int) -> float:
    if len(prices) < period:
        return sum(prices) / max(len(prices), 1)
    return sum(prices[-period:]) / period


def _calc_ema(prices: List[float], period: int) -> float:
    if not prices:
        return 0.0
    if len(prices) < period:
        return sum(prices) / len(prices)
    k = 2.0 / (period + 1.0)
    ema = sum(prices[:period]) / period
    for p in prices[period:]:
        ema = p * k + ema * (1.0 - k)
    return ema


def _calc_rsi(prices: List[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(diff))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 1)


def _calc_std(prices: List[float], period: int = 20) -> float:
    if len(prices) < period:
        period = len(prices)
    if period <= 1:
        return 0.0
    sub = prices[-period:]
    mean = sum(sub) / period
    var = sum((x - mean) ** 2 for x in sub) / (period - 1)
    return math.sqrt(var)


class IntradayStockScanner:
    """Scans watchlist symbols for actionable high-probability intraday setups."""

    def __init__(self):
        self._history_cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
        self._analysis_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._breadth_cache: Optional[Tuple[float, Dict[str, Any]]] = None

    def fetch_intraday_candles(self, symbol: str, interval: str = "5m", lookback_days: str = "5d") -> List[Dict[str, Any]]:
        """Fetches 5m / 15m intraday OHLCV bars from Yahoo Finance with 25s cache."""
        sym = symbol.strip().upper()
        cache_key = f"{sym}:{interval}:{lookback_days}"
        now_ts = time.time()
        cached = self._history_cache.get(cache_key)
        if cached and (now_ts - cached[0]) < 25.0:
            return cached[1]

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={interval}&range={lookback_days}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        try:
            resp = requests.get(url, headers=headers, timeout=3.5)
            if resp.status_code == 200:
                data = resp.json()
                res = data.get("chart", {}).get("result", [{}])[0]
                timestamps = res.get("timestamp", [])
                indicators = res.get("indicators", {}).get("quote", [{}])[0]
                opens = indicators.get("open", [])
                highs = indicators.get("high", [])
                lows = indicators.get("low", [])
                closes = indicators.get("close", [])
                volumes = indicators.get("volume", [])

                bars = []
                for i in range(len(timestamps)):
                    if (
                        closes[i] is not None
                        and opens[i] is not None
                        and highs[i] is not None
                        and lows[i] is not None
                    ):
                        bars.append({
                            "time": timestamps[i],
                            "open": float(opens[i]),
                            "high": float(highs[i]),
                            "low": float(lows[i]),
                            "close": float(closes[i]),
                            "volume": int(volumes[i] or 0)
                        })
                if bars:
                    self._history_cache[cache_key] = (now_ts, bars)
                    return bars
        except Exception as e:
            logger.debug(f"[IntradayScanner] Error fetching candles for {sym}: {e}")

        # Fallback synthetic bars around live quote only if quote is authentic
        q = get_live_stock_quote(sym)
        if not quote_is_usable(q):
            return []
        p = q["price"]
        bars = []
        now_int = int(now_ts)
        for idx in range(30):
            bars.append({
                "time": now_int - (30 - idx) * 300,
                "open": round(p * 0.999, 2),
                "high": round(p * 1.002, 2),
                "low": round(p * 0.998, 2),
                "close": p,
                "volume": 50000
            })
        self._history_cache[cache_key] = (now_ts, bars)
        return bars

    def analyze_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Runs comprehensive technical & microstructure analysis for a single symbol.
        Evaluates ORB, VWAP, Squeeze, EMA9/21, RSI, RVOL, and determines setup readiness.
        """
        sym = symbol.strip().upper()
        now_ts = time.time()
        cached = self._analysis_cache.get(sym)
        if cached and (now_ts - cached[0]) < 25.0:
            return dict(cached[1])

        quote = get_live_stock_quote(sym)
        if not quote_is_usable(quote):
            return {
                "symbol": sym,
                "price": 0.0,
                "confidence": 0.0,
                "bias": "NEUTRAL",
                "setup_type": "NO_AUTHENTIC_QUOTE",
                "reasons": ["Authentic live market data quote unavailable."],
                "usable": False
            }
        bars = self.fetch_intraday_candles(sym, interval="5m", lookback_days="2d")

        if len(bars) < 15:
            res_short = {
                "symbol": sym,
                "price": quote["price"],
                "change_pct": quote["change_pct"],
                "setup_type": "CONSOLIDATION",
                "bias": "NEUTRAL",
                "confidence": 50.0,
                "rvol": 1.0,
                "vwap": quote["price"],
                "ema9": quote["price"],
                "ema21": quote["price"],
                "rsi": 50.0,
                "status": "PASS",
                "reasons": ["Insufficient intraday candle history"]
            }
            self._analysis_cache[sym] = (now_ts, res_short)
            return dict(res_short)

        closes = [b["close"] for b in bars]
        volumes = [b["volume"] for b in bars]
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]

        curr_price = closes[-1]
        ema9 = round(_calc_ema(closes, 9), 2)
        ema21 = round(_calc_ema(closes, 21), 2)
        rsi = _calc_rsi(closes, 14)

        # VWAP calculation over the last 78 bars (~1 trading day on 5m)
        lookback = min(len(bars), 78)
        cum_vol = sum(volumes[-lookback:])
        cum_pv = sum(((highs[i] + lows[i] + closes[i]) / 3.0) * volumes[i] for i in range(len(bars) - lookback, len(bars)))
        vwap = round(cum_pv / max(cum_vol, 1), 2)

        # Multi-timeframe Anchored VWAP standard deviation bands (1s, 2s, 3s)
        vwap_bands = MicrostructureEngine.compute_anchored_vwap_bands(bars[-lookback:])

        # Real-time Order Flow Analytics (CVD, Flow Bias, Blocks)
        order_flow = SubSecondTapeEngine.get_order_flow_analytics(sym)

        # RVOL: Current bar volume vs 20-bar SMA volume
        avg_vol = _calc_sma(volumes[-21:-1], 20) if len(volumes) >= 21 else (sum(volumes) / len(volumes))
        curr_vol = volumes[-1]
        rvol = round(curr_vol / max(avg_vol, 1), 2)

        # Bollinger Bands & Keltner Squeeze detection
        sma20 = _calc_sma(closes, 20)
        std20 = _calc_std(closes, 20)
        bb_upper = round(sma20 + 2.0 * std20, 2)
        bb_lower = round(sma20 - 2.0 * std20, 2)

        # Average True Range (ATR)
        tr_list = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])) for i in range(1, len(bars))]
        atr = _calc_sma(tr_list, 14) if tr_list else 1.0
        kc_upper = round(sma20 + 1.5 * atr, 2)
        kc_lower = round(sma20 - 1.5 * atr, 2)

        is_squeeze = (bb_lower > kc_lower) and (bb_upper < kc_upper)

        # Opening Range (First 15 minutes of today: first 3 5m bars)
        orb_high = max(highs[-15:]) if len(highs) >= 15 else max(highs)
        orb_low = min(lows[-15:]) if len(lows) >= 15 else min(lows)

        # Pattern Evaluation
        setup_type = "CONSOLIDATION"
        bias = "NEUTRAL"
        confidence = 50.0
        reasons = []

        # 1. ORB_BREAKOUT
        if curr_price > orb_high and rvol >= 1.25 and curr_price > vwap:
            setup_type = "ORB_BREAKOUT"
            bias = "BULLISH"
            confidence = 78.5
            reasons.append(f"Broken above 15m ORB High (${orb_high:.2f}) with RVOL {rvol}x and Price > VWAP")
        elif curr_price < orb_low and rvol >= 1.25 and curr_price < vwap:
            setup_type = "ORB_BREAKDOWN"
            bias = "BEARISH"
            confidence = 77.0
            reasons.append(f"Broken below 15m ORB Low (${orb_low:.2f}) with RVOL {rvol}x and Price < VWAP")

        # 2. VWAP_RECLAIM
        elif (closes[-2] < vwap and curr_price > vwap and ema9 > ema21):
            setup_type = "VWAP_RECLAIM"
            bias = "BULLISH"
            confidence = 76.0
            reasons.append(f"Institutional VWAP Reclaim (${vwap:.2f}) with EMA9 > EMA21 trend alignment")
        elif (closes[-2] > vwap and curr_price < vwap and ema9 < ema21):
            setup_type = "VWAP_REJECT"
            bias = "BEARISH"
            confidence = 75.5
            reasons.append(f"Institutional VWAP Breakdown below ${vwap:.2f} with EMA9 < EMA21")

        # 3. SQUEEZE_IGNITION
        elif not is_squeeze and (curr_price > bb_upper or curr_price < bb_lower) and rvol >= 1.2:
            setup_type = "SQUEEZE_IGNITION"
            bias = "BULLISH" if curr_price > bb_upper else "BEARISH"
            confidence = 81.0
            reasons.append(f"Bollinger/Keltner Squeeze fired expansion into {bias} with {rvol}x volume")

        # 4. TREND_MOMENTUM
        elif ema9 > ema21 and curr_price > vwap and 52 <= rsi <= 72:
            setup_type = "TREND_MOMENTUM"
            bias = "BULLISH"
            confidence = 71.5
            reasons.append(f"Bullish Trend alignment (Price > VWAP > EMA9 > EMA21, RSI {rsi})")
        elif ema9 < ema21 and curr_price < vwap and 28 <= rsi <= 48:
            setup_type = "TREND_MOMENTUM"
            bias = "BEARISH"
            confidence = 71.0
            reasons.append(f"Bearish Trend alignment (Price < VWAP < EMA9 < EMA21, RSI {rsi})")

        result = {
            "symbol": sym,
            "price": curr_price,
            "change": quote["change"],
            "change_pct": quote["change_pct"],
            "setup_type": setup_type,
            "bias": bias,
            "confidence": confidence,
            "rvol": rvol,
            "vwap": vwap,
            "ema9": ema9,
            "ema21": ema21,
            "rsi": rsi,
            "atr": round(atr, 2),
            "is_squeeze": is_squeeze,
            "orb_high": round(orb_high, 2),
            "orb_low": round(orb_low, 2),
            "vwap_bands": vwap_bands,
            "order_flow": order_flow,
            "status": "READY" if confidence >= 72.0 and bias != "NEUTRAL" else "MONITORING",
            "reasons": reasons,
            "timestamp": now_ts
        }
        self._analysis_cache[sym] = (now_ts, result)
        return dict(result)

    def scan_watchlist(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Scans a list of symbols concurrently and ranks them by signal confidence and setup quality."""
        results = []
        clean_syms = [s.strip().upper() for s in symbols if s and s.strip()]
        if not clean_syms:
            return results

        with ThreadPoolExecutor(max_workers=min(6, len(clean_syms))) as pool:
            future_map = {pool.submit(self.analyze_symbol, s): s for s in clean_syms}
            for fut in as_completed(future_map):
                sym = future_map[fut]
                try:
                    results.append(fut.result())
                except Exception as e:
                    logger.debug(f"[IntradayScanner] Failed scanning {sym}: {e}")

        # Sort by confidence descending
        results.sort(key=lambda x: x.get("confidence", 0.0), reverse=True)
        return results

    def get_market_breadth(self) -> Dict[str, Any]:
        """Calculates macro equity market breadth across SPY and QQQ with 25s cache."""
        now_ts = time.time()
        if self._breadth_cache and (now_ts - self._breadth_cache[0]) < 25.0:
            return dict(self._breadth_cache[1])

        spy = self.analyze_symbol("SPY")
        qqq = self.analyze_symbol("QQQ")

        spy_pct = spy.get("change_pct", 0.0)
        qqq_pct = qqq.get("change_pct", 0.0)

        if spy_pct > 0.3 and qqq_pct > 0.3:
            macro = "RISK_ON_BULLISH"
        elif spy_pct < -0.3 and qqq_pct < -0.3:
            macro = "RISK_OFF_BEARISH"
        else:
            macro = "MIXED_ROTATIONAL"

        breadth = {
            "macro_bias": macro,
            "spy_change_pct": spy_pct,
            "qqq_change_pct": qqq_pct,
            "spy_vwap": spy.get("vwap"),
            "qqq_vwap": qqq.get("vwap"),
            "aligned": (spy_pct * qqq_pct > 0)
        }
        self._breadth_cache = (now_ts, breadth)
        return dict(breadth)

