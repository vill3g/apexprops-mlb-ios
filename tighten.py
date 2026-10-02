import re
path = "static/saas_dashboard.html"
with open(path, "r", encoding="utf-8") as f:
    html = f.read()

html = html.replace('pt-1 -mt-1', 'pt-0.5 -mt-1')

with open(path, "w", encoding="utf-8") as f:
    f.write(html)
