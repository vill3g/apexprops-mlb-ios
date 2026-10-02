import re

js_path = "static/js/admin_users.js"
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

pattern = r'<div class="flex flex-col sm:flex-row gap-1\.5 sm:gap-1 items-start sm:items-center">'
replace = r'<div class="flex flex-col sm:flex-row flex-wrap gap-1.5 sm:gap-1 items-start sm:items-center">'
js = re.sub(pattern, replace, js)

with open(js_path, "w", encoding="utf-8") as f:
    f.write(js)
print("Added flex-wrap to prevent overflow!")
