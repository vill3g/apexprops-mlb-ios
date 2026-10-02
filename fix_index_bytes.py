# -*- coding: utf-8 -*-
import os

file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\index.html'

with open(file_path, 'rb') as f:
    content = f.read().decode('utf-8', errors='ignore')

# Fix corrupted emojis that were saved as Windows-1252
replaces = {
    'Â·': '·',
    'Â¢': '¢',
    '- ABOVE': '⬆️ ABOVE',
    '- BELOW': '⬇️ BELOW',
    "sT? User Settings": "⚙️ User Settings",
    "s? Reset Paper Balance": "🔄 Reset Paper Balance",
    "ŧ Defaults": "⚙️ Defaults",
    "sT? General": "⚙️ General",
    "s Ambush": "🐅 Ambush",
    "s 1-Shot": "🔫 1-Shot",
    "Y ETH": "💎 ETH",
    "' BTC": "₿ BTC"
}

for k, v in replaces.items():
    content = content.replace(k, v)

# For the unknown characters, I will just remove the replacement char completely:
content = content.replace('\ufffd', '')

# Now re-apply the standard ones just in case:
standard = {
    '? SCALPER': '⚡ SCALPER',
    '?? SCALPER': '⚡ SCALPER',
    '? PAPER MODE': '🧪 PAPER MODE',
    '? LIVE MODE': '🔴 LIVE MODE',
    '?? PAPER MODE:': '🧪 PAPER MODE:',
    '? LINE': '📈 LINE',
    '? CANDLES': '🕯️ CANDLES',
    '? BLEND': '🌪️ BLEND',
    '?? BLEND': '🌪️ BLEND',
    '?? AUTO': '🤖 AUTO',
    '?? Sniper': '🎯 Sniper',
    '?? SNIPER': '🎯 SNIPER',
    '?? Prediction': '🔮 Prediction',
    '?? PREDICTION': '🔮 PREDICTION',
    '?? Momentum': '🏄 Momentum',
    '?? MOMENTUM': '🏄 MOMENTUM',
    '?? MOMENTUM SURFER': '🏄 MOMENTUM SURFER',
    '?? Ambush': '🐅 Ambush',
    '?? AMBUSH': '🐅 AMBUSH',
    '?? Chop': '🪓 Chop',
    '?? CHOP': '🪓 CHOP',
    '?? Deep Q-Network': '🧠 Deep Q-Network',
    '??? God-Tier Swarm': '🐝✨ God-Tier Swarm',
    '?? Blend': '🌪️ Blend',
    '?? 100% AI': '🧠 100% AI',
    '?? 100% Chart': '📊 100% Chart',
    '??? Technical Force': '⚡ Technical Force',
    '?? 1-Shot': '🔫 1-Shot',
    '?? Net P&L': '💰 Net P&L',
    '?? Win Rate': '🎯 Win Rate',
    '?? Trades': '📈 Trades'
}

for k, v in standard.items():
    content = content.replace(k, v)

# Some specific replacements
content = content.replace('<span>s</span> Scalper', '<span>⚡</span> Scalper')
content = content.replace('<span>-?</span>1m', '<span>🔴</span>1m')
content = content.replace('id="appModalIcon">s</span>', 'id="appModalIcon">🤖</span>')
content = content.replace('<span>-</span>', '<span>🔺</span>')
content = content.replace('o ', '✕ ')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("index.html fixed via python bytes read!")
