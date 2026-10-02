
import re
with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("checked ? false", "checked || false")

with open("static/saas_dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)

