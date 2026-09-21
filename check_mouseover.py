import re

with open('static/js/app.js', 'r', encoding='utf-8') as f:
    app = f.read()

match = re.search(r'document\.addEventListener\("mouseover", \(e\) => \{.*?\n      \}\);', app, re.DOTALL)
if match:
    print(match.group(0))
