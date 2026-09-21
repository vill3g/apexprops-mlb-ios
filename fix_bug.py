import re

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('df_c = fetch_candles("15m", limit=30)', 'df_c = fetch_candles(self.asset, timeframe="15m", limit=30)')

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
