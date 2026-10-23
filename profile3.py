import time
from backend.routes.engine import api_sports_events, get_series_events, get_milestone_map
print("Fetching events from cache directly...")
s = time.time()
get_milestone_map()
print("Milestones:", time.time() - s)

s = time.time()
get_series_events("KXNHL")
print("Series KXNHL:", time.time() - s)

s = time.time()
api_sports_events()
print("api_sports_events:", time.time() - s)
