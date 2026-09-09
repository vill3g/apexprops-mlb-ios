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


def get_btc_ticker() -> dict:
    """
    Get live 24h ticker info: price, 24h high, low, volume, and % change.
    """
    try:
        url = "https://api.exchange.coinbase.com/products/BTC-USD/stats"
        resp = requests.get(url, headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            stats = resp.json()
            last_price = float(stats["last"])
            open_price = float(stats["open"])
            high_24h = float(stats["high"])
            low_24h = float(stats["low"])
            volume_24h = float(stats["volume"])
            change_24h = ((last_price - open_price) / open_price) * 100 if open_price > 0 else 0.0

            return {
                "price": last_price,
                "open_24h": open_price,
                "high_24h": high_24h,
                "low_24h": low_24h,
                "volume_24h": volume_24h,
                "change_24h": change_24h,
                "source": "Coinbase"
            }
    except Exception:
        pass

    # Fallback to candle close
    candles = fetch_candles(timeframe="15m", limit=2)
    last_close = float(candles.iloc[-1]["close"])
    prev_close = float(candles.iloc[-2]["close"])
    return {
        "price": last_close,
        "open_24h": prev_close,
        "high_24h": last_close,
        "low_24h": last_close,
        "volume_24h": float(candles.iloc[-1]["volume"]),
        "change_24h": ((last_close - prev_close) / prev_close) * 100,
        "source": "CandleFallback"
    }


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
        # Default to 15m
        cur = (now.minute * 60) + now.second
        seconds_left = 900 - (cur % 900)
        formatted = f"{seconds_left // 60:02d}:{seconds_left % 60:02d}"

    return {
        "timeframe": tf,
        "seconds_left": seconds_left,
        "formatted": formatted
    }


if __name__ == "__main__":
    print("Testing multi-timeframe fetcher...")
    for tf in ["1m", "5m", "15m", "1h", "4h", "1d"]:
        df = fetch_candles(timeframe=tf, limit=10)
        cd = get_candle_countdown(tf)
        print(f"[{tf.upper()}] Fetched {len(df)} candles. Close in: {cd['formatted']} (Latest close: ${df.iloc[-1]['close']:.2f})")
