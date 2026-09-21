import json

with open('backend/data/rl_shadow_trades.json', 'r') as f:
    trades = json.load(f)

ticker = "KXBTC15M-26SEP210845-45"
is_dup = False
for t in trades:
    print("Checking", t.get("ticker"), t.get("status"))
    if t.get("ticker") == ticker and t.get("status") == "OPEN":
        is_dup = True
        break

print("IS DUP:", is_dup)
