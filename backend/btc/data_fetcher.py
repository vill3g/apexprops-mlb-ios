"""
Bitcoin Multi-Timeframe Data Fetcher
Fetches live and historical OHLCV candles (1m, 5m, 15m, 1h, 4h, 1d) and ticker stats for BTC.
Includes fallback logic across Coinbase, Kraken, Binance.US, and Yahoo Finance.

NOTE (Basis Risk): TA indicators and ML inference consume spot BTC-USD feeds (primarily Coinbase/Kraken).
Kalshi KXBTC15M contracts settle against the CF Benchmarks BRTI index. See README.md Safety Notice.
"""

import logging
import os
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from typing import Optional, Dict, Any, Union
from urllib3.util import Retry

logger = logging.getLogger(__name__)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

_HTTP_SESSION = requests.Session()
_adapter = HTTPAdapter(pool_connections=20, pool_maxsize=50, max_retries=Retry(total=2, backoff_factor=0.2))
_HTTP_SESSION.mount("https://", _adapter)
_HTTP_SESSION.mount("http://", _adapter)
_HTTP_SESSION.headers.update(HEADERS)

try:
    from .kalshi_client import get_kalshi_15m_market
except ImportError:
    from kalshi_client import get_kalshi_15m_market

try:
    from .trend_boxes import compute_last_5_targets, compute_streak_summary
except ImportError:
    from trend_boxes import compute_last_5_targets, compute_streak_summary


# Granularity mappings
TIMEFRAMES = {
    "1m": {"seconds": 60, "coinbase": 60, "kraken": 1, "binance": "1m", "yf": "1m"},
    "5m": {"seconds": 300, "coinbase": 300, "kraken": 5, "binance": "5m", "yf": "5m"},
    "15m": {"seconds": 900, "coinbase": 900, "kraken": 15, "binance": "15m", "yf": "15m"},
    "1h": {"seconds": 3600, "coinbase": 3600, "kraken": 60, "binance": "1h", "yf": "1h"},
    "4h": {"seconds": 14400, "coinbase": 3600, "kraken": 240, "binance": "4h", "yf": "1h"},
    "1d": {"seconds": 86400, "coinbase": 86400, "kraken": 1440, "binance": "1d", "yf": "1d"},
}


def _aggregate_to_4h(df_1h: pd.DataFrame) -> pd.DataFrame:
    """Aggregate 1h candles into 4h candles."""
    if df_1h.empty:
        return df_1h
    df = df_1h.copy()
    # Group by 4-hour epoch blocks (14400 seconds)
    df["group"] = df["time"] // 14400
    agg = df.groupby("group").agg({
        "time": "first",
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).reset_index(drop=True)
    return agg.sort_values("time").reset_index(drop=True)


def _fetch_from_coinbase(timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:
    """Fetch candles from Coinbase Exchange API."""
    cfg = TIMEFRAMES.get(timeframe, TIMEFRAMES["15m"])
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
    params = {"granularity": cfg["coinbase"]}
    resp = _HTTP_SESSION.get(url, params=params, timeout=3)
    resp.raise_for_status()
    raw = resp.json()
    if not isinstance(raw, list) or len(raw) == 0:
        raise ValueError("Invalid Coinbase response")

    records = []
    for row in raw:
        records.append({
            "time": int(row[0]),
            "open": float(row[3]),
            "high": float(row[2]),
            "low": float(row[1]),
            "close": float(row[4]),
            "volume": float(row[5])
        })
    df = pd.DataFrame(records).sort_values("time").reset_index(drop=True)

    if timeframe == "4h":
        df = _aggregate_to_4h(df)

    return df


def _fetch_from_kraken(timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:
    """Fallback fetch from Kraken API."""
    cfg = TIMEFRAMES.get(timeframe, TIMEFRAMES["15m"])
    url = "https://api.kraken.com/0/public/OHLC"
    params = {"pair": "XBTUSD", "interval": cfg["kraken"]}
    resp = _HTTP_SESSION.get(url, params=params, timeout=3)
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        raise ValueError(f"Kraken error: {data['error']}")
    
    result = data.get("result", {})
    pair_key = next((k for k in result.keys() if k != "last"), None)
    if not pair_key:
        raise ValueError("No pair found in Kraken result")
    
    raw = result[pair_key][-limit:]
    records = []
    for row in raw:
        records.append({
            "time": int(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[6])
        })
    df = pd.DataFrame(records).sort_values("time").reset_index(drop=True)
    return df.tail(limit).reset_index(drop=True)


def _fetch_from_binance_us(timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:
    """Fallback fetch from Binance.US API."""
    cfg = TIMEFRAMES.get(timeframe, TIMEFRAMES["15m"])
    url = "https://api.binance.us/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": cfg["binance"], "limit": min(limit, 500)}
    resp = _HTTP_SESSION.get(url, params=params, timeout=3)
    resp.raise_for_status()
    raw = resp.json()
    if not isinstance(raw, list) or len(raw) == 0:
        raise ValueError("Invalid Binance.US response")
    
    records = []
    for row in raw:
        records.append({
            "time": int(row[0]) // 1000,
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5])
        })
    df = pd.DataFrame(records).sort_values("time").reset_index(drop=True)
    return df.tail(limit).reset_index(drop=True)


def _fetch_from_yfinance(timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:
    """Fallback fetch from Yahoo Finance."""
    import yfinance as yf
    cfg = TIMEFRAMES.get(timeframe, TIMEFRAMES["15m"])
    period_map = {"1m": "2d", "5m": "5d", "15m": "5d", "1h": "1mo", "4h": "1mo", "1d": "1y"}
    period = period_map.get(timeframe, "5d")

    ticker = yf.Ticker("BTC-USD")
    hist = ticker.history(period=period, interval=cfg["yf"])
    if hist.empty:
        raise ValueError("yfinance returned empty data")
    
    hist = hist.reset_index()
    time_col = "Datetime" if "Datetime" in hist.columns else "Date"
    
    # Vectorized unit-safe conversion to Unix seconds
    dt_series = pd.to_datetime(hist[time_col], utc=True)
    hist["time"] = ((dt_series - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1s")).astype("int64")
    hist = hist.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    df = hist[["time", "open", "high", "low", "close", "volume"]].drop_duplicates(subset=["time"], keep="last").sort_values("time").reset_index(drop=True)
    if timeframe == "4h":
        df = _aggregate_to_4h(df)
    return df



_historical_15m_cache = None

def fetch_candles(
    asset_or_tf: str = "15m",
    *args,
    timeframe: Optional[str] = None,
    limit: Optional[int] = None,
    asset: Optional[str] = None,
    **kwargs
) -> pd.DataFrame:
    """
    Fetch OHLCV candles for any timeframe (1m, 5m, 15m, 1h, 4h, 1d) and asset
    (BTC, ETH, SOL, DOGE) with resilient multi-exchange fallback.
    """
    target_asset = "BTC"
    target_tf = "15m"
    target_limit = 300

    # Parse limit from args if given positionally
    if limit is not None:
        target_limit = int(limit)
    elif len(args) >= 2 and isinstance(args[1], (int, float)):
        target_limit = int(args[1])
    elif len(args) == 1 and isinstance(args[0], (int, float)):
        target_limit = int(args[0])

    if asset:
        target_asset = str(asset).upper()

    if timeframe:
        target_tf = str(timeframe).lower()
        if asset_or_tf and str(asset_or_tf).upper() in ["BTC", "ETH", "SOL", "DOGE", "GOLD", "EURUSD", "GBPUSD", "AUDUSD", "USDJPY"]:
            target_asset = str(asset_or_tf).upper()
    else:
        # Check positional args
        if str(asset_or_tf).upper() in ["BTC", "ETH", "SOL", "DOGE", "GOLD", "EURUSD", "GBPUSD", "AUDUSD", "USDJPY"]:
            target_asset = str(asset_or_tf).upper()
            if len(args) >= 1 and isinstance(args[0], str) and args[0].lower() in TIMEFRAMES:
                target_tf = args[0].lower()
            elif str(asset_or_tf).lower() in TIMEFRAMES:
                target_tf = str(asset_or_tf).lower()
        elif str(asset_or_tf).lower() in TIMEFRAMES:
            target_tf = str(asset_or_tf).lower()
        else:
            target_tf = "15m"

    if target_asset != "BTC":
        try:
            from backend.engine.multi_asset_fetcher import fetch_asset_candles
            df_asset = fetch_asset_candles(target_asset, target_tf, target_limit)
            if df_asset is not None and not df_asset.empty:
                return df_asset
        except Exception as e:
            logger.debug(f"[fetch_candles] multi_asset fallback for {target_asset}: {e}")

    tf = target_tf if target_tf in TIMEFRAMES else "15m"
    limit = target_limit

    fetchers = [
        ("Coinbase", lambda: _fetch_from_coinbase(tf, limit)),
        ("Kraken", lambda: _fetch_from_kraken(tf, limit)),
        ("Binance.US", lambda: _fetch_from_binance_us(tf, limit)),
        ("Yahoo Finance", lambda: _fetch_from_yfinance(tf, limit)),
    ]

    last_err = None
    for name, fetcher in fetchers:
        try:
            df = fetcher()
            min_required = min(limit, 10)
            if df is not None and len(df) >= min_required:
                import os

                import pandas as pd
                if tf == "15m":
                    global _historical_15m_cache
                    hist_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "historical_candles_btc_15m.csv")
                    if os.path.exists(hist_path):
                        try:
                            if _historical_15m_cache is None:
                                _historical_15m_cache = pd.read_csv(hist_path)
                            
                            df_combined = pd.concat([_historical_15m_cache, df], ignore_index=True)
                            df_combined.drop_duplicates(subset=["time"], keep="last", inplace=True)
                            df_combined.sort_values("time", inplace=True)
                            
                            if len(df_combined) > 20000:
                                df_combined = df_combined.tail(20000)
                            
                            _historical_15m_cache = df_combined.copy() # update cache
                            df = df_combined.tail(limit).reset_index(drop=True)
                        except Exception as hist_err:
                            pass # Just fall back to standard df if history file fails
                            
                df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
                return df.tail(limit).reset_index(drop=True)
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"All market data providers failed for timeframe {tf}. Last error: {last_err}")


# Backwards compatibility alias
def fetch_15m_candles(limit: int = 300) -> pd.DataFrame:
    return fetch_candles(timeframe="15m", limit=limit)


def fetch_1m_candles_history(days: int = 15) -> pd.DataFrame:
    """
    Paginated deep-history fetch of 1m BTCUSDT candles from Binance.US,
    used only for offline backtesting (NOT the live trading path).
    Binance klines are capped at 1000 rows per call, so we page backwards
    using `endTime` until we've covered `days` worth of 1m bars.
    Results are cached to backend/data/backtest_1m_candles_cache.json with a 12h TTL.
    """
    import json

    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)
    cache_path = os.path.join(data_dir, "backtest_1m_candles_cache.json")

    # 1. Check cache with 12-hour TTL
    cache_ttl_seconds = 12 * 3600  # 12 hours
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached_obj = json.load(f)
            cached_days = cached_obj.get("days", 0)
            cached_ts = cached_obj.get("timestamp", 0)
            records = cached_obj.get("records", [])
            if cached_days >= days and (time.time() - cached_ts) < cache_ttl_seconds and len(records) > 0:
                logger.info(f"[DataFetcher] Loading {len(records)} backtest candles from cache (saved {int((time.time() - cached_ts)/60)}m ago).")
                df_cached = pd.DataFrame(records)
                df_cached["datetime"] = pd.to_datetime(df_cached["time"], unit="s", utc=True)
                df_cached = df_cached.sort_values("time").drop_duplicates(subset=["time"]).reset_index(drop=True)
                target_candles = days * 1440
                return df_cached.tail(target_candles).reset_index(drop=True)
        except Exception as e_cache:
            logger.warning(f"[DataFetcher] Error reading backtest cache: {e_cache}")

    # 2. Paginated backward fetch from Binance.US
    target_count = max(100, int(days * 1440))
    url = "https://api.binance.us/api/v3/klines"
    all_records = []
    end_time = None

    logger.info(f"[DataFetcher] Initiating paginated fetch for {target_count} 1m candles ({days} days)...")

    while len(all_records) < target_count:
        params = {
            "symbol": "BTCUSDT",
            "interval": "1m",
            "limit": 1000,
        }
        if end_time is not None:
            params["endTime"] = int(end_time)

        try:
            resp = _HTTP_SESSION.get(url, params=params, timeout=10)
            resp.raise_for_status()
            raw = resp.json()
        except Exception as err:
            logger.warning(f"[DataFetcher] Binance.US pagination error: {err}")
            break

        if not isinstance(raw, list) or len(raw) == 0:
            logger.info("[DataFetcher] Reached earliest available Binance.US candles.")
            break

        batch_records = []
        for row in raw:
            batch_records.append({
                "time": int(row[0]) // 1000,
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5])
            })

        # Earliest open_time in this batch
        earliest_open_ms = int(raw[0][0])
        all_records.extend(batch_records)

        # Set next endTime to earliest open_time minus 1ms
        end_time = earliest_open_ms - 1

        # Gentle sleep to respect rate limits
        time.sleep(0.3)

        if len(raw) < 1000:
            # End of historical data
            break

    if not all_records:
        raise RuntimeError(f"Failed to fetch any 1m candles for {days} days backtest.")

    df = pd.DataFrame(all_records)
    df = df.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)
    df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)

    # 3. Cache result
    try:
        cache_data = {
            "days": days,
            "timestamp": time.time(),
            "count": len(df),
            "records": df[["time", "open", "high", "low", "close", "volume"]].to_dict(orient="records")
        }
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)
        logger.info(f"[DataFetcher] Cached {len(df)} candles to {cache_path}")
    except Exception as e_save:
        logger.warning(f"[DataFetcher] Could not write cache file {cache_path}: {e_save}")

    target_candles = days * 1440
    return df.tail(target_candles).reset_index(drop=True)




def fetch_15m_candles_history(days: int = 90) -> pd.DataFrame:
    """
    Paginated deep-history fetch of 15m BTCUSDT candles from Binance.US,
    used only for offline backtesting (NOT the live trading path).
    Binance klines are capped at 1000 rows per call, so we page backwards
    using `endTime` until we've covered `days` worth of 15m bars.
    Results are cached to backend/data/backtest_candles_cache.json with a 12h TTL.
    """
    import json

    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)
    cache_path = os.path.join(data_dir, "backtest_candles_cache.json")

    # 1. Check cache with 12-hour TTL
    cache_ttl_seconds = 12 * 3600  # 12 hours
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached_obj = json.load(f)
            cached_days = cached_obj.get("days", 0)
            cached_ts = cached_obj.get("timestamp", 0)
            records = cached_obj.get("records", [])
            if cached_days >= days and (time.time() - cached_ts) < cache_ttl_seconds and len(records) > 0:
                logger.info(f"[DataFetcher] Loading {len(records)} backtest candles from cache (saved {int((time.time() - cached_ts)/60)}m ago).")
                df_cached = pd.DataFrame(records)
                df_cached["datetime"] = pd.to_datetime(df_cached["time"], unit="s", utc=True)
                df_cached = df_cached.sort_values("time").drop_duplicates(subset=["time"]).reset_index(drop=True)
                target_candles = days * 96
                return df_cached.tail(target_candles).reset_index(drop=True)
        except Exception as e_cache:
            logger.warning(f"[DataFetcher] Error reading backtest cache: {e_cache}")

    # 2. Paginated backward fetch from Binance.US
    target_count = max(100, int(days * 96))
    url = "https://api.binance.us/api/v3/klines"
    all_records = []
    end_time = None

    logger.info(f"[DataFetcher] Initiating paginated fetch for {target_count} 15m candles ({days} days)...")

    while len(all_records) < target_count:
        params = {
            "symbol": "BTCUSDT",
            "interval": "15m",
            "limit": 1000,
        }
        if end_time is not None:
            params["endTime"] = int(end_time)

        try:
            resp = _HTTP_SESSION.get(url, params=params, timeout=10)
            resp.raise_for_status()
            raw = resp.json()
        except Exception as err:
            logger.warning(f"[DataFetcher] Binance.US pagination error: {err}")
            break

        if not isinstance(raw, list) or len(raw) == 0:
            logger.info("[DataFetcher] Reached earliest available Binance.US candles.")
            break

        batch_records = []
        for row in raw:
            batch_records.append({
                "time": int(row[0]) // 1000,
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5])
            })

        # Earliest open_time in this batch
        earliest_open_ms = int(raw[0][0])
        all_records.extend(batch_records)

        # Set next endTime to earliest open_time minus 1ms
        end_time = earliest_open_ms - 1

        # Gentle sleep to respect rate limits
        time.sleep(0.3)

        if len(raw) < 1000:
            # End of historical data
            break

    if not all_records:
        raise RuntimeError(f"Failed to fetch any 15m candles for {days} days backtest.")

    df = pd.DataFrame(all_records)
    df = df.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)
    df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)

    # 3. Cache result
    try:
        cache_data = {
            "days": days,
            "timestamp": time.time(),
            "count": len(df),
            "records": df[["time", "open", "high", "low", "close", "volume"]].to_dict(orient="records")
        }
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)
        logger.info(f"[DataFetcher] Cached {len(df)} candles to {cache_path}")
    except Exception as e_save:
        logger.warning(f"[DataFetcher] Could not write cache file {cache_path}: {e_save}")

    target_candles = days * 96
    return df.tail(target_candles).reset_index(drop=True)


def format_volume_series(df: pd.DataFrame) -> list[dict]:
    """Format volume bars with green/red colors for Lightweight Charts histogram."""
    if df.empty or "volume" not in df.columns:
        return []
    is_green = df["close"].astype(float) >= df["open"].astype(float)
    colors = np.where(is_green, "rgba(16, 185, 129, 0.45)", "rgba(239, 68, 68, 0.45)")
    times = df["time"].astype(int).values
    volumes = np.round(df["volume"].astype(float).values, 4)
    return [
        {"time": int(t), "value": float(v), "color": str(c)}
        for t, v, c in zip(times, volumes, colors)
    ]


import threading

# High-performance in-memory cache for ultra-fast 1-second polling
_ticker_cache = {
    "timestamp": 0.0,
    "data": None
}
_ticker_lock = threading.Lock()

_target_cache = {}
_target_lock = threading.Lock()

# Cache for Binance Futures Data (Per-Asset)
_futures_cache = {}
_futures_lock = threading.Lock()

def get_binance_futures_data(asset: str = "BTC") -> dict:
    """
    Fetches live funding rate and open interest for the given asset (BTC, ETH, SOL, DOGE).
    Uses US-accessible OKX v5 public Swap API as primary with Binance Futures fallback.
    Cached for 10 seconds per asset.
    """
    a_up = str(asset or "BTC").upper().strip()
    if a_up not in ("BTC", "ETH", "SOL", "DOGE"):
        a_up = "BTC"
    now = time.time()
    with _futures_lock:
        entry = _futures_cache.get(a_up)
        if entry and entry.get("data") is not None and (now - entry.get("timestamp", 0.0) < 10.0):
            return dict(entry["data"])

    # Primary: US-accessible OKX v5 Public Swap API
    try:
        inst = f"{a_up}-USDT-SWAP"
        fr_resp = _HTTP_SESSION.get(f"https://www.okx.com/api/v5/public/funding-rate?instId={inst}", timeout=2.0)
        oi_resp = _HTTP_SESSION.get(f"https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId={inst}", timeout=2.0)
        if fr_resp.status_code == 200 and oi_resp.status_code == 200:
            fr_list = fr_resp.json().get("data", [])
            oi_list = oi_resp.json().get("data", [])
            if fr_list and oi_list:
                funding_rate = float(fr_list[0].get("fundingRate", 0.0) or 0.0)
                open_interest = float(oi_list[0].get("oiCcy", 0.0) or oi_list[0].get("oi", 0.0) or 0.0)
                open_interest_usd = float(oi_list[0].get("oiUsd", 0.0) or 0.0)
                result = {
                    "asset": a_up,
                    "funding_rate": funding_rate,
                    "open_interest": open_interest,
                    "open_interest_usd": open_interest_usd,
                }
                with _futures_lock:
                    _futures_cache[a_up] = {"timestamp": now, "data": result}
                return result
    except Exception as e_okx:
        logger.debug(f"[DataFetcher] OKX Swap fallback for {a_up}: {e_okx}")

    # Secondary: Binance Futures
    sym = f"{a_up}USDT"
    try:
        fr_resp = _HTTP_SESSION.get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={sym}", timeout=2)
        fr_data = fr_resp.json()
        funding_rate = float(fr_data.get("lastFundingRate", 0.0))
        oi_resp = _HTTP_SESSION.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={sym}", timeout=2)
        oi_data = oi_resp.json()
        open_interest = float(oi_data.get("openInterest", 0.0))
        result = {
            "asset": a_up,
            "funding_rate": funding_rate,
            "open_interest": open_interest,
        }
        with _futures_lock:
            _futures_cache[a_up] = {"timestamp": now, "data": result}
        return result
    except Exception as e:
        logger.debug(f"[DataFetcher] Futures unavailable for {sym}: {e}")
        fallback = {"asset": a_up, "funding_rate": 0.0, "open_interest": 0.0}
        with _futures_lock:
            _futures_cache[a_up] = {"timestamp": now + 120.0, "data": fallback}
        return fallback

# Cache for Fear & Greed (Updates daily, so 1 hour cache is very safe)
_fng_cache = {
    "timestamp": 0.0,
    "data": None
}
_fng_lock = threading.Lock()

def get_fear_and_greed_index() -> dict:
    """
    Fetches the Crypto Fear & Greed Index from alternative.me.
    Cached for 1 hour to avoid rate limits since it only updates daily.
    """
    now = time.time()
    with _fng_lock:
        if _fng_cache["data"] and (now - _fng_cache["timestamp"] < 3600.0):
            return _fng_cache["data"]
            
    try:
        resp = _HTTP_SESSION.get("https://api.alternative.me/fng/?limit=1", timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            if "data" in data and len(data["data"]) > 0:
                item = data["data"][0]
                result = {
                    "value": int(item.get("value", 50)),
                    "classification": item.get("value_classification", "Neutral")
                }
                with _fng_lock:
                    _fng_cache["timestamp"] = now
                    _fng_cache["data"] = result
                return result
    except Exception as e:
        logger.debug(f"[DataFetcher] Fear & Greed API unavailable: {e}")
        fallback = {"value": 50, "classification": "Neutral"}
        with _fng_lock:
            _fng_cache["timestamp"] = now + 300.0
            _fng_cache["data"] = fallback
        return fallback


def _save_ticker_cache(result: dict, now: float):
    with _ticker_lock:
        _ticker_cache["timestamp"] = now
        _ticker_cache["data"] = result

def get_btc_ticker() -> dict:
    """
    Get live 24h ticker info. Primary source: Coinbase.
    Cached for 2.0s to support high-frequency polling.
    Falls back to Binance.US, then to this app's own recent candle data, if Coinbase is unavailable.
    """
    now = time.time()
    with _ticker_lock:
        if _ticker_cache["data"] and (now - _ticker_cache["timestamp"] < 0.95):
            return _ticker_cache["data"]
        # Temporary lock extension to prevent concurrent stampede
        _ticker_cache["timestamp"] = now + 0.4

    # Original Coinbase logic (fastest endpoint)
    try:
        url = "https://api.exchange.coinbase.com/products/BTC-USD/ticker"
        resp = _HTTP_SESSION.get(url, timeout=3)
        if resp.status_code == 200:
            tick = resp.json()
            last_price = float(tick["price"])
            vol_24h = float(tick.get("volume", 0))
            # Fetch or approximate 24h stats if older than 30s
            stats_cached = _ticker_cache.get("stats")
            if not stats_cached or (now - stats_cached.get("ts", 0) > 30):
                try:
                    s_url = "https://api.exchange.coinbase.com/products/BTC-USD/stats"
                    s_resp = _HTTP_SESSION.get(s_url, timeout=4)
                    if s_resp.status_code == 200:
                        s_data = s_resp.json()
                        stats_cached = {"open": float(s_data["open"]), "high": float(s_data["high"]), "low": float(s_data["low"]), "ts": now}
                        _ticker_cache["stats"] = stats_cached
                except Exception:
                    pass
            open_price = stats_cached["open"] if stats_cached else last_price
            high_24h = max(last_price, stats_cached["high"]) if stats_cached else last_price
            low_24h = min(last_price, stats_cached["low"]) if stats_cached else last_price
            change_24h = ((last_price - open_price) / open_price) * 100 if open_price > 0 else 0.0
            result = {
                "price": round(last_price, 2),
                "open_24h": round(open_price, 2),
                "high_24h": round(high_24h, 2),
                "low_24h": round(low_24h, 2),
                "volume_24h": round(vol_24h, 2),
                "change_24h": round(change_24h, 2),
                "source": "Coinbase",
            }
            _save_ticker_cache(result, now)
            return result
    except Exception as e:
        logger.debug(f"Data source fallback: {e}")

    # Fallback to Binance.US
    try:
        url = "https://api.binance.us/api/v3/ticker/24hr?symbol=BTCUSDT"
        resp = _HTTP_SESSION.get(url, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            result = {
                "price": round(float(data["lastPrice"]), 2),
                "open_24h": round(float(data["openPrice"]), 2),
                "high_24h": round(float(data["highPrice"]), 2),
                "low_24h": round(float(data["lowPrice"]), 2),
                "volume_24h": round(float(data["volume"]), 2),
                "change_24h": round(float(data["priceChangePercent"]), 2),
                "source": "Binance.US",
            }
            _save_ticker_cache(result, now)
            return result
    except Exception as e:
        logger.debug(f"Data source fallback: {e}")

    # Fallback to candles

    with _ticker_lock:
        if _ticker_cache["data"]:
            return _ticker_cache["data"]
    try:
        candles = fetch_candles(timeframe="15m", limit=2)
    except Exception as e:
        logger.warning(f"Ticker fallback fetch failed: {e}")
        return {"price": 0.0, "open_24h": 0.0, "high_24h": 0.0, "low_24h": 0.0, "volume_24h": 0.0, "change_24h": 0.0, "source": "NoData"}

    if candles is None or len(candles) == 0:

        return {"price": 0.0, "open_24h": 0.0, "high_24h": 0.0, "low_24h": 0.0, "volume_24h": 0.0, "change_24h": 0.0, "source": "NoData"}
    last_close = float(candles.iloc[-1]["close"])
    prev_close = float(candles.iloc[-2]["close"]) if len(candles) >= 2 else last_close
    result = {
        "price": round(last_close, 2),
        "open_24h": round(prev_close, 2),
        "high_24h": round(last_close, 2),
        "low_24h": round(last_close, 2),
        "volume_24h": round(float(candles.iloc[-1]["volume"]), 2),
        "change_24h": round(((last_close - prev_close) / max(prev_close, 1e-9)) * 100, 2),
        "source": "CandleFallback",
    }
    _save_ticker_cache(result, now)
    return result


def get_candle_countdown(timeframe: str = "15m", asset: str = "BTC") -> dict:
    """
    Returns seconds and formatted time until the current candle of the selected timeframe closes,
    calibrated to Kalshi/Exchange UTC server time and anchored to active Kalshi 15m contract close_time.
    Supports: 1m, 5m, 15m, 1h, 4h, 1d.
    """
    try:
        from .kalshi_client import get_kalshi_utc_now, sync_exchange_clock_offset, _kalshi_cache, _kalshi_cache_lock
        now = get_kalshi_utc_now()
        offset_sec = sync_exchange_clock_offset(force=False)
    except Exception:
        now = datetime.now(timezone.utc)
        offset_sec = 0.0
        _kalshi_cache = {}
        _kalshi_cache_lock = None

    now_epoch = now.timestamp()
    now_int = int(now_epoch)
    tf = (timeframe or "15m").lower()
    close_epoch = float(((now_int // 900) + 1) * 900)

    if tf == "1m":
        close_epoch = float(((now_int // 60) + 1) * 60)
        seconds_left = 60 - (now.second % 60)
        formatted = f"00:{seconds_left:02d}"
    elif tf == "5m":
        close_epoch = float(((now_int // 300) + 1) * 300)
        cur = (now.minute * 60) + now.second
        seconds_left = 300 - (cur % 300)
        formatted = f"{seconds_left // 60:02d}:{seconds_left % 60:02d}"
    elif tf == "15m":
        series_key = f"KX{str(asset or 'BTC').upper()}15M"
        kalshi_close_epoch = None
        if _kalshi_cache_lock is not None:
            with _kalshi_cache_lock:
                m_cached = _kalshi_cache.get(series_key) or _kalshi_cache.get("KXBTC15M")
                if isinstance(m_cached, dict):
                    ce_ms = m_cached.get("close_epoch_ms")
                    if ce_ms and (ce_ms / 1000.0) > now_epoch and ((ce_ms / 1000.0) - now_epoch) <= 960.0:
                        kalshi_close_epoch = float(ce_ms) / 1000.0
                    elif m_cached.get("close_time"):
                        try:
                            ct_dt = datetime.fromisoformat(str(m_cached["close_time"]).replace("Z", "+00:00"))
                            ct_ep = ct_dt.timestamp()
                            if ct_ep > now_epoch and (ct_ep - now_epoch) <= 960.0:
                                kalshi_close_epoch = ct_ep
                        except Exception:
                            pass
        if kalshi_close_epoch is not None:
            close_epoch = kalshi_close_epoch
            seconds_left = max(0, int(close_epoch - now_int))
        else:
            close_epoch = float(((now_int // 900) + 1) * 900)
            cur = (now.minute * 60) + now.second
            seconds_left = 900 - (cur % 900)
        formatted = f"{seconds_left // 60:02d}:{seconds_left % 60:02d}"
    elif tf == "1h":
        close_epoch = float(((now_int // 3600) + 1) * 3600)
        cur = (now.minute * 60) + now.second
        seconds_left = 3600 - cur
        formatted = f"{seconds_left // 60:02d}:{seconds_left % 60:02d}"
    elif tf == "4h":
        close_epoch = float(((now_int // 14400) + 1) * 14400)
        cur = ((now.hour % 4) * 3600) + (now.minute * 60) + now.second
        seconds_left = 14400 - cur
        hrs = seconds_left // 3600
        mins = (seconds_left % 3600) // 60
        secs = seconds_left % 60
        formatted = f"{hrs:02d}:{mins:02d}:{secs:02d}"
    elif tf == "1d":
        close_epoch = float(((now_int // 86400) + 1) * 86400)
        cur = (now.hour * 3600) + (now.minute * 60) + now.second
        seconds_left = 86400 - cur
        hrs = seconds_left // 3600
        mins = (seconds_left % 3600) // 60
        formatted = f"{hrs:02d}:{mins:02d}"
    else:
        close_epoch = float(((now_int // 900) + 1) * 900)
        cur = (now.minute * 60) + now.second
        seconds_left = 900 - (cur % 900)
        formatted = f"{seconds_left // 60:02d}:{seconds_left % 60:02d}"

    return {
        "timeframe": tf,
        "seconds_left": seconds_left,
        "formatted": formatted,
        "close_epoch_ms": int(close_epoch * 1000),
        "server_now_ms": int(now_epoch * 1000),
        "clock_offset_sec": round(offset_sec, 3),
        "current_interval_id": str(int(close_epoch) - 900),
    }


_live_target_result_cache = {}
_live_target_lock = threading.Lock()


def get_live_15m_target_data(asset: str = "BTC") -> dict:
    """
    High-frequency 1-second resolver for live price, active 15M target,
    live delta spread, and last 5 targets trend box.
    Cached for 0.8s to provide sub-millisecond responses on 1s client polling.
    """
    now = time.time()
    
    with _target_lock:
        if asset not in _target_cache:
            _target_cache[asset] = {
                "timestamp": 0.0,
                "active_target": None,
                "last_5_targets": [],
                "streak_summary": ""
            }

    with _live_target_lock:
        if asset not in _live_target_result_cache:
            _live_target_result_cache[asset] = {"timestamp": 0.0, "data": None}
            
        if _live_target_result_cache[asset]["data"] and (now - _live_target_result_cache[asset]["timestamp"] < 0.95):
            # Update countdown on the fly using Kalshi-calibrated clock
            cached = dict(_live_target_result_cache[asset]["data"])
            cd = get_candle_countdown("15m", asset=asset)
            cached["seconds_left"] = cd["seconds_left"]
            cached["formatted_countdown"] = cd["formatted"]
            cached["close_epoch_ms"] = cd["close_epoch_ms"]
            cached["server_now_ms"] = cd["server_now_ms"]
            return cached
        # AUDIT FIX #4b: Stampede protection
        _live_target_result_cache[asset]["timestamp"] = now

    from backend.engine.multi_asset_fetcher import get_asset_ticker
    ticker = get_asset_ticker(asset)
    curr_price = float(ticker["price"])

    from zoneinfo import ZoneInfo
    try:
        from .kalshi_client import get_kalshi_utc_now
        now_dt = get_kalshi_utc_now().astimezone(ZoneInfo("America/New_York"))
    except Exception:
        now_dt = datetime.now(ZoneInfo("America/New_York"))
    curr_15m_start_min = (now_dt.minute // 15) * 15
    interval_start_dt = now_dt.replace(minute=curr_15m_start_min, second=0, microsecond=0)
    interval_id = int(interval_start_dt.timestamp())
    start_time_12hr = interval_start_dt.strftime("%I:%M %p").lstrip('0')

    with _target_lock:
        # Check if target benchmark needs refresh:
        needs_refresh = (
            _target_cache[asset].get("interval_id") != interval_id or
            _target_cache[asset]["active_target"] is None or
            (now - _target_cache[asset]["timestamp"] >= 300.0)
        )
        if needs_refresh:
            _target_cache[asset]["timestamp"] = now + 10.0  # Prevent stampede while fetching

    if needs_refresh:
        try:
            from backend.engine.multi_asset_fetcher import fetch_asset_candles
            df = fetch_asset_candles(asset, "15m", limit=20)
            n = len(df)
            if n > 0:
                prec = 5 if str(asset).upper() == "DOGE" else 2
                curr_start_price = round(float(df.iloc[-1]["open"]), prec)
                last_5 = compute_last_5_targets(df)
                streak_summary = compute_streak_summary(last_5)

                with _target_lock:
                    _target_cache[asset]["active_target"] = curr_start_price
                    _target_cache[asset]["interval_id"] = interval_id
                    _target_cache[asset]["target_source"] = f"15M Start Price ({start_time_12hr} ET)"
                    _target_cache[asset]["timestamp"] = now
                    _target_cache[asset]["last_5_targets"] = last_5
                    _target_cache[asset]["streak_summary"] = streak_summary
        except Exception as e:
            with _target_lock:
                if not _target_cache[asset]["active_target"]:
                    _target_cache[asset]["active_target"] = curr_price
                    _target_cache[asset]["interval_id"] = interval_id
                    _target_cache[asset]["target_source"] = f"15M Start Price ({start_time_12hr} ET)"
                    _target_cache[asset]["last_5_targets"] = []
                    _target_cache[asset]["streak_summary"] = "--"

    with _target_lock:
        target_price = _target_cache[asset]["active_target"] or curr_price
        target_source = _target_cache[asset].get("target_source", f"15M Start Price ({start_time_12hr} ET)")
        last_5_targets = _target_cache[asset]["last_5_targets"]
        streak_summary = _target_cache[asset]["streak_summary"]

    # Override with Kalshi Official Strike
    kalshi_m = get_kalshi_15m_market(series_ticker=f"KX{asset}15M", force_refresh=needs_refresh)
    if kalshi_m:
        kalshi_m = dict(kalshi_m)
        kalshi_m["is_synthetic"] = (kalshi_m.get("status") == "synthetic") or (kalshi_m.get("source") == "Kalshi Synthetic")
    if kalshi_m and kalshi_m.get("target_price"):
        target_price = float(kalshi_m["target_price"])
        target_source = "Kalshi Official Strike" if not kalshi_m.get("is_synthetic") else "Simulated (Kalshi Offline)"

    countdown = get_candle_countdown("15m", asset=asset)
    delta = round(curr_price - target_price, 2)
    delta_pct = round((delta / (target_price + 1e-10)) * 100, 3)
    status = "ABOVE" if delta >= 0 else "BELOW"

    res = {
        "price": curr_price,
        "target_price": target_price,
        "target_source": target_source,
        "delta": delta,
        "delta_pct": delta_pct,
        "status": status,
        "kalshi": kalshi_m,
        "change_24h": ticker["change_24h"],
        "high_24h": ticker["high_24h"],
        "low_24h": ticker["low_24h"],
        "volume_24h": ticker["volume_24h"],
        "seconds_left": countdown["seconds_left"],
        "formatted_countdown": countdown["formatted"],
        "close_epoch_ms": countdown["close_epoch_ms"],
        "server_now_ms": countdown["server_now_ms"],
        "last_5_targets": last_5_targets,
        "streak_summary": streak_summary,
        "latency_ms": round((time.time() - now) * 1000, 3)
    }
    with _live_target_lock:
        if asset not in _live_target_result_cache:
            _live_target_result_cache[asset] = {"timestamp": 0.0, "data": None}
        _live_target_result_cache[asset]["timestamp"] = time.time()
        _live_target_result_cache[asset]["data"] = res
    return res


if __name__ == "__main__":
    logger.info("Testing multi-timeframe fetcher...")
    for tf in ["1m", "5m", "15m", "1h", "4h", "1d"]:
        df = fetch_candles(timeframe=tf, limit=10)
        cd = get_candle_countdown(tf)
        logger.info(f"[{tf.upper()}] Fetched {len(df)} candles. Close in: {cd['formatted']} (Latest close: ${df.iloc[-1]['close']:.2f})")


_ob_cache = {}
_ob_lock = threading.Lock()

def get_coinbase_orderbook_imbalance(asset: str = "BTC", depth_percent: float = 0.5) -> dict:
    # Support legacy callers passing depth_percent as first positional float arg
    if isinstance(asset, (int, float)):
        depth_percent = float(asset)
        asset = "BTC"
    a_up = str(asset or "BTC").upper().strip()
    if a_up not in ("BTC", "ETH", "SOL", "DOGE"):
        a_up = "BTC"

    now = time.time()
    with _ob_lock:
        entry = _ob_cache.get(a_up)
        if entry and entry.get("data") is not None and (now - entry.get("time", 0.0)) < 4.0:
            return dict(entry["data"])

    try:
        url = f'https://api.exchange.coinbase.com/products/{a_up}-USD/book?level=2'
        resp = _HTTP_SESSION.get(url, headers={'Accept': 'application/json'}, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            bids = data.get('bids', [])
            asks = data.get('asks', [])
            if not bids or not asks:
                return {'asset': a_up, 'imbalance': 0.0, 'bid_vol': 0.0, 'ask_vol': 0.0, 'largest_bid_wall': None, 'largest_ask_wall': None, 'bid_wall_size': 0.0, 'ask_wall_size': 0.0}
            best_bid = float(bids[0][0])
            best_ask = float(asks[0][0])
            mid = (best_bid + best_ask) / 2.0
            bid_vol = sum(float(b[1]) for b in bids if float(b[0]) >= mid * (1 - depth_percent/100))
            ask_vol = sum(float(a[1]) for a in asks if float(a[0]) <= mid * (1 + depth_percent/100))

            # Find the largest single order level
            largest_bid_wall = max(bids, key=lambda x: float(x[1])) if bids else None
            largest_ask_wall = max(asks, key=lambda x: float(x[1])) if asks else None

            imb = 0.0
            total_vol = bid_vol + ask_vol
            if total_vol > 0:
                imb = ((bid_vol - ask_vol) / total_vol) * 100.0

            res = {
                'asset': a_up,
                'imbalance': round(imb, 2),
                'bid_vol': round(bid_vol, 2),
                'ask_vol': round(ask_vol, 2),
                'largest_bid_wall': float(largest_bid_wall[0]) if largest_bid_wall else None,
                'bid_wall_size': float(largest_bid_wall[1]) if largest_bid_wall else 0.0,
                'largest_ask_wall': float(largest_ask_wall[0]) if largest_ask_wall else None,
                'ask_wall_size': float(largest_ask_wall[1]) if largest_ask_wall else 0.0
            }
            with _ob_lock:
                _ob_cache[a_up] = {"data": res, "time": now}
            return res
    except Exception as e:
        pass

    return {'asset': a_up, 'imbalance': 0.0, 'bid_vol': 0.0, 'ask_vol': 0.0, 'largest_bid_wall': None, 'largest_ask_wall': None, 'bid_wall_size': 0.0, 'ask_wall_size': 0.0}
