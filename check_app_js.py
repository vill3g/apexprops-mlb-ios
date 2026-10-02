file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\app.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re
# Find all getAuthHeaders functions and see if they have return statements
matches = re.finditer(r'function getAuthHeaders.*?\}(?=\s*(?:\n|$))', content, re.DOTALL)
for m in matches:
    print(m.group(0))
    print("-----")
