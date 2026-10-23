import logging
import threading
import time
from datetime import datetime

import pandas as pd
import pytz
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

logger = logging.getLogger(__name__)

# Map internal pairs to Yahoo Finance tickers
FOREX_TICKERS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
}

TIMEFRAMES = {
    "1m": {"yf": "1m", "period": "2d"},
    "5m": {"yf": "5m", "period": "5d"},
    "15m": {"yf": "15m", "period": "5d"},
    "1h": {"yf": "60m", "period": "1mo"},
    "4h": {"yf": "60m", "period": "1mo"},
    "1d": {"yf": "1d", "period": "6mo"},
}

_FX_SESSION = requests.Session()
_FX_ADAPTER = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=Retry(total=2, backoff_factor=0.15))
_FX_SESSION.mount("https://", _FX_ADAPTER)
_FX_SESSION.mount("http://", _FX_ADAPTER)
_FX_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
})

_fx_candles_cache = {}
_fx_candles_lock = threading.Lock()
_FX_CANDLES_TTL = 4.0

_fx_ticker_cache = {}
_fx_ticker_lock = threading.Lock()
_FX_TICKER_TTL = 3.0


def _fetch_yahoo_v8_chart(symbol: str, interval: str, period: str, timeout: float = 3.5) -> dict:
    """Direct, thread-safe fetch from Yahoo Finance v8 chart JSON API."""
    last_err = None
    for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
        url = f"https://{host}/v8/finance/chart/{symbol}"
        try:
            resp = _FX_SESSION.get(url, params={"interval": interval, "range": period}, timeout=timeout)
            if resp.status_code == 200:
                payload = resp.json()
                results = (payload.get("chart") or {}).get("result")
                if results and isinstance(results, list) and results[0]:
                    return results[0]
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    raise ValueError(f"Empty Yahoo v8 chart response for {symbol} ({interval}, {period})")


def fetch_forex_candles(pair: str, timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:
    """Fetch OHLCV data for Forex pairs via Yahoo Finance v8 API with thread-safe caching and fallback."""
    pair = str(pair or "").upper().strip()
    symbol = FOREX_TICKERS.get(pair)
    if not symbol:
        raise ValueError(f"Unsupported pair: {pair}")

    tf = str(timeframe or "15m").lower().strip()
    cfg = TIMEFRAMES.get(tf, TIMEFRAMES["15m"])
    cache_key = (pair, tf)
    now = time.time()

    with _fx_candles_lock:
        cached = _fx_candles_cache.get(cache_key)
        if cached and (now - cached[0]) < _FX_CANDLES_TTL and not cached[1].empty:
            return cached[1].tail(limit).copy().reset_index(drop=True)

    df = None
    # Primary: Direct Yahoo v8 JSON API (fast, thread-safe, returns exact Unix second timestamps)
    try:
        res = _fetch_yahoo_v8_chart(symbol, interval=cfg["yf"], period=cfg["period"])
        timestamps = res.get("timestamp") or []
        quote_list = ((res.get("indicators") or {}).get("quote") or [{}])
        quote = quote_list[0] if quote_list else {}
        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []

        records = []
        n = len(timestamps)
        for i in range(n):
            t = timestamps[i]
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
    except Exception as e:
        logger.debug(f"[ForexFetcher] Yahoo v8 direct chart fallback for {pair} {tf}: {e}")

    # Secondary fallback: yfinance library with unit-safe Unix timestamp conversion
    if df is None or df.empty:
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=cfg["period"], interval=cfg["yf"])
            if not hist.empty:
                hist = hist.reset_index()
                time_col = "Datetime" if "Datetime" in hist.columns else "Date"
                dt_series = pd.to_datetime(hist[time_col], utc=True)
                hist["time"] = ((dt_series - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1s")).astype("int64")
                hist = hist.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
                df = hist[["time", "open", "high", "low", "close", "volume"]].dropna(subset=["open", "high", "low", "close"])
                df = df.drop_duplicates(subset=["time"], keep="last").sort_values("time").reset_index(drop=True)
        except Exception as yf_err:
            logger.debug(f"[ForexFetcher] yfinance fallback error for {pair} {tf}: {yf_err}")

    if df is None or df.empty:
        with _fx_candles_lock:
            if cached and not cached[1].empty:
                return cached[1].tail(limit).copy().reset_index(drop=True)
        raise ValueError(f"Empty data returned for {symbol} at {tf}")

    if tf == "4h" and len(df) >= 4:
        df["bucket"] = (df["time"] // 14400) * 14400
        df = df.groupby("bucket", as_index=False).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).rename(columns={"bucket": "time"}).sort_values("time").reset_index(drop=True)

    with _fx_candles_lock:
        _fx_candles_cache[cache_key] = (now, df)

    return df.tail(limit).copy().reset_index(drop=True)


def get_forex_ticker(pair: str) -> dict:
    """Get real-time spot pricing and 24h stats with fast in-memory caching."""
    pair = str(pair or "").upper().strip()
    symbol = FOREX_TICKERS.get(pair)
    if not symbol:
        return {"price": 0.0, "change_24h": 0.0, "high_24h": 0.0, "low_24h": 0.0, "volume_24h": 0.0}

    now = time.time()
    with _fx_ticker_lock:
        cached = _fx_ticker_cache.get(pair)
        if cached and (now - cached[0]) < _FX_TICKER_TTL and cached[1].get("price", 0) > 0:
            return dict(cached[1])

    try:
        res = _fetch_yahoo_v8_chart(symbol, interval="15m", period="5d", timeout=3.0)
        meta = res.get("meta") or {}
        quote_list = ((res.get("indicators") or {}).get("quote") or [{}])
        quote = quote_list[0] if quote_list else {}
        closes = [float(c) for c in (quote.get("close") or []) if c is not None]
        highs = [float(h) for h in (quote.get("high") or []) if h is not None]
        lows = [float(l) for l in (quote.get("low") or []) if l is not None]

        curr_price = float(meta.get("regularMarketPrice") or (closes[-1] if closes else 0.0))
        prev_close = float(meta.get("chartPreviousClose") or meta.get("previousClose") or (closes[-96] if len(closes) >= 96 else (closes[0] if closes else curr_price)))
        recent_highs = highs[-96:] if highs else [curr_price]
        recent_lows = lows[-96:] if lows else [curr_price]
        high_24h = float(meta.get("regularMarketDayHigh") or max(recent_highs))
        low_24h = float(meta.get("regularMarketDayLow") or min(recent_lows))
        vol_24h = float(meta.get("regularMarketVolume") or 0.0)
        change = ((curr_price - prev_close) / prev_close * 100.0) if prev_close else 0.0

        out = {
            "price": round(curr_price, 5),
            "change_24h": round(change, 4),
            "high_24h": round(high_24h, 5),
            "low_24h": round(low_24h, 5),
            "volume_24h": round(vol_24h, 2),
        }
        with _fx_ticker_lock:
            _fx_ticker_cache[pair] = (now, out)
        return dict(out)
    except Exception as e:
        logger.debug(f"[ForexFetcher] Fast ticker fallback for {pair}: {e}")
        with _fx_ticker_lock:
            if cached and cached[1].get("price", 0) > 0:
                return dict(cached[1])
        try:
            df = fetch_forex_candles(pair, "15m", limit=96)
            if not df.empty:
                curr_price = float(df.iloc[-1]["close"])
                prev_close = float(df.iloc[0]["close"])
                change = ((curr_price - prev_close) / prev_close * 100.0) if prev_close else 0.0
                out = {
                    "price": round(curr_price, 5),
                    "change_24h": round(change, 4),
                    "high_24h": round(float(df["high"].max()), 5),
                    "low_24h": round(float(df["low"].min()), 5),
                    "volume_24h": round(float(df["volume"].sum()), 2),
                }
                with _fx_ticker_lock:
                    _fx_ticker_cache[pair] = (now, out)
                return dict(out)
        except Exception as inner_e:
            logger.error(f"Error fetching ticker for {pair}: {inner_e}")

        return {"price": 0.0, "change_24h": 0.0, "high_24h": 0.0, "low_24h": 0.0, "volume_24h": 0.0}


def is_forex_market_open() -> bool:
    """Forex markets are 24/5. Closed from Friday 5 PM EST to Sunday 5 PM EST."""
    now = datetime.now(pytz.timezone("America/New_York"))
    # Friday is 4, Sunday is 6
    if now.weekday() == 4 and now.hour >= 17:
        return False
    if now.weekday() == 5:
        return False
    if now.weekday() == 6 and now.hour < 17:
        return False
    return True
