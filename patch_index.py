file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\index.html'
with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

replaces = [
    ('?', '???'),
    ('\' BTC', '? BTC'),
    ('\'', '??'),
    ('Y ETH', '?? ETH'),
    ('Y', '??'),
    ('s', '?'),
    (' OOG LLC ', '© OOG LLC -'),
    ('?"', '-'),
    ('- ABOVE', '?? ABOVE'),
    ('- BELOW', '?? BELOW'),
    ('-', '??'),
    ('-?', '??'),
    ('\'', '??'),
    ('sT? General', '?? General'),
    ('sT? User Settings', '?? User Settings'),
    ('s Ambush', '?? Ambush'),
    ('?\'', '-'),
    ('s 1-Shot', '?? 1-Shot'),
    ('??', '??'),
    ('t', '??'),
    ('s?', '??'),
    ('o', '?'),
    ('F', '°F'),
    ('-', '??')
]

for old, new in replaces:
    content = content.replace(old, new)

# And clear any remaining replacement chars
import re
content = re.sub(r'.*?', '?', content)
content = content.replace('', '')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("index.html fully patched")
