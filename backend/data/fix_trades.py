import json
import time
import os

path = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\data\trades_history.json"
with open(path, "r") as f:
    trades = json.load(f)

changed = 0
now = time.time()
for t in trades:
    if t.get("status") == "OPEN":
        # Check if trade is old
        epoch = t.get("close_epoch", 0)
        if epoch == 0 or (now - epoch > 3600):
            t["status"] = "CLOSED"
            t["result"] = "REFUNDED (BUGGED TRADE)"
            changed += 1

if changed > 0:
    with open(path, "w") as f:
        json.dump(trades, f, indent=2)
    print(f"Fixed {changed} stuck trades.")
else:
    print("No stuck trades found.")
