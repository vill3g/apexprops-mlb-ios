import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

html = html.replace('<div class="bg-[#0e1626] border-b lg:border lg:border-y-0 lg:border-kalshi-border lg:rounded-none border-white/5 px-2.5 py-2 sm:p-3 shadow-md flex items-center justify-between">', '<div id="stats-bar-target" class="bg-[#0e1626] border-b lg:border lg:border-y-0 lg:border-kalshi-border lg:rounded-none border-white/5 px-2.5 py-2 sm:p-3 shadow-md flex items-center justify-between">')

html = html.replace("document.getElementById('stats-bar')", "document.getElementById('stats-bar-target')")

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('added ID to stats bar')
