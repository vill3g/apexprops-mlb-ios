import time
from backend.routes.engine import api_sports_events

s = time.time()
print("Starting...")
api_sports_events()
print("Done in", time.time() - s)
