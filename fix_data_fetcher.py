import re

# Fix data_fetcher.py RuntimeError
df_fetcher_path = 'backend/btc/data_fetcher.py'
with open(df_fetcher_path, 'r', encoding='utf-8') as f:
    df_text = f.read()

# Replace get_btc_ticker fetch_candles outside try-except
new_get_btc_ticker = """
    with _ticker_lock:
        if _ticker_cache["data"]:
            return _ticker_cache["data"]
    try:
        candles = fetch_candles(timeframe="15m", limit=2)
    except Exception as e:
        logger.warning(f"Ticker fallback fetch failed: {e}")
        return {"price": 0.0, "open_24h": 0.0, "high_24h": 0.0, "low_24h": 0.0, "volume_24h": 0.0, "change_24h": 0.0, "source": "NoData"}

    if candles is None or len(candles) == 0:
"""
df_text = df_text.replace(
    '    with _ticker_lock:\n        if _ticker_cache["data"]:\n            return _ticker_cache["data"]\n    candles = fetch_candles(timeframe="15m", limit=2)\n    if candles is None or len(candles) == 0:',
    new_get_btc_ticker
)

with open(df_fetcher_path, 'w', encoding='utf-8') as f:
    f.write(df_text)

print("data_fetcher.py fixed")
