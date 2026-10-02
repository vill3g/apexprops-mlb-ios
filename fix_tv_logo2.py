import re
html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

html = html.replace(
    '<div class="absolute bottom-0 left-0 w-24 h-8 bg-[#131b2c] z-50 pointer-events-none"></div>',
    '<div class="absolute bottom-0 left-0 w-24 h-8 bg-[#131b2c] z-50"></div>'
)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Removed pointer-events-none from TV logo cover div.")
