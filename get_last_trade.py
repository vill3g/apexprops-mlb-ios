import json
try:
    with open(" backend/data/trades_history.json\, encoding=\utf-8\) as f:
 trades = json.load(f)
 if trades:
 print(json.dumps(trades[-1], indent=2))
 else:
 print(\No trades found.\)
except Exception as e:
 print(e)

