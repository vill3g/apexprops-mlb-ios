import re

with open('backend/routes/engine.py', 'r', encoding='utf-8') as f:
    code = f.read()

sports_stub = '''
        if asset.upper() in ["NFL", "MLB", "NBA", "UFC"]:
            return JSONResponse({
                "price": 0.0,
                "target_price": 0.0,
                "target_source": "SPORTS",
                "delta": 0.0,
                "delta_pct": 0.0,
                "status": "NEUTRAL",
                "seconds_left": 0,
                "formatted_countdown": "--:--",
                "last_5_targets": [],
                "streak_summary": "--",
                "volume_24h": 0.0,
                "kalshi": {
                    "is_synthetic": False,
                    "source": "Sports Bridge Engine",
                    "yes_prob": 50,
                    "no_prob": 50,
                    "volume_24h": 0
                }
            })
'''

if 'asset.upper() in ["NFL", "MLB", "NBA", "UFC"]:' not in code:
    code = code.replace('if asset.upper() in ACTIVE_PAIRS:', sports_stub + '\n        if asset.upper() in ACTIVE_PAIRS:')

# Also patch api_btc_ticker
ticker_stub = '''
        if asset.upper() in ["NFL", "MLB", "NBA", "UFC"]:
            return JSONResponse({
                "price": 0.0,
                "volume_24h": 0.0,
                "change_24h": 0.0,
                "change_pct_24h": 0.0
            })
'''
if 'asset.upper() in ["NFL", "MLB", "NBA", "UFC"]:' not in code.split('def api_btc_ticker')[1]:
    # Need to target the second ACTIVE_PAIRS
    parts = code.split('def api_btc_ticker(asset: str):')
    parts[1] = parts[1].replace('if asset.upper() in ACTIVE_PAIRS:', ticker_stub + '\n        if asset.upper() in ACTIVE_PAIRS:', 1)
    code = parts[0] + 'def api_btc_ticker(asset: str):' + parts[1]

# Also patch api_btc_countdown
countdown_stub = '''
        if asset.upper() in ["NFL", "MLB", "NBA", "UFC"]:
            return JSONResponse({
                "seconds_left": 0,
                "formatted": "--:--",
                "next_candle_ms": 0,
                "interval": timeframe
            })
'''
if 'asset.upper() in ["NFL", "MLB", "NBA", "UFC"]:' not in code.split('def api_btc_countdown')[1]:
    parts = code.split('def api_btc_countdown(asset: str, timeframe: str = "15m"):')
    parts[1] = parts[1].replace('if asset.upper() in ACTIVE_PAIRS:', countdown_stub + '\n        if asset.upper() in ACTIVE_PAIRS:', 1)
    code = parts[0] + 'def api_btc_countdown(asset: str, timeframe: str = "15m"):' + parts[1]

# Also patch api_btc_kalshi
kalshi_stub = '''
        if asset.upper() in ["NFL", "MLB", "NBA", "UFC"]:
            return JSONResponse({
                "is_synthetic": False,
                "source": "Sports Bridge Engine",
                "yes_prob": 50,
                "no_prob": 50,
                "volume_24h": 0
            })
'''
if 'asset.upper() in ["NFL", "MLB", "NBA", "UFC"]:' not in code.split('def api_btc_kalshi')[1]:
    parts = code.split('def api_btc_kalshi(asset: str):')
    parts[1] = parts[1].replace('if asset.upper() in ACTIVE_PAIRS:', kalshi_stub + '\n        if asset.upper() in ACTIVE_PAIRS:', 1)
    code = parts[0] + 'def api_btc_kalshi(asset: str):' + parts[1]

# Also patch api_btc_chart
chart_stub = '''
        if asset.upper() in ["NFL", "MLB", "NBA", "UFC"]:
            return JSONResponse({"data": []})
'''
if 'asset.upper() in ["NFL", "MLB", "NBA", "UFC"]:' not in code.split('def api_btc_chart')[1]:
    parts = code.split('def api_btc_chart(asset: str, timeframe: str = "15m", limit: int = 150):')
    parts[1] = parts[1].replace('if asset.upper() in ACTIVE_PAIRS:', chart_stub + '\n        if asset.upper() in ACTIVE_PAIRS:', 1)
    code = parts[0] + 'def api_btc_chart(asset: str, timeframe: str = "15m", limit: int = 150):' + parts[1]


with open('backend/routes/engine.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Patched routes for sports stubs')
