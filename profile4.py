import time
from backend.engine.kalshi_events_cache import get_series_events, get_milestone_map
from backend.routes.engine import api_sports_events

s = time.time()
print("Milestones...")
get_milestone_map()
print("Took", time.time() - s)

s = time.time()
print("Series events KXNHL...")
get_series_events("KXNHL")
print("Took", time.time() - s)

s = time.time()
print("api_sports_events...")
api_sports_events()
print("Took", time.time() - s)
