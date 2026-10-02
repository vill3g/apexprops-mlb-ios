import re
html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Replace the previous cover div with a specifically positioned circular patch
html = html.replace(
    '<div class="absolute bottom-0 left-0 w-24 h-8 bg-[#131b2c] z-50"></div>',
    '<div class="absolute bottom-[22px] left-[10px] w-[50px] h-[50px] rounded-full bg-[#131b2c] z-50"></div>'
)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Updated TV logo cover div to be a perfectly positioned circular patch.")
