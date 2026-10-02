import re

html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Swap buttons
pattern1 = r'(<button id="btn-chart-candle".*?</button>)\s*(<button id="btn-chart-line".*?</button>)'
html = re.sub(pattern1, r'\2\n                    \1', html, flags=re.DOTALL)

# Change classes for line and candle
# We know the first button was candle, it has "bg-kalshi-blue text-white shadow-sm"
# The second was line, it has "text-gray-400 hover:text-white hover:bg-white/5"
html = html.replace('id="btn-chart-candle" onclick="setChartStyle(\'1\')" class="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider transition-all bg-kalshi-blue text-white shadow-sm flex items-center gap-1"', 'id="btn-chart-candle" onclick="setChartStyle(\'1\')" class="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider transition-all text-gray-400 hover:text-white hover:bg-white/5 flex items-center gap-1"')

html = html.replace('id="btn-chart-line" onclick="setChartStyle(\'2\')" class="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider transition-all text-gray-400 hover:text-white hover:bg-white/5 flex items-center gap-1"', 'id="btn-chart-line" onclick="setChartStyle(\'2\')" class="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider transition-all bg-kalshi-blue text-white shadow-sm flex items-center gap-1"')

# Change classes for 15m
html = html.replace('id="btn-chart-15m" onclick="setChartInterval(\'15\')" class="px-2 py-1 rounded text-[10px] font-mono font-bold uppercase tracking-wider transition-all bg-kalshi-blue text-white shadow-sm"', 'id="btn-chart-15m" onclick="setChartInterval(\'15\')" class="px-2 py-1 rounded text-[10px] font-mono font-bold uppercase tracking-wider transition-all text-gray-400 hover:text-white hover:bg-white/5"')

# Change classes for 1m (wait, it might already be changed by the previous run)
html = html.replace('id="btn-chart-1m" onclick="setChartInterval(\'1\')" class="px-2 py-1 rounded text-[10px] font-mono font-bold uppercase tracking-wider transition-all text-gray-400 hover:text-white hover:bg-white/5"', 'id="btn-chart-1m" onclick="setChartInterval(\'1\')" class="px-2 py-1 rounded text-[10px] font-mono font-bold uppercase tracking-wider transition-all bg-kalshi-blue text-white shadow-sm"')

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

js_path = "static/js/dashboard.js"
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

js = js.replace('let currentChartStyle = "1";', 'let currentChartStyle = "2";')
js = js.replace('let currentChartInterval = "15";', 'let currentChartInterval = "1";')

with open(js_path, "w", encoding="utf-8") as f:
    f.write(js)
