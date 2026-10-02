import re

html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Row 2 classes
pattern_row2 = r'<div class="header-inner grid grid-cols-3 items-center w-full pt-1\.5 pb-1 px-1">'
replace_row2 = r'<div class="header-inner grid grid-cols-3 items-center w-full pt-1.5 pb-0 px-1">'
html = re.sub(pattern_row2, replace_row2, html)

# Row 3 classes
pattern_row3 = r'<div class="header-inner grid grid-cols-3 items-center w-full pb-1 px-1 border-t border-kalshi-border/30 pt-1 mt-1 relative z-10">'
replace_row3 = r'<div class="header-inner grid grid-cols-3 items-center w-full pb-1 px-1 border-t border-kalshi-border/30 pt-1 mt-0 relative z-10">'
html = re.sub(pattern_row3, replace_row3, html)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Updated HTML to compress header spacing!")
