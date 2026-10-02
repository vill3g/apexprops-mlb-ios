import re

js_path = "static/js/admin_users.js"
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

pattern = r'<div class="grid grid-cols-2 sm:grid-cols-4 gap-2\.5">'
replace = r'<div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 gap-y-4">'
js = re.sub(pattern, replace, js)

with open(js_path, "w", encoding="utf-8") as f:
    f.write(js)
print("Updated admin_users.js grid gap!")
