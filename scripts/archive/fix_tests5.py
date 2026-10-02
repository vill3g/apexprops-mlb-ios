import re
with open('tests/test_remediation.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('        engine = ScalpEngine.__new__(ScalpEngine)\n        engine.config = {"mode": "PAPER", "max_contracts": 1}', '        engine = ScalpEngine.__new__(ScalpEngine)\n        engine.asset = "BTC"\n        engine.config = {"mode": "PAPER", "max_contracts": 1}')

with open('tests/test_remediation.py', 'w', encoding='utf-8') as f:
    f.write(content)
