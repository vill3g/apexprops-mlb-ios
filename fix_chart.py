import re

with open('backend/routes/engine.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Also patch api_chart_candles
chart_stub = '''
        if asset.upper() in ["NFL", "MLB", "NBA", "UFC"]:
            return JSONResponse({"data": []})
'''
if 'asset.upper() in ["NFL", "MLB", "NBA", "UFC"]:' not in code.split('def api_chart_candles')[1]:
    parts = code.split('def api_chart_candles(asset: str, timeframe: str = "1m", limit: int = 300):')
    parts[1] = parts[1].replace('if asset.upper() in ACTIVE_PAIRS:', chart_stub + '\n        if asset.upper() in ACTIVE_PAIRS:', 1)
    code = parts[0] + 'def api_chart_candles(asset: str, timeframe: str = "1m", limit: int = 300):' + parts[1]


with open('backend/routes/engine.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Patched api_chart_candles')
