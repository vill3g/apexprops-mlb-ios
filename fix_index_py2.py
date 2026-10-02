# -*- coding: utf-8 -*-
import codecs
import re

file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\index.html'

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

replaces = [
    ('Â·', '·'),
    ('Â¢', '¢'),
    ('\ufffd', ''),
    ('\xef\xbf\xbd', ''),
    ('? SCALPER', '\u26A1 SCALPER'),
    ('? LINE', '\U0001F4C8 LINE'),
    ('? CANDLES', '\U0001F56F\uFE0F CANDLES'),
    ('? PAPER MODE', '\U0001F9EA PAPER MODE'),
    ('? LIVE MODE', '\U0001F534 LIVE MODE'),
    ('?? PAPER MODE:', '\U0001F9EA PAPER MODE:'),
    ('?? PAPER SIMULATION', '\U0001F9EA PAPER SIMULATION'),
    ('? BLEND', '\U0001F32A\uFE0F BLEND'),
    ('?? AUTO', '\U0001F916 AUTO'),
    ('?? Sniper', '\U0001F3AF Sniper'),
    ('?? SNIPER', '\U0001F3AF SNIPER'),
    ('?? Prediction', '\U0001F52E Prediction'),
    ('?? PREDICTION', '\U0001F52E PREDICTION'),
    ('?? Momentum', '\U0001F3C4 Momentum'),
    ('?? MOMENTUM', '\U0001F3C4 MOMENTUM'),
    ('?? MOMENTUM SURFER', '\U0001F3C4 MOMENTUM SURFER'),
    ('?? Ambush', '\U0001F405 Ambush'),
    ('?? AMBUSH', '\U0001F405 AMBUSH'),
    ('?? Chop', '\U0001FA93 Chop'),
    ('?? CHOP', '\U0001FA93 CHOP'),
    ('?? Deep Q-Network', '\U0001F9E0 Deep Q-Network'),
    ('??? God-Tier Swarm', '\U0001F41D\u2728 God-Tier Swarm'),
    ('?? Blend', '\U0001F32A\uFE0F Blend'),
    ('?? BLEND', '\U0001F32A\uFE0F BLEND'),
    ('?? 100% AI', '\U0001F9E0 100% AI'),
    ('?? 100% Chart', '\U0001F4C8 100% Chart'),
    ('??? Technical Force', '\u26A1 Technical Force'),
    ('?? 1-Shot', '\U0001F52B 1-Shot'),
    ('?? Net P&L', '\U0001F4B0 Net P&L'),
    ('?? Win Rate', '\U0001F3AF Win Rate'),
    ('?? Trades', '\U0001F4C8 Trades'),
    ('?? SCALPER', '\u26A1 SCALPER'),
    ('- ABOVE', '\u2B06\uFE0F ABOVE'),
    ('- BELOW', '\u2B07\uFE0F BELOW')
]

for k, v in replaces:
    content = content.replace(k, v)

# Fix UI badges
content = re.sub(r'class="text-xs">\?\?</span>', 'class="text-xs">\u23F1\uFE0F</span>', content)

# Fallback: remove any remaining replacement chars to avoid rendering on screen
content = content.replace('\ufffd', '')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("index.html emojis fixed!")
