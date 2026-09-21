import time
import sys
import pandas as pd
sys.path.append('.')
from backend.btc.data_fetcher import fetch_candles
from backend.btc.indicators import compute_ema, compute_rsi, compute_macd, compute_bollinger_bands, compute_atr, compute_vwap, add_all_indicators

def prof():
    df = fetch_candles("15m", limit=1000)
    
    t0 = time.time()
    compute_ema(df["close"], 9)
    print("compute_ema took", time.time()-t0)
    
    t0 = time.time()
    compute_rsi(df["close"], 14)
    print("compute_rsi took", time.time()-t0)
    
    t0 = time.time()
    compute_macd(df["close"], 12, 26, 9)
    print("compute_macd took", time.time()-t0)
    
    t0 = time.time()
    compute_bollinger_bands(df["close"], 20, 2.0)
    print("compute_bollinger_bands took", time.time()-t0)
    
    t0 = time.time()
    compute_atr(df, 14)
    print("compute_atr took", time.time()-t0)
    
    t0 = time.time()
    compute_vwap(df)
    print("compute_vwap took", time.time()-t0)
    
    t0 = time.time()
    add_all_indicators(df)
    print("add_all_indicators took", time.time()-t0)

prof()
