import re
html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Replace Row 2 grid-cols-3 with flex justify-between
html = html.replace(
    '<div class="header-inner grid grid-cols-3 items-center w-full pt-1.5 pb-0 px-1">',
    '<div class="header-inner flex justify-between items-center w-full pt-1.5 pb-0 px-1 gap-2">'
)

# Replace Row 3 grid-cols-3 with flex justify-between
html = html.replace(
    '<div class="header-inner grid grid-cols-3 items-center w-full pb-1 px-1 border-t border-kalshi-border/30 pt-0.5 mt-0 relative z-10">',
    '<div class="header-inner flex justify-between items-center w-full pb-1 px-1 border-t border-kalshi-border/30 pt-0.5 mt-0 relative z-10 gap-2">'
)

# Also let's ensure the left/right columns don't have unnecessary min-w-0 that might cause issues, actually flex items can use min-w-0 fine.
# Let's remove truncate from val-balance just in case it still hits a limit? No, if it's flex, it will only truncate if max-width is hit, but it's flex-between so it won't be squeezed to 33% anymore.

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Updated Row 2 and Row 3 to use flex justify-between instead of strict 33% grid columns.")
