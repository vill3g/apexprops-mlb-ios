import re

html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Add a slight negative margin to pull PNL closer to BAL
pattern_pnl_row = r'<div class="flex items-baseline gap-1\.5">\s*<span class="text-\[10px\] sm:text-xs text-gray-500 uppercase font-bold tracking-wider shrink-0">PNL</span>'
replace_pnl_row = r'<div class="flex items-baseline gap-1.5 -mt-0.5">\n                    <span class="text-[10px] sm:text-xs text-gray-500 uppercase font-bold tracking-wider shrink-0">PNL</span>'
html = re.sub(pattern_pnl_row, replace_pnl_row, html)

# And remove margin top entirely from the border
pattern_row3 = r'pt-1 mt-0 relative'
replace_row3 = r'pt-0.5 mt-0 relative'
html = re.sub(pattern_row3, replace_row3, html)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Updated HTML to compress header spacing further!")
