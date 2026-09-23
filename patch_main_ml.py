import re

with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''        data = dict(data)
        data["is_synthetic"] = (data.get("status") == "synthetic") or (data.get("source") == "Kalshi Synthetic")
        return JSONResponse(data)'''

new_block = '''        data = dict(data)
        data["is_synthetic"] = (data.get("status") == "synthetic") or (data.get("source") == "Kalshi Synthetic")
        try:
            _, analysis = get_cached_btc_analysis(asset=asset, timeframe="15m")
            data["ml_reasoning"] = sanitize_btc_json(analysis)
        except:
            pass
        return JSONResponse(data)'''

content = content.replace(old_block, new_block)

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
