import re
import time

fpath = 'static/saas_dashboard.html'
with open(fpath, 'r', encoding='utf-8') as f:
    html = f.read()

# Bump dashboard.js version
new_version = f"?v={int(time.time())}"
html = re.sub(r'\?v=\d+', new_version, html)

# Add no-cache meta tags if not present
meta_tags = """    <meta charset="UTF-8">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
    <meta http-equiv="Pragma" content="no-cache" />
    <meta http-equiv="Expires" content="0" />"""
html = html.replace('<meta charset="UTF-8">', meta_tags)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(html)

fpath_index = 'static/index.html'
with open(fpath_index, 'r', encoding='utf-8') as f:
    html_idx = f.read()

html_idx = re.sub(r'\?v=\d+', new_version, html_idx)
html_idx = html_idx.replace('<meta charset="UTF-8">', meta_tags)

with open(fpath_index, 'w', encoding='utf-8') as f:
    f.write(html_idx)

print("Cache busted!")
