import time
import sys
sys.path.append('.')
from backend.btc.data_fetcher import fetch_candles
from backend.btc.indicators import add_all_indicators
from backend.btc.pattern_detector import detect_candlestick_patterns
from backend.btc.news_fetcher import get_news_sentiment_summary
from backend.engine.multi_asset_fetcher import get_cb_orderbook, get_binance_futures_data
from backend.btc.fng_fetcher import get_fng_index

def prof():
    df = fetch_candles("15m", limit=1000)
    
    t0 = time.time()
    add_all_indicators(df)
    print("add_all_indicators took", time.time()-t0)
    
    t0 = time.time()
    detect_candlestick_patterns(df)
    print("detect_candlestick_patterns took", time.time()-t0)
    
    t0 = time.time()
    get_news_sentiment_summary()
    print("get_news_sentiment_summary took", time.time()-t0)
    
    t0 = time.time()
    get_cb_orderbook()
    print("get_cb_orderbook took", time.time()-t0)
    
    t0 = time.time()
    get_binance_futures_data()
    print("get_binance_futures_data took", time.time()-t0)
    
    t0 = time.time()
    get_fng_index()
    print("get_fng_index took", time.time()-t0)

prof()
