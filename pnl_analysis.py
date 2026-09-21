import json, pandas as pd; trades = json.load(open('backend/data/trades_history.json')); df = pd.DataFrame(trades); print(df.groupby('trade_source')['pnl'].sum())
