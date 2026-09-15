import sys

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'from datetime import datetime' in line and i > 250:
        lines[i] = '# datetime is globally imported\\n'

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Fixed precise shadowing!')
