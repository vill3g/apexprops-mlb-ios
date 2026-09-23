import json
try:
    d = json.load(open('backend/data/trades_history.json', 'r'))
    for t in d[-8:]:
        print(f"{t.get('timestamp')} | ID: {t.get('id')} | Dir: {t.get('direction')} | Ticker: {t.get('ticker')}")
except Exception as e:
    print('Error:', e)
