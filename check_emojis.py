import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

match = re.search(r'<select id="trading-style.*?</select>', content, re.DOTALL)
if match:
    print(match.group(0))
