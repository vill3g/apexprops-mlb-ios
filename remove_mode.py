import re

html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

pattern = r'<!-- Mode Switcher & Quick Controls -->\s*<div class="dashboard-item item-mode mx-3 sm:mx-4 mb-2\.5 flex items-center gap-2">\s*<div class="flex-1 bg-\[#131b2c\] rounded-xl p-1 flex relative shadow-sm border border-kalshi-border">\s*<div id="mode-slider" [^>]+></div>\s*<button id="btn-mode-paper" [^>]+>Paper Trading</button>\s*<button id="btn-mode-live" [^>]+>Live Trading</button>\s*</div>\s*</div>'

html = re.sub(pattern, '', html)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Removed mode switcher from UI!")
