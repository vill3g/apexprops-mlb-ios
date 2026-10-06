import os

html_path = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    c = f.read()

idx = c.find('<div id="finance-risk-settings">')
if idx != -1:
    print("Found finance-risk-settings HTML")
    print(repr(c[idx-200:idx]))
