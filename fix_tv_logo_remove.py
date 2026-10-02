import re
html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Remove the bad patch
html = re.sub(r'<div class="absolute bottom-\[22px\] left-\[10px\] w-\[50px\] h-\[50px\] rounded-full bg-\[#131b2c\] z-50"></div>', "", html)

# Also ensure any other variations are removed just in case
html = re.sub(r'<div class="absolute bottom-0 left-0 w-24 h-8 bg-\[#131b2c\] z-50"></div>', "", html)
html = re.sub(r'<div class="absolute bottom-0 left-0 w-24 h-8 bg-\[#131b2c\] z-50 pointer-events-none"></div>', "", html)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Removed old patch.")
