import re

file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\dashboard.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace any sequence of ? followed by a space, then the word
replacements = [
    (r'\?+\s*Blend', r'??? Blend'),
    (r'\?+\s*Loading Community', r'? Loading Community'),
    (r'\?+\s*MANUAL', r'??? MANUAL'),
    (r'\?+\s*MOMENTUM', r'?? MOMENTUM'),
    (r'\?+\s*SNIPER', r'?? SNIPER'),
    (r'\?+\s*PREDICTION', r'?? PREDICTION'),
    (r'\?+\s*CHOP', r'?? CHOP'),
    (r'\?+\s*GUARD', r'??? GUARD'),
    (r'\?+\s*2ND ENTRY ROLLOVER', r'?? 2ND ENTRY ROLLOVER'),
    (r'\?+\s*2ND ENTRY', r'?? 2ND ENTRY'),
    (r'\?+\s*RL DQN', r'?? RL DQN'),
    (r'\?+\s*TECH', r'?? TECH'),
    (r'\?+\s*SWARM', r'?? SWARM'),
    (r'\?+\s*REVERSAL FADE', r'?? REVERSAL FADE'),
    (r'\?+\s*REVERSAL', r'?? REVERSAL'),
    (r'\?+\s*FORCE', r'? FORCE'),
    (r'\?+\s*LIVE TRADING', r'?? LIVE TRADING'),
    (r'\?+\s*LIVE trading', r'?? LIVE trading'),
    (r'\?+\s*PAPER SIMULATION', r'?? PAPER SIMULATION'),
    (r'\?+\s*PAPER trading', r'?? PAPER trading'),
    (r'\?+\s*Details\s*\?', r'?? Details ?'),
    
    (r">\?+\s*'\s*\+\s*rawSource", r">?? ' + rawSource"),
    (r">\?+\s*'\s*\+\s*rawStyle", r">?? ' + rawStyle"),
    (r">\?+\s*\$\{\s*rawStyle", r">?? ${rawStyle"),
    
    (r">\?+\s*<span class='text-blue-400", r">?? <span class='text-blue-400"),
    (r"'>\?+</div>", r"'>#</div>"),
]

for old, new in replacements:
    content = re.sub(old, new, content)

# Clean up exit icons
content = re.sub(r'exitIcon = "\?+";', 'exitIcon = "??";', content)
content = re.sub(r"exitIcon = '\?+';", "exitIcon = '??';", content)
content = re.sub(r"let exitIcon = '\?+';", "let exitIcon = '??';", content)

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

print("dashboard.js fixes complete")
