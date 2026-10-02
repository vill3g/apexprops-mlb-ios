import re

with open('backend/btc/analyzer.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_block = """    # Calculate Target Settlement Zone based on ATR dispersion
    if "YES" in pred or "ABOVE" in pred:
        z_min = target + (atr * 0.15)
        z_max = target + (atr * 0.90)
        direction = "YES"
        action = "BID YES"
    else:
        z_min = target - (atr * 0.90)
        z_max = target - (atr * 0.15)
        direction = "NO"
        action = "BID NO"

    zone_str = f"${z_min:,.0f} - ${z_max:,.0f}"
    prob = min(98, max(50, prob))
    if direction == "PASS":
        prob = 50"""

new_block = """    # Calculate Target Settlement Zone based on ATR dispersion
    if "PASS" in pred:
        z_min = target - (atr * 0.15)
        z_max = target + (atr * 0.15)
        direction = "PASS"
        action = "PASS"
        prob = 50
    elif "YES" in pred or "ABOVE" in pred:
        z_min = target + (atr * 0.15)
        z_max = target + (atr * 0.90)
        direction = "YES"
        action = "BID YES"
    else:
        z_min = target - (atr * 0.90)
        z_max = target - (atr * 0.15)
        direction = "NO"
        action = "BID NO"

    zone_str = f"${z_min:,.0f} - ${z_max:,.0f}"
    prob = min(98, max(50, prob))"""

code = code.replace(old_block, new_block)

with open('backend/btc/analyzer.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched analyzer evaluate logic!")
