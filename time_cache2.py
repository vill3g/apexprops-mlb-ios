import time
import backend.engine.kalshi_events_cache as cache

start = time.time()
cache.update_events_cache()
print("Took:", time.time() - start)
print("Keys:", len(cache._GLOBAL_EVENTS_CACHE))
if "KXNHLGAME" in cache._GLOBAL_EVENTS_CACHE:
    print("NHL Events:", len(cache._GLOBAL_EVENTS_CACHE["KXNHLGAME"]))
