import requests
import pandas as pd
import yfinance as yf
from datetime import datetime

def _fetch_from_yfinance(asset: str, timeframe: str = '15m', limit: int = 300) -> pd.DataFrame:
    period_map = {'1m': '2d', '5m': '5d', '15m': '5d', '1h': '1mo', '4h': '1mo', '1d': '1y'}
    period = period_map.get(timeframe, '5d')

    ticker_map = {
        'BTC': 'BTC-USD',
        'ETH': 'ETH-USD',
        'GOLD': 'GC=F',
        'NDQ': 'NQ=F'
    }
    yf_symbol = ticker_map.get(asset, 'BTC-USD')
    
    ticker = yf.Ticker(yf_symbol)
    hist = ticker.history(period=period, interval=timeframe)
    if hist.empty:
        raise ValueError('yfinance returned empty data')
    
    hist = hist.reset_index()
    time_col = 'Datetime' if 'Datetime' in hist.columns else 'Date'
    
    hist['time'] = pd.to_datetime(hist[time_col]).astype('int64') // 10**9
    hist = hist.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
    df = hist[['time', 'open', 'high', 'low', 'close', 'volume']].sort_values('time').reset_index(drop=True)
    return df

try:
    print('NDQ:', _fetch_from_yfinance('NDQ').head(2))
    print('GOLD:', _fetch_from_yfinance('GOLD').head(2))
except Exception as e:
    print('Error:', e)
