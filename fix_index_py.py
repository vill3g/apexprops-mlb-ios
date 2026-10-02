# -*- coding: utf-8 -*-
import codecs
import re

file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\index.html'

# Read as utf-8, ignore errors just in case, but Latin-1 is actually the bytes we see as mojibake
with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Emojis were saved as Windows-1252 and read as UTF-8, destroying them.
# The user's screenshots showed: "? PAPER MODE", "? SCALPER", "56Â¢", etc.
# Some of these are unprintable. Let's do string replacements of the exact visual matches.
# But wait, we saw \ufffd () in the output. This means the bytes were invalid utf-8.

replaces = [
    ('Â·', '·'),
    ('Â¢', '¢'),
    ('s', '⚡'),
    ('s?', '🔄'),
    ('-', '⬆️'),
    ('-?', '🔴'),
    ('\'', '💰'),
    ('Y', '💎'),
    ('o', '✕'),
    ('F', '°F'),
    ('??', '⏱️'),
    ('?', '🛡️'),
    ('-?', '🔴'),
    ('sT?', '⚙️'),
    ('- ABOVE', '⬆️ ABOVE'),
    ('- BELOW', '⬇️ BELOW'),
]

for k, v in replaces:
    content = content.replace(k, v)

# Also fix the standard '?? ' ones:
content = content.replace('?? AUTO', '🤖 AUTO')
content = content.replace('?? Sniper', '🎯 Sniper')
content = content.replace('?? SNIPER', '🎯 SNIPER')
content = content.replace('?? Prediction', '🔮 Prediction')
content = content.replace('?? PREDICTION', '🔮 PREDICTION')
content = content.replace('?? Momentum', '🏄 Momentum')
content = content.replace('?? MOMENTUM', '🏄 MOMENTUM')
content = content.replace('?? MOMENTUM SURFER', '🏄 MOMENTUM SURFER')
content = content.replace('?? Ambush', '🐅 Ambush')
content = content.replace('?? AMBUSH', '🐅 AMBUSH')
content = content.replace('?? Chop', '🪓 Chop')
content = content.replace('?? CHOP', '🪓 CHOP')
content = content.replace('?? Deep Q-Network', '🧠 Deep Q-Network')
content = content.replace('??? God-Tier Swarm', '🐝✨ God-Tier Swarm')
content = content.replace('?? Blend', '🌪️ Blend')
content = content.replace('?? BLEND', '🌪️ BLEND')
content = content.replace('?? 100% AI', '🧠 100% AI')
content = content.replace('?? 100% Chart', '📊 100% Chart')
content = content.replace('??? Technical Force', '⚡ Technical Force')
content = content.replace('?? 1-Shot', '🔫 1-Shot')
content = content.replace('?? Net P&L', '💰 Net P&L')
content = content.replace('?? Win Rate', '🎯 Win Rate')
content = content.replace('?? Trades', '📈 Trades')
content = content.replace('?? SCALPER', '⚡ SCALPER')
content = content.replace('? SCALPER', '⚡ SCALPER')
content = content.replace('? LINE', '📈 LINE')
content = content.replace('? CANDLES', '🕯️ CANDLES')
content = content.replace('? PAPER MODE', '🧪 PAPER MODE')
content = content.replace('? LIVE MODE', '🔴 LIVE MODE')
content = content.replace('?? PAPER MODE:', '🧪 PAPER MODE:')
content = content.replace('?? PAPER SIMULATION', '🧪 PAPER SIMULATION')
content = content.replace('? BLEND', '🌪️ BLEND')

# Fix UI badges
content = re.sub(r'class="text-xs">\?\?</span>', 'class="text-xs">⏱️</span>', content)

# Fallback: remove any remaining replacement chars to avoid  rendering on screen
content = content.replace('', '')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("index.html emojis fixed!")
