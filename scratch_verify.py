import json

try:
    with open('backend/data/trades_history.json', 'r') as f:
        trades = json.load(f)
    print('\n--- LAST 10 TRADES ---')
    last_10 = trades[-10:]
    for t in last_10:
        print(f"ID: {t.get('id')} | Dir: {t.get('prediction_direction')} | Entry: {t.get('entry_price')} | Result: {t.get('result', 'N/A')} | PnL: {t.get('pnl')} | Conf: {t.get('probability_percent')}% | Market: {t.get('ticker')}")

except Exception as e:
    print('Error:', e)
