import json
with open('backend/data/trades_history.json', 'r') as f:
    trades = json.load(f)

for t in trades:
    if t.get('result') == 'CLOSED_FLAT' and t.get('exit_reason') == 'KALSHI_POSITION_RECONCILED':
        # Revert
        print(f"Reverting {t.get('id')}")
        t['status'] = 'OPEN'
        t['result'] = 'PENDING'
        if 'exit_reason' in t: del t['exit_reason']
        if 'closed_at' in t: del t['closed_at']

with open('backend/data/trades_history.json', 'w') as f:
    json.dump(trades, f, indent=2)
print('Reverted.')
