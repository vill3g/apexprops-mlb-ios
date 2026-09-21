import json
import os

fpath = 'backend/data/rl_shadow_trades.json'
if os.path.exists(fpath):
    with open(fpath, 'r') as f:
        trades = json.load(f)
    
    unique_trades = []
    seen = set()
    for t in trades:
        k = t.get('ticker')
        if k not in seen:
            seen.add(k)
            unique_trades.append(t)
    
    with open(fpath, 'w') as f:
        json.dump(unique_trades, f, indent=2)
    
    print(f"Cleaned up duplicates. Left with {len(unique_trades)} unique trades.")
