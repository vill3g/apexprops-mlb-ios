import re
html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

pattern = r'<div id="ml-status-bubble"[^>]*>.*?</div>'
html = re.sub(pattern, "", html)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Removed ml-status-bubble from HTML")
