import re

file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\dashboard.js'
with open(file_path, 'r', encoding='latin-1') as f:
    content = f.read()

exact_replaces = {
    '?? FORCE': '? FORCE',
    '?? 2ND ENTRY': '?? 2ND ENTRY',
    '?? RL DQN': '?? RL DQN',
    '?? TECH': '?? TECH',
    '?? SWARM': '?? SWARM',
    '?? LIVE TRADING': '?? LIVE TRADING',
    '?? PAPER SIMULATION': '?? PAPER SIMULATION',
    '?? REVERSAL FADE': '?? REVERSAL FADE',
    '?? REVERSAL': '?? REVERSAL',
    '?? Blend': '??? Blend',
    '?? Details ?': '?? Details ?',
    "if (isWin) iconEl.innerText = '??';": "if (isWin) iconEl.innerText = '?';",
    "else if (isLoss) iconEl.innerText = '???';": "else if (isLoss) iconEl.innerText = '?';",
    "else if (isOpen) iconEl.innerText = '?';": "else if (isOpen) iconEl.innerText = '?';",
    "else iconEl.innerText = '??';": "else iconEl.innerText = '?';",
}

for k, v in exact_replaces.items():
    content = content.replace(k, v)

content = content.replace('>? ' + r"'" + '+ rawStyle.replace(/_/g, \' \')', ">?? ' + rawStyle.replace(/_/g, ' ')")
content = content.replace(">?? ' + rawSource.replace(/_/g, \' \')", ">?? ' + rawSource.replace(/_/g, ' ')")
content = content.replace(">?? ", ">?? ")

content = content.replace('exitIcon = \'??\';', "exitIcon = '??';")

exit_icon_blocks = [
    ('exitReason.includes("SETTLE")', 'exitIcon = "??";', 'exitIcon = "??";'),
    ('exitReason.includes("MANUAL")', 'exitIcon = "??";', 'exitIcon = "???";'),
    ('exitReason.includes("PROFIT")', 'exitIcon = "??";', 'exitIcon = "??";'),
    ('exitReason.includes("STOP")', 'exitIcon = "??";', 'exitIcon = "???";'),
    ('exitReason.includes("TRAILING")', 'exitIcon = "??";', 'exitIcon = "??";'),
]

lines = content.split('\n')
for i, line in enumerate(lines):
    for condition, bad, good in exit_icon_blocks:
        if bad in line:
            if i >= 1 and (condition in lines[i-1] or (i >= 2 and condition in lines[i-2])):
                lines[i] = line.replace(bad, good)
                
content = '\n'.join(lines)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("dashboard.js fixes complete")
