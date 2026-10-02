import re

js_path = "static/js/dashboard.js"
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

# Fix the Binance tick size bug
pattern1 = r'pnlEl\.className = `text-xs sm:text-sm font-black tabular-nums truncate \$\{liveTotalPnl >= 0 \? \'text-emerald-400\' : \'text-rose-400\'\}`;'
replace1 = r'pnlEl.className = `text-sm sm:text-base font-black tabular-nums truncate ${liveTotalPnl >= 0 ? \'text-emerald-400\' : \'text-rose-400\'}`;'
js = re.sub(pattern1, replace1, js)

with open(js_path, "w", encoding="utf-8") as f:
    f.write(js)
print("Updated dashboard.js val-pnl size!")
