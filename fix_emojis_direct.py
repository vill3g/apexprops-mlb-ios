file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\dashboard.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replaces = {
    '??? MANUAL': '??? MANUAL',
    '?? MOMENTUM': '?? MOMENTUM',
    '?? SNIPER': '?? SNIPER',
    '?? PREDICTION': '?? PREDICTION',
    '?? CHOP': '?? CHOP',
    '??? GUARD': '??? GUARD',
    '???? GUARD': '??? GUARD',
    '?? 2ND ENTRY': '?? 2ND ENTRY',
    '?? RL DQN': '?? RL DQN',
    '?? TECH': '?? TECH',
    '?? SWARM': '?? SWARM',
    '?? REVERSAL': '?? REVERSAL',
    '?? LIVE TRADING': '?? LIVE TRADING',
    '?? PAPER SIMULATION': '?? PAPER SIMULATION',
    '?? 2ND ENTRY ROLLOVER': '?? 2ND ENTRY ROLLOVER',
    '?? REVERSAL FADE': '?? REVERSAL FADE',
    '??? Blend': '??? Blend',
    '???? Blend': '??? Blend',
    '?? Loading Community': '? Loading Community',
    '?? LIVE trading': '?? LIVE trading',
    '?? PAPER trading': '?? PAPER trading',
    "?? <span class='text-blue-400": "?? <span class='text-blue-400",
    "?? Details ?": "?? Details ?",
    "?? ' + rawStyle": "?? ' + rawStyle",
    "?? ' + rawSource": "?? ' + rawSource",
    "?? ${rawStyle": "?? ${rawStyle",
    "exitIcon = '??';": "exitIcon = '??';",
    "exitIcon = \"??\";": "exitIcon = \"??\";",
    "exitIcon = \"???\";": "exitIcon = \"??\";",
    "iconEl.innerText = '??';": "iconEl.innerText = '?';",
    "iconEl.innerText = '???';": "iconEl.innerText = '?';",
    "iconEl.innerText = '?';": "iconEl.innerText = '?';",
    "'>??</div>": "'>#</div>"
}

for k, v in replaces.items():
    content = content.replace(k, v)

# Fix exit icons contextually
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'exitIcon =' in line and '??' in line:
        if i >= 1 and 'SETTLE' in lines[i-1]:
            lines[i] = line.replace("'??'", '"??"').replace('"??"', '"??"')
        elif i >= 1 and 'MANUAL' in lines[i-1]:
            lines[i] = line.replace("'??'", '"???"').replace('"??"', '"???"')
        elif i >= 1 and 'PROFIT' in lines[i-1]:
            lines[i] = line.replace("'??'", '"??"').replace('"??"', '"??"')
        elif i >= 1 and 'STOP' in lines[i-1]:
            lines[i] = line.replace("'??'", '"???"').replace('"??"', '"???"')
        elif i >= 1 and 'TRAILING' in lines[i-1]:
            lines[i] = line.replace("'??'", '"??"').replace('"??"', '"??"')

content = '\n'.join(lines)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("dashboard.js direct string replace complete")
