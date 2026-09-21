import json

try:
    with open('backend/data/trades_history.json', 'r') as f:
        trades = json.load(f)
    
    recent = trades[-6:]
    for t in recent:
        ts = t.get('timestamp')
        direction = t.get('direction')
        pnl = t.get('pnl')
        ml_reasoning = t.get('market_snapshot', {}).get('decision_factors', [])
        # Actually I need the log file to see what `evaluate_next_15m_contract` printed out!
        print(f"[{ts}] Dir: {direction}, PNL: {pnl}")
except Exception as e:
    print(e)
