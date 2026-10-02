import re

html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Pattern to find the pulsating dot
pattern = r'<!-- Live pulsing emerald heartbeat pip -->\s*<span class="absolute -bottom-0\.5 -right-0\.5 w-2 h-2 rounded-full bg-emerald-400 border border-black shadow-\[0_0_6px_rgba\(52,211,153,0\.9\)\] animate-pulse"></span>'

html = re.sub(pattern, '', html)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Removed pulsing green dot!")
