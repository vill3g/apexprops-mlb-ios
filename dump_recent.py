import os, sys, json
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
with open("backend/data/trades_history.json") as f:
    history = json.load(f)

live = [t for t in history if t.get("mode", "") == "LIVE"][-3:]

print(json.dumps(live, indent=2))
