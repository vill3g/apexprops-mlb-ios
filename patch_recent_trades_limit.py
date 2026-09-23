import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Change the slice limit from 5 to 10
content = content.replace('const recent = (s.recent_trades || []).slice(0, 5);', 'const recent = (s.recent_trades || []).slice(0, 10);')

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
