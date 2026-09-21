import time
import pandas as pd
import numpy as np
import sys
sys.path.append('.')
from backend.btc.data_fetcher import fetch_candles

def compute_trailing_poc_slow(df: pd.DataFrame, window: int = 96) -> pd.Series:  
    pocs = []  
    for i in range(len(df)):  
        if i < 10:  
            pocs.append(df['close'].iloc[i])  
            continue  
        start = max(0, i - window + 1)  
        sub = df.iloc[start:i+1]  
        min_p = sub['low'].min()  
        max_p = sub['high'].max()  
        bins = np.linspace(min_p, max_p, 50)  
        vol_profile = np.zeros(49)  
        for _, row in sub.iterrows():  
            idx = np.digitize((row['high']+row['low']+row['close'])/3.0, bins) - 1  
            idx = max(0, min(48, idx))  
            vol_profile[idx] += row['volume']  
        poc_idx = np.argmax(vol_profile)  
        pocs.append((bins[poc_idx] + bins[poc_idx+1]) / 2.0)  
    return pd.Series(pocs, index=df.index)

def compute_trailing_poc_fast(df: pd.DataFrame, window: int = 96) -> pd.Series:
    pocs = np.zeros(len(df))
    close_vals = df['close'].values
    high_vals = df['high'].values
    low_vals = df['low'].values
    vol_vals = df['volume'].values
    typ_price = (high_vals + low_vals + close_vals) / 3.0
    
    for i in range(len(df)):
        if i < 10:
            pocs[i] = close_vals[i]
            continue
            
        start = max(0, i - window + 1)
        # Slices
        sub_high = high_vals[start:i+1]
        sub_low = low_vals[start:i+1]
        sub_typ = typ_price[start:i+1]
        sub_vol = vol_vals[start:i+1]
        
        min_p = np.min(sub_low)
        max_p = np.max(sub_high)
        
        if min_p == max_p:
            pocs[i] = min_p
            continue
            
        bins = np.linspace(min_p, max_p, 50)
        idx = np.digitize(sub_typ, bins) - 1
        idx = np.clip(idx, 0, 48)
        
        vol_profile = np.bincount(idx, weights=sub_vol, minlength=49)
        poc_idx = np.argmax(vol_profile)
        pocs[i] = (bins[poc_idx] + bins[poc_idx+1]) / 2.0
        
    return pd.Series(pocs, index=df.index)

df = fetch_candles("15m", limit=1000)

t0 = time.time()
compute_trailing_poc_slow(df)
print("Slow took:", time.time()-t0)

t0 = time.time()
compute_trailing_poc_fast(df)
print("Fast took:", time.time()-t0)
