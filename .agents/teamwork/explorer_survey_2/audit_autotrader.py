import re

with open('static/saas_dashboard.html', encoding='utf-8') as f:
    html_lines = f.readlines()

print("Searching for auto-trader elements in HTML...")
for idx, line in enumerate(html_lines):
    if any(k in line.lower() for k in ['autotrader', 'auto-trader', 'auto_trader', 'autotrade', 'auto-toggle', 'header-auto']):
        print(f"L{idx+1}: {line.strip()[:100]}")

print("\nSearching for all <input type='checkbox'> in HTML...")
for idx, line in enumerate(html_lines):
    if '<input' in line and 'type="checkbox"' in line:
        print(f"L{idx+1}: {line.strip()[:100]}")
