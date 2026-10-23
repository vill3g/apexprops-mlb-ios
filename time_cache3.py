import time
import backend.engine.kalshi_events_cache as cache

start = time.time()
cache.update_events_cache()
for k, v in cache._GLOBAL_EVENTS_CACHE.items():
    if "NHL" in k and len(v) > 0:
        print(f"{k}: {len(v)}")
