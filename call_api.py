import sys
sys.path.append('.')
from backend.routes.engine import api_sports_events
import json

events = api_sports_events(filter="TEN")
for e in events:
    print(e.get("ticker"), e.get("game_time"))
