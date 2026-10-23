from backend.btc.kalshi_trader import kalshi_trader
from backend.engine.kalshi_market_cache import get_market_cache_instance
import backend.btc.market_results as mr

cache = get_market_cache_instance()

tickers = ['KXETH15M-26OCT211400-00', 'KXBTC15M-26OCT211400-00']
for tk in tickers:
    q = kalshi_trader.get_market_quote(tk)
    m = cache.get_market(tk) if cache else None
    res = mr.get_result(tk)
    print(tk)
    print('  quote:', q)
    print('  cache:', m is not None)
    print('  settled result:', res)
