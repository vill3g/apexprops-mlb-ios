import re

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

match = re.search(r'record_trade\(.*?\)', code, re.DOTALL)
if match:
    print(match.group(0))
