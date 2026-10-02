file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\app.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Fix 1:
def repl1(m):
    return m.group(0) + '\n      return headers;'

content = re.sub(
    r'(function getAuthHeaders\(customHeaders = \{\}\) \{\s*const headers = \{ \.\.\.customHeaders \};\s*const token = getAppApiToken\(\);\s*if \(token\) \{\s*headers\["X-API-Token"\] = token;\s*\})',
    repl1,
    content
)

# Fix 2:
def repl2(m):
    return m.group(0) + '\n      return headers;'

content = re.sub(
    r'(function getAuthHeaders\(customHeaders = \{\}\) \{\s*const headers = \{ \.\.\.customHeaders \};\s*const urlParams = new URLSearchParams\(window\.location\.search\);\s*const urlToken = urlParams\.get\("token"\) \|\| urlParams\.get\("api_token"\);\s*if \(urlToken\) \{\s*localStorage\.setItem\("app_api_token", urlToken\);\s*const cleanUrl = window\.location\.pathname \+ window\.location\.hash;\s*window\.history\.replaceState\(\{\}, document\.title, cleanUrl\);\s*\}\s*const token = localStorage\.getItem\("app_api_token"\) \|\| "";\s*if \(token\) \{\s*headers\["X-API-Token"\] = token;\s*\})',
    repl2,
    content
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("app.js headers fixed!")
