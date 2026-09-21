import time
import sys
sys.path.append('.')
from backend.btc.analyzer import analyze_btc
from backend.btc.data_fetcher import fetch_candles

def prof():
    df = fetch_candles("15m", limit=1000)
    
    t0 = time.time()
    res = analyze_btc(df)
    print("analyze_btc took", time.time()-t0)

prof()
