file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\index.html'
with open(file_path, 'r', encoding='latin-1') as f:
    content = f.read()

replaces = {
    'Â·': '·',
    'Â¢': '¢',
    '- ABOVE': '?? ABOVE',
    '- BELOW': '?? BELOW',
    '-': '??', # Might need to be careful
    's Ambush': '?? Ambush',
    's 1-Shot AI Trade': '?? 1-Shot AI Trade',
    '?? Execution': '?? Execution',
    's? Reset Paper': '?? Reset Paper',
    's Scalp Engine': '? Scalp Engine',
    't Defaults': '?? Defaults',
    'sT? User Settings': '?? User Settings',
    '-?': '??',
    '' : '??', # Wait, that might match too much. Let's not do 1 char replacements unless exact.
    'Y ETH': '?? ETH',
    '\' BTC': '? BTC',
    '?': '??',
}

for k, v in replaces.items():
    content = content.replace(k, v)

# Also fix the standard '?? ' ones:
content = content.replace('?? AUTO', '?? AUTO')
content = content.replace('?? Sniper', '?? Sniper')
content = content.replace('?? SNIPER', '?? SNIPER')
content = content.replace('?? Prediction', '?? Prediction')
content = content.replace('?? PREDICTION', '?? PREDICTION')
content = content.replace('?? Momentum', '?? Momentum')
content = content.replace('?? MOMENTUM', '?? MOMENTUM')
content = content.replace('?? MOMENTUM SURFER', '?? MOMENTUM SURFER')
content = content.replace('?? Ambush', '?? Ambush')
content = content.replace('?? AMBUSH', '?? AMBUSH')
content = content.replace('?? Chop', '?? Chop')
content = content.replace('?? CHOP', '?? CHOP')
content = content.replace('?? Deep Q-Network', '?? Deep Q-Network')
content = content.replace('??? God-Tier Swarm', '??? God-Tier Swarm')
content = content.replace('?? Blend', '??? Blend')
content = content.replace('?? BLEND', '??? BLEND')
content = content.replace('?? 100% AI', '?? 100% AI')
content = content.replace('?? 100% Chart', '?? 100% Chart')
content = content.replace('??? Technical Force', '? Technical Force')
content = content.replace('?? 1-Shot', '?? 1-Shot')
content = content.replace('?? Net P&L', '?? Net P&L')
content = content.replace('?? Win Rate', '?? Win Rate')
content = content.replace('?? Trades', '?? Trades')
content = content.replace('?? SCALPER', '? SCALPER')
content = content.replace('? SCALPER', '? SCALPER')
content = content.replace('? LINE', '?? LINE')
content = content.replace('? CANDLES', '??? CANDLES')
content = content.replace('? PAPER MODE', '?? PAPER MODE')
content = content.replace('? LIVE MODE', '?? LIVE MODE')
content = content.replace('?? PAPER MODE:', '?? PAPER MODE:')
content = content.replace('?? PAPER SIMULATION', '?? PAPER SIMULATION')

import re
content = re.sub(r'class="text-xs">\?\?</span>', 'class="text-xs">??</span>', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("index.html emojis fixed!")
