from backend.engine.multi_asset_fetcher import fetch_asset_candles

for asset in ['ETH', 'GOLD', 'NDQ']:
    try:
        df = fetch_asset_candles(asset, '15m', limit=5)
        print(f'{asset}: fetched {len(df)} candles. Last Close: {df.iloc[-1]["close"]}')
    except Exception as e:
        print(f'Error for {asset}: {e}')
