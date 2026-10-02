import re

file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\dashboard.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    (r'\?\?\? Blend', r'??? Blend'),
    (r'\?\? Blend', r'??? Blend'),
    (r'\?\? Loading Community', r'? Loading Community'),
    (r"'>\?\?</div>", r"'>#</div>"),
    (r"isWin\) iconEl\.innerText = '\?\?';", r"isWin) iconEl.innerText = '?';"),
    (r"isLoss\) iconEl\.innerText = '\?\?\?';", r"isLoss) iconEl.innerText = '?';"),
    (r"isOpen\) iconEl\.innerText = '\?';", r"isOpen) iconEl.innerText = '?';"),
    (r"else iconEl\.innerText = '\?\?';", r"else iconEl.innerText = '?';"),
    
    (r'\?\? LIVE trading', r'?? LIVE trading'),
    (r'\?\? PAPER trading', r'?? PAPER trading'),
    (r'\?\? <span class=\'text-blue-400', r'?? <span class=\'text-blue-400'),
    
    (r'\?\? MANUAL', r'??? MANUAL'),
    (r'\?\? MOMENTUM', r'?? MOMENTUM'),
    (r'\?\? SNIPER', r'?? SNIPER'),
    (r'\?\? PREDICTION', r'?? PREDICTION'),
    (r'\?\? CHOP', r'?? CHOP'),
    (r'\?\?\? GUARD', r'??? GUARD'),
    (r'\?\? GUARD', r'??? GUARD'),
    (r'\?\? 2ND ENTRY ROLLOVER', r'?? 2ND ENTRY ROLLOVER'),
    (r'\?\? 2ND ENTRY', r'?? 2ND ENTRY'),
    (r'\?\? RL DQN', r'?? RL DQN'),
    (r'\?\? TECH', r'?? TECH'),
    (r'\?\? SWARM', r'?? SWARM'),
    (r'\?\? REVERSAL FADE', r'?? REVERSAL FADE'),
    (r'\?\? REVERSAL', r'?? REVERSAL'),
    (r'\?\? FORCE', r'? FORCE'),
    (r'\?\? LIVE TRADING', r'?? LIVE TRADING'),
    (r'\?\? PAPER SIMULATION', r'?? PAPER SIMULATION'),
    (r'\?\? Details \?', r'?? Details ?'),
    
    (r'\?\? \'\s*\+\s*rawSource', r'?? \' + rawSource'),
    (r'\?\? \$\{\s*rawStyle', r'?? ${rawStyle'),
    (r'\? \'\s*\+\s*rawStyle', r'?? \' + rawStyle'),
]

for old, new in replacements:
    content = re.sub(old, new, content)

exit_icon_blocks = [
    ('exitReason.includes("SETTLE")', '"??"', '"??"'),
    ('exitReason.includes("MANUAL")', '"??"', '"???"'),
    ('exitReason.includes("PROFIT")', '"??"', '"??"'),
    ('exitReason.includes("STOP")', '"??"', '"???"'),
    ('exitReason.includes("STOP")', '"???"', '"???"'),
    ('exitReason.includes("TRAILING")', '"??"', '"??"'),
]

lines = content.split('\n')
for i, line in enumerate(lines):
    if 'exitIcon =' in line:
        for condition, bad, good in exit_icon_blocks:
            if bad in line:
                if i >= 1 and (condition in lines[i-1] or (i >= 2 and condition in lines[i-2])):
                    lines[i] = line.replace(bad, good)
        if "'??'" in lines[i]:
            lines[i] = lines[i].replace("'??'", "'??'")

content = '\n'.join(lines)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("dashboard.js updated successfully")
