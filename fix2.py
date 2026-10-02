import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'\s*<button onclick="event\.stopPropagation\(\); executeManualTrade.*?ADD</button>', '', content)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Removed ADD buttons')
