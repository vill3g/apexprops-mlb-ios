import time
from datetime import datetime
import pandas as pd
import yfinance as yf
import pytz
import logging

logger = logging.getLogger(__name__)

# Map internal pairs to Yahoo Finance tickers
FOREX_TICKERS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X"
}

TIMEFRAMES = {
    "1m": {"yf": "1m", "period": "5d"},
    "5m": {"yf": "5m", "period": "60d"},
    "15m": {"yf": "15m", "period": "60d"},
    "1h": {"yf": "60m", "period": "1mo"},
    "4h": {"yf": "1h", "period": "1mo"},  # yf doesn't always have reliable 4h, fallback to 1h
    "1d": {"yf": "1d", "period": "1y"},
}

def fetch_forex_candles(pair: str, timeframe: str = "15m", limit: int = 300) -> pd.DataFrame:
    """Fetch OHLCV data for Forex pairs via Yahoo Finance."""
    symbol = FOREX_TICKERS.get(pair)
    if not symbol:
        raise ValueError(f"Unsupported pair: {pair}")
        
    cfg = TIMEFRAMES.get(timeframe, TIMEFRAMES["15m"])
    ticker = yf.Ticker(symbol)
    
    # yfinance fetches by period
    hist = ticker.history(period=cfg["period"], interval=cfg["yf"])
    if hist.empty:
        raise ValueError(f"Empty data returned for {symbol} at {timeframe}")
        
    hist = hist.reset_index()
    time_col = "Datetime" if "Datetime" in hist.columns else "Date"
    hist["time"] = pd.to_datetime(hist[time_col], utc=True).astype("int64") // 10**9
    hist = hist.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    
    df = hist[["time", "open", "high", "low", "close", "volume"]].sort_values("time").reset_index(drop=True)
    return df.tail(limit)

def get_forex_ticker(pair: str) -> dict:
    """Get real-time spot pricing and 24h stats."""
    try:
        df_1m = fetch_forex_candles(pair, "1m", limit=1)
        df_1d = fetch_forex_candles(pair, "1d", limit=2)
        
        if df_1d.empty:
            return {"price": 0.0, "change_24h": 0.0, "high_24h": 0.0, "low_24h": 0.0, "volume_24h": 0.0}
            
        latest_1d = df_1d.iloc[-1]
        curr_price = float(df_1m.iloc[-1]["close"]) if not df_1m.empty else float(latest_1d["close"])
        high = float(latest_1d["high"])
        low = float(latest_1d["low"])
        vol = float(latest_1d["volume"])
        
        prev_close = float(df_1d.iloc[-2]["close"]) if len(df_1d) > 1 else float(latest_1d["close"])
        change = ((curr_price - prev_close) / prev_close * 100) if prev_close else 0.0
        
        return {
            "price": curr_price,
            "change_24h": round(change, 4),
            "high_24h": round(high, 5),
            "low_24h": round(low, 5),
            "volume_24h": round(vol, 2)
        }
    except Exception as e:
        logger.error(f"Error fetching ticker for {pair}: {e}")
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
