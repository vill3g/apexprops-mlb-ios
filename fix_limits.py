import re

def patch_file(fpath):
    with open(fpath, 'r', encoding='utf-8') as f:
        text = f.read()

    # Replace limit=1000 with limit=350
    text = text.replace('fetch_candles(self.asset, timeframe="1m", limit=1000)', 'fetch_candles(self.asset, timeframe="1m", limit=350)')
    text = text.replace('fetch_candles(self.asset, timeframe="15m", limit=1000)', 'fetch_candles(self.asset, timeframe="15m", limit=350)')
    text = text.replace('fetch_candles(self.asset, "1m", limit=1000)', 'fetch_candles(self.asset, "1m", limit=350)')
    text = text.replace('fetch_candles(self.asset, "15m", limit=1000)', 'fetch_candles(self.asset, "15m", limit=350)')
    text = text.replace('fetch_candles(self.asset, timeframe="1m", limit=500)', 'fetch_candles(self.asset, timeframe="1m", limit=350)')

    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(text)

patch_file('backend/btc/auto_executor/executor.py')
patch_file('backend/btc/auto_executor/saas_broadcaster.py')
patch_file('backend/btc/auto_executor/stop_manager.py')

print("Limits optimized to 350 for MOMENTUM_SURFER")
