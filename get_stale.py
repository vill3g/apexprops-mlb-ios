import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.routes.engine import _fetch_kalshi_series_events, extract_sports_event_date_and_time

events = []
for series in ["KXATPMATCH", "KXWTAMATCH"]:
    events.extend(_fetch_kalshi_series_events(series))

print(f"Total tennis events on Kalshi: {len(events)}")
now_et = datetime.now(ZoneInfo("America/New_York"))
today_et = now_et.date()

stale_count = 0
for e in events:
    event_ticker = e.get('event_ticker', '')
    ev_date, start_epoch = extract_sports_event_date_and_time(event_ticker, event_obj=e)
    if ev_date and (today_et - ev_date).days >= 1:
        print(f"Stale (older than 1 day): {event_ticker} ({ev_date})")
        stale_count += 1
print(f"Total stale: {stale_count}")
