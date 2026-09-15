import json, time
with open('backend/data/trades_history.json', 'r') as f:
    trades = json.load(f)

fixed = 0
for t in trades:
    if t.get('result') == 'CLOSED_FLAT' and t.get('exit_reason') == 'KALSHI_POSITION_RECONCILED':
        close_epoch = float(t.get('close_epoch') or 0)
        if time.time() < close_epoch:  # market is still live!
            t['status'] = 'OPEN'
            t['result'] = 'PENDING'
            del t['exit_reason']
            if 'closed_at' in t: del t['closed_at']
            fixed += 1
            print("Restored OPEN trade:", t.get('id'), t.get('ticker'))

with open('backend/data/trades_history.json', 'w') as f:
    json.dump(trades, f, indent=2)
print(f"Restored {fixed} active trades.")
