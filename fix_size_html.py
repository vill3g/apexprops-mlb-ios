import re

html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

pattern = r'<span id="val-pnl" class="text-xs sm:text-sm font-black tabular-nums text-gray-400 truncate">'
replace = r'<span id="val-pnl" class="text-sm sm:text-base font-black tabular-nums text-gray-400 truncate">'
html = re.sub(pattern, replace, html)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Updated HTML val-pnl size!")
