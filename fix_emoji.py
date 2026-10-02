
import re
with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("Trade Won! �YZ%", "Trade Won! ??")
content = content.replace("Trade Won! YZ%", "Trade Won! ??")

with open("static/saas_dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)

