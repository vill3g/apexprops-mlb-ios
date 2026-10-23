import requests, time, collections
from datetime import datetime
from zoneinfo import ZoneInfo
r = requests.get("http://127.0.0.1:8058/api/engine/sports/events?public=1", timeout=60)
ev = r.json().get("events", [])
now = time.time()
today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
print("events", len(ev), "today", today)
print("sample keys", sorted(ev[0].keys())[:40] if ev else None)
cnt = collections.Counter()
rows = []
for e in ev:
    ap = e.get("ai_prediction")
    st = e.get("start_epoch") or e.get("start_time")
    sp = e.get("sport")
    live = e.get("is_live") or e.get("live")
    cnt[(sp, bool(ap), "live" if live else "pre")] += 1
    if ap:
        rows.append((sp, e.get("title") or e.get("event_title"), st, live, ap.get("predicted_team") or ap.get("pick"), ap.get("confidence_pct"), ap.get("edge_pct")))
for k, v in sorted(cnt.items(), key=lambda kv: str(kv[0])):
    print(k, v)
print("--- events WITH AI pick (sample):")
for row in rows[:25]:
    print(row)
