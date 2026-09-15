import json

with open('backend/data/trades_history.json', 'r') as f:
    trades = json.load(f)

live = [t for t in trades if t.get('mode','').upper() == 'LIVE'
        and t.get('result') in ('WIN','LOSS')
        and t.get('status') in ('SETTLED','CLOSED')]

conflicts = [t for t in live if 'Model Conflict' in str(t.get('catalysts',''))]
conflict_losses = [t for t in conflicts if t.get('result') == 'LOSS']

for t in conflict_losses:
    print(f"  ID: {t.get('id')} | Dir: {t.get('direction')} | PNL: {t.get('pnl')}")
