import os, sys, json
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
with open("backend/data/trades_history.json") as f:
    history = json.load(f)
live = [t for t in history if t.get("mode", "") == "LIVE"]
for t in live[-3:]:
    print(t["timestamp"], t["ticker"], t["side"], t["count"], "cost:", t["cost"], "result:", t.get("result"), "pnl:", t.get("pnl"))
