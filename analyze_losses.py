import json

try:
    with open('backend/data/trades_history.json', 'r') as f:
        trades = json.load(f)
    
    recent = trades[-20:]
    for t in recent:
        ts = t.get('timestamp')
        direction = t.get('direction')
        pnl = t.get('pnl')
        factors = t.get('market_snapshot', {}).get('decision_factors', [])
        ml_prob = t.get('market_snapshot', {}).get('probability_percent')
        print(f"[{ts}] {direction} PNL: {pnl} | PROB: {ml_prob} | Factors: {factors}")
except Exception as e:
    print(e)
