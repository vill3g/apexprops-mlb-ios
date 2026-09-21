import json

try:
    with open('backend/data/trades_history.json', 'r') as f:
        trades = json.load(f)
    
    recent = trades[-10:]
    for t in recent:
        ts = t.get('timestamp')
        direction = t.get('direction')
        pnl = t.get('pnl')
        ml_prob = t.get('market_snapshot', {}).get('probability_percent')
        factors = t.get('market_snapshot', {}).get('decision_factors', [])
        print(f"[{ts}] {direction} PNL: {pnl} | PROB: {ml_prob}")
        for fac in factors:
            print(f"  - {fac}")
except Exception as e:
    print(e)
