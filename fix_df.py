import os
filepath = 'C:/Users/vill3/.gemini/antigravity/scratch/mlb_props_app/backend/btc/data_fetcher.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

good_kalshi_code = """    target_price = _target_cache["active_target"] or curr_price
    target_source = _target_cache.get("target_source", f"15M Start Price ({start_time_12hr} ET)")

    # Override with Kalshi Official Strike
    kalshi_m = get_kalshi_15m_market()
    if kalshi_m and kalshi_m.get("target_price"):
        target_price = float(kalshi_m["target_price"])
        target_source = "Kalshi Official Strike (CME CF BRR)"

    delta = round(curr_price - target_price, 2)"""

content = content.replace('    target_price = _target_cache["active_target"] or curr_price\n    target_source = _target_cache.get("target_source", f"15M Start Price ({start_time_12hr} ET)")\n\n    delta = round(curr_price - target_price, 2)', good_kalshi_code)

content = content.replace('"kalshi": get_kalshi_15m_market(),', '"kalshi": kalshi_m,')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed data_fetcher.py')
