import os

html_path = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    c = f.read()

idx2 = c.find('<div id="sports-risk-settings"')
if idx2 != -1:
    print("Found sports-risk-settings HTML")
    print(repr(c[idx2-200:idx2]))
