"""
Bitcoin Multi-Timeframe Data Fetcher
Fetches live and historical OHLCV candles (1m, 5m, 15m, 1h, 4h, 1d) and ticker stats for BTC.
Includes fallback logic across Coinbase, Kraken, Binance.US, and Yahoo Finance.
"""

import time
from datetime import datetime, timezone
import requests
import pandas as pd

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

try:
    from .kalshi_client import get_kalshi_15m_market
except ImportError:
    from kalshi_client import get_kalshi_15m_market


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
    resp = requests.get(url, params=params, headers=HEADERS, timeout=8)
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

    return df.tail(limit).reset_index(drop=True)


def _fetch_from_kraken(timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:
    """Fallback fetch from Kraken API."""
    cfg = TIMEFRAMES.get(timeframe, TIMEFRAMES["15m"])
    url = "https://api.kraken.com/0/public/OHLC"
    params = {"pair": "XBTUSD", "interval": cfg["kraken"]}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=8)
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
    return df


def _fetch_from_binance_us(timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:
    """Fallback fetch from Binance.US API."""
    cfg = TIMEFRAMES.get(timeframe, TIMEFRAMES["15m"])
    url = "https://api.binance.us/api/v3/klines"
    params = {"symbol": "BTCUSDT", "interval": cfg["binance"], "limit": min(limit, 500)}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=8)
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
    return df


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
    records = []
    for _, row in hist.iterrows():
        ts = int(row[time_col].timestamp())
        records.append({
            "time": ts,
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row["Volume"])
        })
    df = pd.DataFrame(records).sort_values("time").reset_index(drop=True)
    if timeframe == "4h":
        df = _aggregate_to_4h(df)
    return df.tail(limit).reset_index(drop=True)


def fetch_candles(timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:
    """
    Fetch OHLCV candles for any timeframe (1m, 5m, 15m, 1h, 4h, 1d)
    with resilient multi-exchange fallback.
    """
    tf = timeframe.lower()
    if tf not in TIMEFRAMES:
        tf = "15m"

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
                df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
                return df
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"All market data providers failed for timeframe {tf}. Last error: {last_err}")


# Backwards compatibility alias
def fetch_15m_candles(limit: int = 300) -> pd.DataFrame:
    return fetch_candles(timeframe="15m", limit=limit)


def format_volume_series(df: pd.DataFrame) -> list[dict]:
    """Format volume bars with green/red colors for Lightweight Charts histogram."""
    if df.empty or "volume" not in df.columns:
        return []
    series = []
    for _, row in df.iterrows():
        is_green = float(row["close"]) >= float(row["open"])
        series.append({
            "time": int(row["time"]),
            "value": round(float(row["volume"]), 4),
            "color": "rgba(16, 185, 129, 0.45)" if is_green else "rgba(239, 68, 68, 0.45)"
        })
    return series


# High-performance in-memory cache for ultra-fast 1-second polling
_ticker_cache = {
    "timestamp": 0.0,
    "data": None
}

_target_cache = {
    "timestamp": 0.0,
    "active_target": None,
    "last_5_targets": [],
    "streak_summary": ""
}


def get_btc_ticker() -> dict:
    """
    Get live 24h ticker info: price, 24h high, low, volume, and % change.
    Cached for 1.0s to support high-frequency 1s polling without external API limits.
    """
    now = time.time()
    if _ticker_cache["data"] and (now - _ticker_cache["timestamp"] < 1.0):
        return _ticker_cache["data"]

    # Try Coinbase ticker (fastest endpoint)
    try:
        url = "https://api.exchange.coinbase.com/products/BTC-USD/ticker"
        resp = requests.get(url, headers=HEADERS, timeout=3)
        if resp.status_code == 200:
            tick = resp.json()
            last_price = float(tick["price"])
            vol_24h = float(tick.get("volume", 0))

            # Fetch or approximate 24h stats if older than 30s
            stats_cached = _ticker_cache.get("stats")
            if not stats_cached or (now - stats_cached.get("ts", 0) > 30):
                try:
                    s_url = "https://api.exchange.coinbase.com/products/BTC-USD/stats"
                    s_resp = requests.get(s_url, headers=HEADERS, timeout=4)
                    if s_resp.status_code == 200:
                        s_data = s_resp.json()
                        stats_cached = {
                            "open": float(s_data["open"]),
                            "high": float(s_data["high"]),
                            "low": float(s_data["low"]),
                            "ts": now
                        }
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
                "source": "Coinbase"
            }
            _ticker_cache["timestamp"] = now
            _ticker_cache["data"] = result
            return result
    except Exception:
        pass

    # Fallback to Binance.US
    try:
        url = "https://api.binance.us/api/v3/ticker/24hr?symbol=BTCUSDT"
        resp = requests.get(url, headers=HEADERS, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            result = {
                "price": round(float(data["lastPrice"]), 2),
                "open_24h": round(float(data["openPrice"]), 2),
                "high_24h": round(float(data["highPrice"]), 2),
                "low_24h": round(float(data["lowPrice"]), 2),
                "volume_24h": round(float(data["volume"]), 2),
                "change_24h": round(float(data["priceChangePercent"]), 2),
                "source": "Binance.US"
            }
            _ticker_cache["timestamp"] = now
            _ticker_cache["data"] = result
            return result
    except Exception:
        pass

    # Fallback to candles
    if _ticker_cache["data"]:
        return _ticker_cache["data"]

    candles = fetch_candles(timeframe="15m", limit=2)
    last_close = float(candles.iloc[-1]["close"])
    prev_close = float(candles.iloc[-2]["close"])
    result = {
        "price": round(last_close, 2),
        "open_24h": round(prev_close, 2),
        "high_24h": round(last_close, 2),
        "low_24h": round(last_close, 2),
        "volume_24h": round(float(candles.iloc[-1]["volume"]), 2),
        "change_24h": round(((last_close - prev_close) / prev_close) * 100, 2),
        "source": "CandleFallback"
    }
    _ticker_cache["timestamp"] = now
    _ticker_cache["data"] = result
    return result


def get_candle_countdown(timeframe: str = "15m") -> dict:
    """
    Returns seconds and formatted time until the current candle of the selected timeframe closes.
    Supports: 1m, 5m, 15m, 1h, 4h, 1d.
    """
    now = datetime.now(timezone.utc)
    tf = timeframe.lower()

    if tf == "1m":
        seconds_left = 60 - (now.second % 60)
        formatted = f"00:{seconds_left:02d}"
    elif tf == "5m":
        cur = (now.minute * 60) + now.second
        seconds_left = 300 - (cur % 300)
        formatted = f"{seconds_left // 60:02d}:{seconds_left % 60:02d}"
    elif tf == "15m":
        cur = (now.minute * 60) + now.second
        seconds_left = 900 - (cur % 900)
        formatted = f"{seconds_left // 60:02d}:{seconds_left % 60:02d}"
    elif tf == "1h":
        cur = (now.minute * 60) + now.second
        seconds_left = 3600 - cur
        formatted = f"{seconds_left // 60:02d}:{seconds_left % 60:02d}"
    elif tf == "4h":
        cur = ((now.hour % 4) * 3600) + (now.minute * 60) + now.second
        seconds_left = 14400 - cur
        hrs = seconds_left // 3600
        mins = (seconds_left % 3600) // 60
        secs = seconds_left % 60
        formatted = f"{hrs:02d}:{mins:02d}:{secs:02d}"
    elif tf == "1d":
        cur = (now.hour * 3600) + (now.minute * 60) + now.second
        seconds_left = 86400 - cur
        hrs = seconds_left // 3600
        mins = (seconds_left % 3600) // 60
        formatted = f"{hrs:02d}:{mins:02d}"
    else:
        cur = (now.minute * 60) + now.second
        seconds_left = 900 - (cur % 900)
        formatted = f"{seconds_left // 60:02d}:{seconds_left % 60:02d}"

    return {
        "timeframe": tf,
        "seconds_left": seconds_left,
        "formatted": formatted
    }


_live_target_result_cache = {
    "timestamp": 0.0,
    "data": None
}


def get_live_15m_target_data() -> dict:
    """
    High-frequency 1-second resolver for BTC live price, active 15M target,
    live delta spread, and last 5 targets trend box.
    Cached for 0.8s to provide sub-millisecond responses on 1s client polling.
    """
    now = time.time()
    if _live_target_result_cache["data"] and (now - _live_target_result_cache["timestamp"] < 1.2):
        # Update countdown on the fly
        cached = dict(_live_target_result_cache["data"])
        cd = get_candle_countdown("15m")
        cached["seconds_left"] = cd["seconds_left"]
        cached["formatted_countdown"] = cd["formatted"]
        return cached

    ticker = get_btc_ticker()
    curr_price = float(ticker["price"])
    countdown = get_candle_countdown("15m")

    # Refresh target cache every 30s or when empty
    if not _target_cache["active_target"] or (now - _target_cache["timestamp"] > 30.0):
        try:
            df = fetch_candles("15m", limit=20)
            n = len(df)
            if n >= 7:
                # Active target is previous closed 15m candle close (index n - 2)
                _target_cache["active_target"] = round(float(df.iloc[-2]["close"]), 2)
                
                # Extract last 5 completed targets (indices n - 6 to n - 2)
                last_5 = []
                higher_count = 0
                lower_count = 0
                for i in range(n - 6, n - 1):
                    c = df.iloc[i]
                    p = df.iloc[i - 1]
                    c_close = float(c["close"])
                    p_close = float(p["close"])
                    diff = round(c_close - p_close, 2)
                    diff_pct = round((diff / (p_close + 1e-10)) * 100, 2)
                    is_higher = diff >= 0
                    if is_higher:
                        higher_count += 1
                    else:
                        lower_count += 1

                    # Format timestamp cleanly: e.g. "15:45"
                    t_val = c.get("time")
                    time_str = datetime.fromtimestamp(int(t_val), tz=timezone.utc).strftime("%H:%M") if t_val else "--:--"

                    last_5.append({
                        "time": time_str,
                        "price": round(c_close, 2),
                        "delta": diff,
                        "delta_pct": diff_pct,
                        "direction": "HIGHER" if is_higher else "LOWER",
                        "arrow": "▲" if is_higher else "▼",
                        "color": "green" if is_higher else "red"
                    })

                _target_cache["last_5_targets"] = last_5
                _target_cache["streak_summary"] = f"{higher_count} Higher / {lower_count} Lower"
                _target_cache["timestamp"] = now
        except Exception as e:
            if not _target_cache["active_target"]:
                _target_cache["active_target"] = curr_price
                _target_cache["last_5_targets"] = []
                _target_cache["streak_summary"] = "--"

    # Check Kalshi live 15M target strike
    kalshi_m = None
    try:
        kalshi_m = get_kalshi_15m_market()
    except Exception:
        pass

    target_source = "15M Candle Close"
    if kalshi_m and kalshi_m.get("target_price"):
        target_price = kalshi_m["target_price"]
        target_source = "Kalshi KXBTC15M"
    else:
        target_price = _target_cache["active_target"] or curr_price

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
        "last_5_targets": _target_cache["last_5_targets"],
        "streak_summary": _target_cache["streak_summary"],
        "latency_ms": round((time.time() - now) * 1000, 3)
    }
    _live_target_result_cache["timestamp"] = time.time()
    _live_target_result_cache["data"] = res
    return res


if __name__ == "__main__":
    print("Testing multi-timeframe fetcher...")
    for tf in ["1m", "5m", "15m", "1h", "4h", "1d"]:
        df = fetch_candles(timeframe=tf, limit=10)
        cd = get_candle_countdown(tf)
        print(f"[{tf.upper()}] Fetched {len(df)} candles. Close in: {cd['formatted']} (Latest close: ${df.iloc[-1]['close']:.2f})")
