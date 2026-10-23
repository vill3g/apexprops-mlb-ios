import requests

r = requests.get('http://127.0.0.1:8058/api/engine/sports/events?sport=NHL-nocache')
events = r.json().get('events', [])

picks_by_type = {}
total_nhl = 0

for e in events:
    total_nhl += 1
    if e.get("has_ai_prediction") and e.get("ai_prediction"):
        mtype = e.get("market_type", "Unknown")
        picks_by_type[mtype] = picks_by_type.get(mtype, 0) + 1

print(f"Total NHL Events returned: {total_nhl}")
print("NHL Picks by market type:")
for k, v in picks_by_type.items():
    print(f"  {k}: {v}")

start_epochs = [e.get("start_epoch") for e in events]
print("Start epochs valid:", all(se > 1000 for se in start_epochs if se is not None))
