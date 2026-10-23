import time
from backend.routes.engine import api_sports_events

print("Profiling...")
s = time.time()
res = api_sports_events()
print("Total:", time.time() - s)
