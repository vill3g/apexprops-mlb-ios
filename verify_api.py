import sys
import asyncio

from backend.routes.engine import api_sports_events
try:
    res = api_sports_events(sport="TEN", filter_type="events")
    events = res.get("events", [])
    print(f"Total Tennis Events: {len(events)}")
    for i, e in enumerate(events[:5]):
        print(f"{i+1}. {e.get('matchup')} | AI Pick: {e.get('ai_pick')} | Time: {e.get('game_time')} | Strike: {e.get('strike_details')}")
except Exception as ex:
    print(f"Error: {ex}")
