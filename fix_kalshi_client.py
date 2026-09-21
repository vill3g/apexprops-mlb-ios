import re

with open('backend/btc/kalshi_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('if _kalshi_cache and (now - _kalshi_cache_time) < CACHE_TTL_SEC:\n            return _kalshi_cache',
'''if series_ticker in _kalshi_cache and (now - _kalshi_cache_times.get(series_ticker, 0)) < CACHE_TTL_SEC:
            return _kalshi_cache.get(series_ticker)''')

content = content.replace('global _kalshi_cache, _kalshi_cache_time', 'global _kalshi_cache, _kalshi_cache_times')
content = content.replace('_kalshi_cache_time = time.time()', '_kalshi_cache_times[series_ticker] = time.time()')
content = content.replace('return _kalshi_cache or {}', 'return _kalshi_cache.get(series_ticker) or {}')

with open('backend/btc/kalshi_client.py', 'w', encoding='utf-8') as f:
    f.write(content)
