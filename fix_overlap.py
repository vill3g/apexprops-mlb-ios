import re

js_path = "static/js/admin_users.js"
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

pattern = r'<div class="grid grid-cols-1 sm:grid-cols-3 gap-2\.5 text-xs">'
replace = r'<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">'
js = re.sub(pattern, replace, js)

with open(js_path, "w", encoding="utf-8") as f:
    f.write(js)
print("Fixed grid columns to prevent overlap!")
