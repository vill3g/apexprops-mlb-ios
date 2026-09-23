import time
from datetime import datetime
import pandas as pd
import logging
from backend.btc.data_fetcher import (
    _fetch_from_kraken, _fetch_from_binance_us, _fetch_from_coinbase, _fetch_from_yfinance,
    TIMEFRAMES, get_candle_countdown, _HTTP_SESSION
)

logger = logging.getLogger(__name__)

# Fallback mapping if asset isn't BTC
TICKER_MAP = {
    "BTC": {"kraken": "XBTUSD", "binance": "BTCUSDT", "coinbase": "BTC-USD", "yf": "BTC-USD"},
    "ETH": {"kraken": "ETHUSD", "binance": "ETHUSDT", "coinbase": "ETH-USD", "yf": "ETH-USD"},
    "GOLD": {"kraken": "PAXGUSD", "binance": None, "coinbase": None, "yf": "PAXG-USD"},
    "NDQ": {"kraken": None, "binance": None, "coinbase": None, "yf": "NQ=F"},
    "EURUSD": {"kraken": None, "binance": None, "coinbase": None, "yf": "EURUSD=X"},
    "GBPUSD": {"kraken": None, "binance": None, "coinbase": None, "yf": "GBPUSD=X"},
    "USDJPY": {"kraken": None, "binance": None, "coinbase": None, "yf": "USDJPY=X"},
    "AUDUSD": {"kraken": None, "binance": None, "coinbase": None, "yf": "AUDUSD=X"},
}

def _fetch_yf_asset(asset: str, timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:
    import yfinance as yf
    cfg = TIMEFRAMES.get(timeframe, TIMEFRAMES["15m"])
    period_map = {"1m": "2d", "5m": "5d", "15m": "5d", "1h": "1mo", "4h": "1mo", "1d": "1y"}
    period = period_map.get(timeframe, "5d")
    
    symbol = TICKER_MAP.get(asset, {}).get("yf", "BTC-USD")
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period, interval=cfg["yf"])
    if hist.empty:
        raise ValueError(f"yfinance returned empty data for {symbol}")
    
    hist = hist.reset_index()
    time_col = "Datetime" if "Datetime" in hist.columns else "Date"
    hist["time"] = pd.to_datetime(hist[time_col], utc=True).astype("int64") // 10**9
    hist = hist.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    df = hist[["time", "open", "high", "low", "close", "volume"]].sort_values("time").reset_index(drop=True)
    return df

def _fetch_kraken_asset(asset: str, timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:
    symbol = TICKER_MAP.get(asset, {}).get("kraken")
    if not symbol:
        raise ValueError(f"Asset {asset} not supported on Kraken")
    
    cfg = TIMEFRAMES.get(timeframe, TIMEFRAMES["15m"])
    url = "https://api.kraken.com/0/public/OHLC"
    params = {"pair": symbol, "interval": cfg["kraken"]}
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
    return pd.DataFrame(records)

def _fetch_binance_asset(asset: str, timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:
    symbol = TICKER_MAP.get(asset, {}).get("binance")
    if not symbol:
        raise ValueError(f"Asset {asset} not supported on Binance.US")
    
    cfg = TIMEFRAMES.get(timeframe, TIMEFRAMES["15m"])
    url = "https://api.binance.us/api/v3/klines"
    params = {"symbol": symbol, "interval": cfg["binance"], "limit": min(limit, 500)}
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
    return pd.DataFrame(records)

def fetch_asset_candles(asset: str = "BTC", timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:
    """Fetch candles for multi-assets with correct fallbacks."""
    asset = asset.upper()
    if asset == "BTC":
        from backend.btc.data_fetcher import fetch_candles
        return fetch_candles(timeframe, limit)

    tf = timeframe.lower()
    if tf not in TIMEFRAMES:
        tf = "15m"

    if asset == "NDQ":
        fetchers = [("Yahoo Finance", lambda: _fetch_yf_asset(asset, tf, limit))]
    elif asset == "GOLD":
        fetchers = [
            ("Kraken", lambda: _fetch_kraken_asset(asset, tf, limit)),
            ("Yahoo Finance", lambda: _fetch_yf_asset(asset, tf, limit))
        ]
    elif asset == "ETH":
        fetchers = [
            ("Kraken", lambda: _fetch_kraken_asset(asset, tf, limit)),
            ("Binance", lambda: _fetch_binance_asset(asset, tf, limit)),
            ("Yahoo Finance", lambda: _fetch_yf_asset(asset, tf, limit))
        ]
    elif asset in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]:
        from backend.forex.data_fetcher import fetch_forex_candles
        return fetch_forex_candles(asset, tf, limit)
    else:
        raise ValueError(f"Unknown asset {asset}")

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

    raise RuntimeError(f"All providers failed for {asset} {tf}. Last error: {last_err}")


def get_asset_ticker(asset: str) -> dict:
    asset = asset.upper()
    if asset == "BTC":
        from backend.btc.data_fetcher import get_btc_ticker
        return get_btc_ticker()
    if asset in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]:
        from backend.forex.data_fetcher import get_forex_ticker
        return get_forex_ticker(asset)
    df_1m = fetch_asset_candles(asset, "1m", limit=1)
    df_1d = fetch_asset_candles(asset, "1d", limit=2)
    
    if df_1d.empty or len(df_1d) < 1:
        return {"price": 0, "change_24h": 0, "high_24h": 0, "low_24h": 0, "volume_24h": 0}
        
    latest_1d = df_1d.iloc[-1]
    curr_price = float(df_1m.iloc[-1]["close"]) if not df_1m.empty else float(latest_1d["close"])
    high = float(latest_1d["high"])
    low = float(latest_1d["low"])
    vol = float(latest_1d["volume"])
    prev_close = float(df_1d.iloc[-2]["close"]) if len(df_1d) > 1 else float(latest_1d["close"])
    change = ((curr_price - prev_close) / prev_close * 100) if prev_close else 0.0
    return {
        "price": curr_price,
        "change_24h": round(change, 2),
        "high_24h": round(high, 2),
        "low_24h": round(low, 2),
        "volume_24h": round(vol, 2)
    }

import pytz
def is_market_open(asset: str) -> bool:
    asset = asset.upper()
    if asset in ["BTC", "ETH"]:
        return True
    now = datetime.now(pytz.timezone("America/New_York"))
    if asset == "NDQ":
        if now.weekday() >= 5: return False
        current_minutes = now.hour * 60 + now.minute
        return 570 <= current_minutes < 960
    if asset == "GOLD":
        if now.weekday() == 4 and now.hour >= 17: return False
        if now.weekday() == 5: return False
        if now.weekday() == 6 and now.hour < 18: return False
        return True
    return True
