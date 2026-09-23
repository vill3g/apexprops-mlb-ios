import os, json

data_dir = os.path.join('backend', 'data', 'users')
if os.path.exists(data_dir):
    for uid in os.listdir(data_dir):
        hist_path = os.path.join(data_dir, uid, 'trades_history.json')
        if os.path.exists(hist_path):
            with open(hist_path, 'r') as f:
                trades = json.load(f)
            recent = trades[-5:] if len(trades) > 5 else trades
            for t in recent:
                print("User", uid,
                      "| ticker=", t.get("ticker"),
                      "| side=", t.get("side"),
                      "| status=", t.get("status"),
                      "| reason=", t.get("reason"),
                      "| pnl=", t.get("pnl"),
                      "| entry=", t.get("entry_price"))
