import re
html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Row 2
html = html.replace(
    '<div class="header-inner flex justify-between items-center w-full pt-1.5 pb-0 px-1 gap-2">',
    '<div class="header-inner grid grid-cols-[45%_30%_25%] items-center w-full pt-1.5 pb-0 px-1">'
)
# If it had no gap-2 just in case
html = html.replace(
    '<div class="header-inner flex justify-between items-center w-full pt-1.5 pb-0 px-1">',
    '<div class="header-inner grid grid-cols-[45%_30%_25%] items-center w-full pt-1.5 pb-0 px-1">'
)

# Row 3
html = html.replace(
    '<div class="header-inner flex justify-between items-center w-full pb-1 px-1 border-t border-kalshi-border/30 pt-0.5 mt-0 relative z-10 gap-2">',
    '<div class="header-inner grid grid-cols-[45%_30%_25%] items-center w-full pb-1 px-1 border-t border-kalshi-border/30 pt-0.5 mt-0 relative z-10">'
)
html = html.replace(
    '<div class="header-inner flex justify-between items-center w-full pb-1 px-1 border-t border-kalshi-border/30 pt-0.5 mt-0 relative z-10">',
    '<div class="header-inner grid grid-cols-[45%_30%_25%] items-center w-full pb-1 px-1 border-t border-kalshi-border/30 pt-0.5 mt-0 relative z-10">'
)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Updated grid")
