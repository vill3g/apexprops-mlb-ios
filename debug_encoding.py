file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\dashboard.js'
with open(file_path, 'rb') as f:
    content = f.read()

import re
matches = re.finditer(b'\\?+.*?MANUAL', content)
for m in matches:
    print(m.group(0))
