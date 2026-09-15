import json
from collections import Counter

with open('backend/data/trades_history.json', 'r') as f:
    trades = json.load(f)

valid_trades = [t for t in trades if t.get('status') in ['SETTLED', 'CLOSED'] and t.get('result') in ['WIN', 'LOSS']]

best_chunk = valid_trades[100:120]
print("Best Chunk Timestamps:")
print(best_chunk[0]['timestamp'], "to", best_chunk[-1]['timestamp'])

for t in best_chunk:
    if 'AUTO' in str(t.get('trade_source')):
        print(t['timestamp'], "| Source:", t.get('trade_source'), "| Grade:", t.get('conviction_grade'), "| Catalyst:", t.get('catalysts'))
