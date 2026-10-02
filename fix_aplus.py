import re

fpath = 'backend/btc/analyzer/contract_eval.py'
with open(fpath, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Patch CHOP Dynamic Theta Decay for kalshi_no_ask
chop_no_ask_old = "if 0.40 <= kalshi_no_ask <= 0.60:"
chop_no_ask_new = """import time
            sec_left = 900 - (int(time.time()) % 900)
            tolerance = min(0.35, max(0.10, 0.10 + (840 - sec_left) * 0.000378))
            if (0.50 - tolerance) <= kalshi_no_ask <= (0.50 + tolerance):"""
text = text.replace(chop_no_ask_old, chop_no_ask_new)

# 1. Patch CHOP Dynamic Theta Decay for kalshi_yes_ask
chop_yes_ask_old = "if 0.40 <= kalshi_yes_ask <= 0.60:"
chop_yes_ask_new = """import time
            sec_left = 900 - (int(time.time()) % 900)
            tolerance = min(0.35, max(0.10, 0.10 + (840 - sec_left) * 0.000378))
            if (0.50 - tolerance) <= kalshi_yes_ask <= (0.50 + tolerance):"""
text = text.replace(chop_yes_ask_old, chop_yes_ask_new)


# 2. Patch AMBUSH Orderbook Absorption (CVD)
ambush_old = """        try:
            is_fading_pump = (c_close > c_open) and direction == "BELOW"
            is_fading_dump = (c_close < c_open) and direction == "ABOVE"
            
            if is_fading_pump and trend_1h == "BULLISH":"""

ambush_new = """        try:
            is_fading_pump = (c_close > c_open) and direction == "BELOW"
            is_fading_dump = (c_close < c_open) and direction == "ABOVE"
            cvd_accel = float(c.get("cvd_acceleration", 0.0))
            
            if is_fading_dump and cvd_accel < -0.1:
                catalysts.insert(0, "🛑 AMBUSH Blocked: Dropping into negative CVD (Real Sellers, No Limit Absorption).")
                pred = "PASS / NO BID (CVD CONFLICT)"
                direction = "PASS"
                grade = "PASS / HIGH RISK"
                badge = "⚠️ PASS (NO ABSORPTION)"
                prob = 50.0
            elif is_fading_pump and cvd_accel > 0.1:
                catalysts.insert(0, "🛑 AMBUSH Blocked: Pumping into positive CVD (Real Buyers, No Limit Selling).")
                pred = "PASS / NO BID (CVD CONFLICT)"
                direction = "PASS"
                grade = "PASS / HIGH RISK"
                badge = "⚠️ PASS (NO ABSORPTION)"
                prob = 50.0
            elif is_fading_pump and trend_1h == "BULLISH":"""

text = text.replace(ambush_old, ambush_new)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(text)

print("contract_eval.py patched with A+ AMBUSH and CHOP mechanics!")
