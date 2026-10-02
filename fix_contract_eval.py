import re

fpath = 'backend/btc/analyzer/contract_eval.py'
with open(fpath, 'r', encoding='utf-8') as f:
    text = f.read()

# Fix CHOP 100% probability
text = text.replace('prob = 100.0', 'prob = 75.0')

# Fix AMBUSH conflict
text = text.replace(
    'if ("YES" in str(pred) or direction == "YES") and delta_target_pts < -25.0:\n            if (c_close < c_open) and (ema_9 < ema_21) and not is_exhaustion_spring:',
    'if ("YES" in str(pred) or direction == "YES") and delta_target_pts < -25.0:\n            if (c_close < c_open) and (ema_9 < ema_21) and not is_exhaustion_spring and trading_style != "AMBUSH":'
)
text = text.replace(
    'if ("NO" in str(pred) or direction == "NO") and delta_target_pts > 25.0:\n            if (c_close > c_open) and (ema_9 > ema_21) and not is_exhaustion_fade:',
    'if ("NO" in str(pred) or direction == "NO") and delta_target_pts > 25.0:\n            if (c_close > c_open) and (ema_9 > ema_21) and not is_exhaustion_fade and trading_style != "AMBUSH":'
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(text)

print("contract_eval.py fixed")
