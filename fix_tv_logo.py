import re
html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Add a cover div for the TradingView logo
overlay = '\n                <!-- Cover TV Logo -->\n                <div class="absolute bottom-0 left-0 w-24 h-8 bg-[#131b2c] z-50 pointer-events-none"></div>'
html = html.replace(
    '<div id="tradingview_btc_chart" style="height: 100%; width: 100%;"></div>',
    '<div id="tradingview_btc_chart" style="height: 100%; width: 100%;"></div>' + overlay
)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Added TV logo cover div.")
