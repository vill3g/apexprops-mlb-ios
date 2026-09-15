import sys

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('from datetime import datetime', '# from datetime import datetime (already imported globally)')

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done fixing shadowing!')
