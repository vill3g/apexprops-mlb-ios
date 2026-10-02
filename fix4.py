with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 't.trading_style !== "SECOND_ENTRY"' in line:
        print(''.join(lines[i-3:i+6]))
