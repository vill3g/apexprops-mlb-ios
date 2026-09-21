with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re
scripts = list(re.finditer(r'<script>(.*?)</script>', text, flags=re.DOTALL))
s2 = scripts[2].group(1)

lines = s2.split('\n')
for i in range(len(lines)-20, len(lines)):
    print(f"{i+1}: {lines[i].encode('ascii', 'ignore').decode('ascii')}")
