import re

with open('backend/btc/indicators.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Bullish RSI divergence
old_bull = 'if curr_low < prev_low and curr_rsi > prev_rsi and curr_rsi < 45 and (curr_idx - prev_low_idx) >= 3:'
new_bull = 'if curr_low < prev_low and curr_rsi > prev_rsi and curr_rsi < 45 and prev_rsi < 45 and (curr_idx - prev_low_idx) >= 3:'
content = content.replace(old_bull, new_bull)

# Bearish RSI divergence
old_bear = 'if curr_high > prev_high and curr_rsi < prev_rsi and curr_rsi > 55 and (curr_idx - prev_high_idx) >= 3:'
new_bear = 'if curr_high > prev_high and curr_rsi < prev_rsi and curr_rsi > 55 and prev_rsi > 55 and (curr_idx - prev_high_idx) >= 3:'
content = content.replace(old_bear, new_bear)

with open('backend/btc/indicators.py', 'w', encoding='utf-8') as f:
    f.write(content)
