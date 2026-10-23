import time
from backend.engine.kalshi_events_cache import update_events_cache, _GLOBAL_EVENTS_CACHE

start = time.time()
update_events_cache()
print("Took:", time.time() - start)
print("Keys:", len(_GLOBAL_EVENTS_CACHE))
