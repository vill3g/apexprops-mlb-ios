import os, sys, json
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
with open("backend/data/trades_history.json") as f:
    history = json.load(f)
for t in history[-5:]:
    print(t["timestamp"], "mode:", t["mode"], "is_auto:", t["is_auto"], "id:", t["id"])
