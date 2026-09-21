import json, pandas as pd; trades = json.load(open('backend/data/trades_history.json')); df = pd.DataFrame(trades); print(df[['timestamp', 'trade_source', 'result', 'pnl']].tail(15))
