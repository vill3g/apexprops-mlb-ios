import logging
import threading
import time
from datetime import datetime

import pandas as pd
import pytz

from backend.btc.data_fetcher import _HTTP_SESSION, TIMEFRAMES

logger = logging.getLogger(__name__)

# Fallback mapping if asset isn't BTC
TICKER_MAP = {
    "BTC": {"kraken": "XBTUSD", "binance": "BTCUSDT", "coinbase": "BTC-USD", "yf": "BTC-USD"},
    "ETH": {"kraken": "ETHUSD", "binance": "ETHUSDT", "coinbase": "ETH-USD", "yf": "ETH-USD"},
    "SOL": {"kraken": "SOLUSD", "binance": "SOLUSDT", "coinbase": "SOL-USD", "yf": "SOL-USD"},
    "DOGE": {"kraken": "XDGUSD", "binance": "DOGEUSDT", "coinbase": "DOGE-USD", "yf": "DOGE-USD"},
    "GOLD": {"kraken": "PAXGUSD", "binance": None, "coinbase": None, "yf": "PAXG-USD"},
    "NDQ": {"kraken": None, "binance": None, "coinbase": None, "yf": "NQ=F"},
    "EURUSD": {"kraken": None, "binance": None, "coinbase": None, "yf": "EURUSD=X"},
    "GBPUSD": {"kraken": None, "binance": None, "coinbase": None, "yf": "GBPUSD=X"},
    "USDJPY": {"kraken": None, "binance": None, "coinbase": None, "yf": "USDJPY=X"},
    "AUDUSD": {"kraken": None, "binance": None, "coinbase": None, "yf": "AUDUSD=X"},
}

_YF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

_asset_candles_cache = {}
_asset_candles_lock = threading.Lock()
_ASSET_CANDLES_TTL = 2.5


def _fetch_yf_asset(asset: str, timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:
    cfg = TIMEFRAMES.get(timeframe, TIMEFRAMES["15m"])
    period_map = {"1m": "2d", "5m": "5d", "15m": "5d", "1h": "1mo", "4h": "1mo", "1d": "1y"}
    period = period_map.get(timeframe, "5d")
    symbol = TICKER_MAP.get(asset, {}).get("yf", "BTC-USD")

    # 1. Primary: Direct Yahoo v8 JSON chart API (fast, thread-safe, exact Unix seconds)
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        try:
            url = f"https://{host}/v8/finance/chart/{symbol}"
            resp = _HTTP_SESSION.get(url, params={"interval": cfg["yf"], "range": period}, headers=_YF_HEADERS, timeout=3.5)
            if resp.status_code == 200:
                payload = resp.json()
                results = (payload.get("chart") or {}).get("result")
                if results and isinstance(results, list) and results[0]:
                    res = results[0]
                    timestamps = res.get("timestamp") or []
                    quote_list = ((res.get("indicators") or {}).get("quote") or [{}])
                    quote = quote_list[0] if quote_list else {}
                    opens = quote.get("open") or []
                    highs = quote.get("high") or []
                    lows = quote.get("low") or []
                    closes = quote.get("close") or []
                    volumes = quote.get("volume") or []
                    records = []
                    for i, t in enumerate(timestamps):
                        o = opens[i] if i < len(opens) else None
                        h = highs[i] if i < len(highs) else None
                        l = lows[i] if i < len(lows) else None
                        c = closes[i] if i < len(closes) else None
                        v = volumes[i] if i < len(volumes) else 0
                        if t is None or o is None or h is None or l is None or c is None:
                            continue
                        records.append({
                            "time": int(t),
                            "open": float(o),
                            "high": float(h),
                            "low": float(l),
                            "close": float(c),
                            "volume": float(v or 0.0),
                        })
                    if records:
                        df = pd.DataFrame(records).drop_duplicates(subset=["time"], keep="last").sort_values("time").reset_index(drop=True)
                        return df.tail(limit).reset_index(drop=True)
        except Exception as e:
            logger.debug(f"[MultiAssetFetcher] Yahoo v8 direct chart fallback for {symbol}: {e}")

    # 2. Secondary fallback: yfinance library with unit-safe Unix second conversion
    import yfinance as yf
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period, interval=cfg["yf"])
    if hist.empty:
        raise ValueError(f"yfinance returned empty data for {symbol}")

    hist = hist.reset_index()
    time_col = "Datetime" if "Datetime" in hist.columns else "Date"
    dt_series = pd.to_datetime(hist[time_col], utc=True)
    hist["time"] = ((dt_series - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1s")).astype("int64")
    hist = hist.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    df = hist[["time", "open", "high", "low", "close", "volume"]].dropna(subset=["open", "high", "low", "close"])
    df = df.drop_duplicates(subset=["time"], keep="last").sort_values("time").reset_index(drop=True)
    return df.tail(limit).reset_index(drop=True)


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
    """Fetch candles for multi-assets with correct fallbacks and short TTL cache."""
    asset = asset.upper()
    if asset == "BTC":
        from backend.btc.data_fetcher import fetch_candles
        return fetch_candles(timeframe, limit)

    tf = timeframe.lower()
    if tf not in TIMEFRAMES:
        tf = "15m"

    if asset in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]:
        from backend.forex.data_fetcher import fetch_forex_candles
        df_fx = fetch_forex_candles(asset, tf, limit)
        if not df_fx.empty:
            df_fx["datetime"] = pd.to_datetime(df_fx["time"], unit="s", utc=True)
        return df_fx

    cache_key = (asset, tf)
    now = time.time()
    with _asset_candles_lock:
        cached = _asset_candles_cache.get(cache_key)
        if cached and (now - cached[0]) < _ASSET_CANDLES_TTL and len(cached[1]) >= min(limit, 10):
            return cached[1].tail(limit).copy().reset_index(drop=True)

    if asset == "NDQ":
        fetchers = [("Yahoo Finance", lambda: _fetch_yf_asset(asset, tf, max(limit, 300)))]
    elif asset == "GOLD":
        fetchers = [
            ("Kraken", lambda: _fetch_kraken_asset(asset, tf, max(limit, 300))),
            ("Yahoo Finance", lambda: _fetch_yf_asset(asset, tf, max(limit, 300)))
        ]
    elif asset in ["ETH", "SOL", "DOGE"]:
        fetchers = [
            ("Kraken", lambda: _fetch_kraken_asset(asset, tf, max(limit, 300))),
            ("Binance", lambda: _fetch_binance_asset(asset, tf, max(limit, 300))),
            ("Yahoo Finance", lambda: _fetch_yf_asset(asset, tf, max(limit, 300)))
        ]
    else:
        raise ValueError(f"Unknown asset {asset}")

    last_err = None
    for name, fetcher in fetchers:
        try:
            df = fetcher()
            min_required = min(limit, 10)
            if df is not None and len(df) >= min_required:
                df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
                with _asset_candles_lock:
                    _asset_candles_cache[cache_key] = (now, df)
                return df.tail(limit).copy().reset_index(drop=True)
        except Exception as e:
            last_err = e
            continue

    with _asset_candles_lock:
        if cached and not cached[1].empty:
            return cached[1].tail(limit).copy().reset_index(drop=True)

    raise RuntimeError(f"All providers failed for {asset} {tf}. Last error: {last_err}")


_multi_ticker_cache = {}
_multi_ticker_lock = threading.Lock()
_MULTI_TICKER_TTL = 2.0


def get_asset_ticker(asset: str) -> dict:
    asset = asset.upper()
    if asset == "BTC":
        from backend.btc.data_fetcher import get_btc_ticker
        return get_btc_ticker()
    if asset in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]:
        from backend.forex.data_fetcher import get_forex_ticker
        return get_forex_ticker(asset)

    now = time.time()
    with _multi_ticker_lock:
        cached = _multi_ticker_cache.get(asset)
        if cached and cached["data"] and (now - cached["timestamp"] < _MULTI_TICKER_TTL):
            return cached["data"]
        if asset not in _multi_ticker_cache:
            _multi_ticker_cache[asset] = {"timestamp": 0.0, "data": None}
        # Prevent stampede
        _multi_ticker_cache[asset]["timestamp"] = now + 3.0

    prec = 5 if asset == "DOGE" else 2

    # Fast path 1: Binance.US 24hr ticker for ETH, SOL, DOGE
    bin_sym = TICKER_MAP.get(asset, {}).get("binance")
    if bin_sym:
        try:
            resp = _HTTP_SESSION.get("https://api.binance.us/api/v3/ticker/24hr", params={"symbol": bin_sym}, timeout=2.5)
            if resp.status_code == 200:
                d = resp.json()
                curr_p = float(d.get("lastPrice") or 0.0)
                if curr_p > 0:
                    res = {
                        "price": round(curr_p, prec),
                        "change_24h": round(float(d.get("priceChangePercent") or 0.0), 2),
                        "high_24h": round(float(d.get("highPrice") or curr_p), prec),
                        "low_24h": round(float(d.get("lowPrice") or curr_p), prec),
                        "volume_24h": round(float(d.get("volume") or 0.0), 2),
                    }
                    with _multi_ticker_lock:
                        _multi_ticker_cache[asset] = {"timestamp": time.time(), "data": res}
                    return res
        except Exception:
            pass

    # Fast path 2: Kraken Ticker for GOLD (PAXGUSD) or crypto fallback
    kr_sym = TICKER_MAP.get(asset, {}).get("kraken")
    if kr_sym:
        try:
            resp = _HTTP_SESSION.get("https://api.kraken.com/0/public/Ticker", params={"pair": kr_sym}, timeout=2.5)
            if resp.status_code == 200:
                r_json = (resp.json() or {}).get("result") or {}
                pk = next(iter(r_json.keys()), None)
                if pk:
                    tk = r_json[pk]
                    curr_p = float(tk["c"][0])
                    open_p = float(tk.get("o") or curr_p)
                    chg = ((curr_p - open_p) / open_p * 100.0) if open_p else 0.0
                    res = {
                        "price": round(curr_p, prec),
                        "change_24h": round(chg, 2),
                        "high_24h": round(float(tk["h"][1]), prec),
                        "low_24h": round(float(tk["l"][1]), prec),
                        "volume_24h": round(float(tk["v"][1]), 2),
                    }
                    with _multi_ticker_lock:
                        _multi_ticker_cache[asset] = {"timestamp": time.time(), "data": res}
                    return res
        except Exception:
            pass

    # Fast path 3: Yahoo v8 chart meta (for NDQ and fallback)
    yf_sym = TICKER_MAP.get(asset, {}).get("yf")
    if yf_sym:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_sym}"
            resp = _HTTP_SESSION.get(url, params={"interval": "15m", "range": "5d"}, headers=_YF_HEADERS, timeout=3.0)
            if resp.status_code == 200:
                results = ((resp.json() or {}).get("chart") or {}).get("result")
                if results and results[0]:
                    meta = results[0].get("meta") or {}
                    curr_p = float(meta.get("regularMarketPrice") or 0.0)
                    prev_c = float(meta.get("chartPreviousClose") or meta.get("previousClose") or curr_p)
                    if curr_p > 0:
                        chg = ((curr_p - prev_c) / prev_c * 100.0) if prev_c else 0.0
                        res = {
                            "price": round(curr_p, prec),
                            "change_24h": round(chg, 2),
                            "high_24h": round(float(meta.get("regularMarketDayHigh") or curr_p), prec),
                            "low_24h": round(float(meta.get("regularMarketDayLow") or curr_p), prec),
                            "volume_24h": round(float(meta.get("regularMarketVolume") or 0.0), 2),
                        }
                        with _multi_ticker_lock:
                            _multi_ticker_cache[asset] = {"timestamp": time.time(), "data": res}
                        return res
        except Exception:
            pass

    # Fallback: derive from 15m candles
    try:
        df_15m = fetch_asset_candles(asset, "15m", limit=96)
        if not df_15m.empty:
            curr_price = float(df_15m.iloc[-1]["close"])
            prev_close = float(df_15m.iloc[0]["close"])
            change = ((curr_price - prev_close) / prev_close * 100.0) if prev_close else 0.0
            res = {
                "price": round(curr_price, prec),
                "change_24h": round(change, 2),
                "high_24h": round(float(df_15m["high"].max()), prec),
                "low_24h": round(float(df_15m["low"].min()), prec),
                "volume_24h": round(float(df_15m["volume"].sum()), 2),
            }
            with _multi_ticker_lock:
                _multi_ticker_cache[asset] = {"timestamp": time.time(), "data": res}
            return res
    except Exception as e:
        logger.debug(f"[MultiAssetFetcher] Asset {asset} candles unavailable: {e}")

    res = {"price": 0.50, "change_24h": 0, "high_24h": 0, "low_24h": 0, "volume_24h": 0}
    with _multi_ticker_lock:
        _multi_ticker_cache[asset] = {"timestamp": time.time(), "data": res}
    return res


def is_market_open(asset: str) -> bool:
    asset = asset.upper()
    if asset in ["BTC", "ETH", "SOL", "DOGE"]:
        return True
    now = datetime.now(pytz.timezone("America/New_York"))
    if asset == "NDQ":
        if now.weekday() >= 5:
            return False
        current_minutes = now.hour * 60 + now.minute
        return 570 <= current_minutes < 960
    if asset == "GOLD":
        if now.weekday() == 4 and now.hour >= 17:
            return False
        if now.weekday() == 5:
            return False
        if now.weekday() == 6 and now.hour < 18:
            return False
        return True
    if asset in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]:
        # Spot FX: closed from Friday 17:00 ET until Sunday 17:00 ET
        if now.weekday() == 4 and now.hour >= 17:
            return False
        if now.weekday() == 5:
            return False
        if now.weekday() == 6 and now.hour < 17:
            return False
        return True
    return True
