import time
import sys
sys.path.append('.')
from backend.btc.data_fetcher import fetch_candles

def prof():
    t0 = time.time()
    df_15 = fetch_candles("15m", limit=1000)
    print("15m took", time.time()-t0)
    
    t0 = time.time()
    df_1h = fetch_candles("1h", limit=50)
    print("1h took", time.time()-t0)
    
    t0 = time.time()
    df_4h = fetch_candles("4h", limit=50)
    print("4h took", time.time()-t0)

prof()
