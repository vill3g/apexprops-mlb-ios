with open('backend/main.py', 'r', encoding='utf-8') as f:
    c = f.read()

old_ticker = """        if asset.upper() in ACTIVE_PAIRS:
            from backend.forex.data_fetcher import get_forex_ticker
            return JSONResponse(sanitize_btc_json(get_forex_ticker(asset.upper())))
        ticker = get_asset_ticker(asset)
        return JSONResponse(sanitize_btc_json(ticker))"""

new_ticker = """        if asset.upper() in ACTIVE_PAIRS:
            from backend.forex.data_fetcher import get_forex_ticker
            return JSONResponse(sanitize_btc_json(get_forex_ticker(asset.upper())))
        ticker = get_asset_ticker(asset.upper())
        return JSONResponse(sanitize_btc_json(ticker))"""

c = c.replace(old_ticker, new_ticker)

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(c)
