import re

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix pre_gate_grade
content = content.replace('pre_gate_dir = forecast.get("pre_gate_direction")', 'pre_gate_dir = forecast.get("pre_gate_direction")\n            pre_gate_grade = str(forecast.get("pre_gate_grade", ""))')

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
