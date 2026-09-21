with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re
headers = re.findall(r'// [0-9]\. .*', text)
for h in headers:
    print(h)
