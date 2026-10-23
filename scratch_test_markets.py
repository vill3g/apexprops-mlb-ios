from backend.engine.kalshi_market_cache import get_market_cache_instance
cache = get_market_cache_instance()
print("Market for KXETH15M-26OCT211400-00:", cache.get_market("KXETH15M-26OCT211400-00"))
print("Market for KXBTC15M-26OCT211400-00:", cache.get_market("KXBTC15M-26OCT211400-00"))
