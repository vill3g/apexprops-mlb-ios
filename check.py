import json
trades = json.load(open('backend/data/trades_history.json'))
valid = [t for t in trades if t.get('market_snapshot', {}).get('raw_features')]
print('Valid trades:', len(valid))
