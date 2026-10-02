import re
path = "static/saas_dashboard.html"
with open(path, "r", encoding="utf-8") as f:
    html = f.read()

# Add leading-none to labels to completely nuke all invisible vertical whitespace
html = html.replace('class="text-[10px] sm:text-xs text-gray-500 uppercase font-bold tracking-wider shrink-0"', 'class="text-[10px] sm:text-xs text-gray-500 uppercase font-bold tracking-wider shrink-0 leading-none"')

with open(path, "w", encoding="utf-8") as f:
    f.write(html)
print("Updated labels to leading-none")
