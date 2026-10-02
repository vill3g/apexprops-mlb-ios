import re
path = "static/saas_dashboard.html"
with open(path, "r", encoding="utf-8") as f:
    html = f.read()

# Add leading-none to the large numbers to compress vertical spacing
html = html.replace('id="val-balance" class="text-sm sm:text-base font-black tabular-nums text-white tracking-tight truncate"', 'id="val-balance" class="text-sm sm:text-base font-black tabular-nums text-white tracking-tight truncate leading-none"')
html = html.replace('id="val-pnl" class="text-sm sm:text-base font-black tabular-nums text-gray-400 truncate"', 'id="val-pnl" class="text-sm sm:text-base font-black tabular-nums text-gray-400 truncate leading-none"')
html = html.replace('id="val-open-pnl" class="text-sm sm:text-base font-black tabular-nums text-gray-400 truncate"', 'id="val-open-pnl" class="text-sm sm:text-base font-black tabular-nums text-gray-400 truncate leading-none"')
html = html.replace('id="val-winrate" class="text-sm sm:text-base font-black tabular-nums text-gray-300 truncate"', 'id="val-winrate" class="text-sm sm:text-base font-black tabular-nums text-gray-300 truncate leading-none"')
html = html.replace('id="live-btc-price" class="text-sm sm:text-base font-black tabular-nums text-white tracking-tight truncate"', 'id="live-btc-price" class="text-sm sm:text-base font-black tabular-nums text-white tracking-tight truncate leading-none"')
html = html.replace('id="kalshi-target" class="text-sm sm:text-base font-mono font-bold text-kalshi-blue tabular-nums"', 'id="kalshi-target" class="text-sm sm:text-base font-mono font-bold text-kalshi-blue tabular-nums leading-none"')
html = html.replace('id="time-left" class="text-sm sm:text-base font-black tabular-nums text-blue-600 truncate"', 'id="time-left" class="text-sm sm:text-base font-black tabular-nums text-blue-600 truncate leading-none"')

# Also let's tighten the flex columns
html = html.replace('class="flex items-baseline gap-1.5 -mt-0.5"', 'class="flex items-baseline gap-1.5 -mt-1"')
html = html.replace('<div class="header-inner grid grid-cols-[45%_30%_25%] items-center w-full pb-1 px-1 border-t border-kalshi-border/30 pt-0.5 mt-0 relative z-10">', '<div class="header-inner grid grid-cols-[45%_30%_25%] items-center w-full pb-1 px-1 border-t border-kalshi-border/30 pt-1 -mt-1 relative z-10">')

with open(path, "w", encoding="utf-8") as f:
    f.write(html)
print("Updated leading-none and margins to close gap")
