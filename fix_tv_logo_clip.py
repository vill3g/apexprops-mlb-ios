import re
html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

css_rule = """
        /* Magically hide TradingView logo via a precise CSS clip-path notch on the iframe */
        #tradingview_btc_chart iframe {
            clip-path: polygon(0 0, 100% 0, 100% 100%, 0 100%, 0 calc(100% - 25px), 65px calc(100% - 25px), 65px calc(100% - 75px), 0 calc(100% - 75px));
        }
"""

html = html.replace("</style>", css_rule + "</style>")

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Added iframe clip-path CSS.")
