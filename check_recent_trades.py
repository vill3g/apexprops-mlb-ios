import json
with open('backend/data/trades_history.json', 'r') as f:
    trades = json.load(f)

for t in trades[-5:]:
    print(f"ID: {t.get('id')}, Ticker: {t.get('ticker')}, Mode: {t.get('mode')}, Status: {t.get('status')}, Result: {t.get('result')}, PNL: {t.get('pnl')}")
