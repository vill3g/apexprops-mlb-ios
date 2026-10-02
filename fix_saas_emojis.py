file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html'
with open(file_path, 'r', encoding='latin-1') as f:
    content = f.read()

replaces = {
    '?? AUTO': '?? AUTO',
    '?? Sniper': '?? Sniper',
    '?? SNIPER': '?? SNIPER',
    '?? Prediction': '?? Prediction',
    '?? PREDICTION': '?? PREDICTION',
    '?? Momentum': '?? Momentum',
    '?? MOMENTUM': '?? MOMENTUM',
    '?? MOMENTUM SURFER': '?? MOMENTUM SURFER',
    '?? Ambush': '?? Ambush',
    '?? AMBUSH': '?? AMBUSH',
    '?? Chop': '?? Chop',
    '?? CHOP': '?? CHOP',
    '?? Deep Q-Network': '?? Deep Q-Network',
    '????? God-Tier Swarm': '??? God-Tier Swarm',
    '?? Blend': '??? Blend',
    '?? 100% AI': '?? 100% AI',
    '?? 100% Chart': '?? 100% Chart',
    '??? Technical Force': '? Technical Force',
    '?? 1-Shot': '?? 1-Shot',
    '?? Net P&L': '?? Net P&L',
    '?? Win Rate': '?? Win Rate',
    '?? Trades': '?? Trades',
    '?? <span class="text-blue-400 font-bold">PAPER MODE:</span>': '?? <span class="text-blue-400 font-bold">PAPER MODE:</span>',
    '<span>??</span> <span>Line</span>': '<span>??</span> <span>Line</span>',
    '<span>???</span> <span>Candles</span>': '<span>???</span> <span>Candles</span>',
    '?? Paper Mode': '?? Paper Mode',
    '<span>??</span> Selected Style': '<span>??</span> Selected Style',
    '<span>??</span> Signal Source': '<span>??</span> Signal Source',
    '<span>??</span> Deep Q-Network Reasoning': '<span>??</span> Deep Q-Network Reasoning',
    '<span>??</span> Why Swarm': '<span>??</span> Why Swarm',
    '<span>??</span> Direction & Model Signal Rationale': '<span>??</span> Direction & Model Signal Rationale',
    '<span>???</span> Risk Management & Exit Discipline': '<span>???</span> Risk Management & Exit Discipline',
    '<span>??</span> Contract Anatomy & Financial Ledger': '<span>??</span> Contract Anatomy & Financial Ledger',
}

for k, v in replaces.items():
    content = content.replace(k, v)

# For isolated ?? inside tags
import re
content = re.sub(r'>\?\?</', '>?</', content)
content = re.sub(r'>\?\?\?</', '>?</', content)
content = re.sub(r'class="text-xs">\?\?</span>', 'class="text-xs">??</span>', content)
content = re.sub(r'text-3xl mb-2">\?\?</', 'text-3xl mb-2">??</', content)
content = re.sub(r'text-2xl">\?\?</', 'text-2xl">??</', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("saas_dashboard.html emojis fixed!")
