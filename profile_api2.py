import time
from backend.routes.engine import api_sports_events

s = time.time()
print("Starting 1...")
api_sports_events()
print("Done 1 in", time.time() - s)

s = time.time()
print("Starting 2...")
api_sports_events()
print("Done 2 in", time.time() - s)
