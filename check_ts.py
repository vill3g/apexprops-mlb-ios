import json

try:
    with open('backend/data/trades_history.json', 'r') as f:
        trades = json.load(f)
    
    recent = trades[-20:]
    for t in recent:
        ts = t.get('timestamp')
        res = t.get('result')
        pnl = t.get('pnl')
        ml_prob = t.get('ml_prob', 0.5)
        ml_dir = "ABOVE" if ml_prob > 0.5 else "BELOW"
        print(f"[{ts}] {ml_dir} {ml_prob} -> {res} {pnl}")
except Exception as e:
    print(e)
