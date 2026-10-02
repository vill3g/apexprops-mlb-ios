import os

html_path = 'static/saas_dashboard.html'
js_path = 'static/js/dashboard.js'
css_path = 'static/css/dashboard.css'

os.makedirs('static/js', exist_ok=True)
os.makedirs('static/css', exist_ok=True)

with open(html_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_html = []
css_lines = []
js_lines = []

in_css = False
in_js1 = False
in_js2 = False

for i, line in enumerate(lines):
    idx = i + 1
    
    if idx == 53:
        in_css = True
        new_html.append('    <link rel="stylesheet" href="/static/css/dashboard.css">\n')
        continue
    elif idx == 163:
        in_css = False
        continue
    elif in_css:
        css_lines.append(line)
        continue
        
    if idx == 953:
        in_js1 = True
        new_html.append('    <script src="/static/js/dashboard.js"></script>\n')
        continue
    elif idx == 2828:
        in_js1 = False
        continue
    elif in_js1:
        js_lines.append(line)
        continue
        
    if idx == 3146:
        in_js2 = True
        continue
    elif idx == 3714:
        in_js2 = False
        continue
    elif in_js2:
        js_lines.append(line)
        continue
        
    new_html.append(line)

with open(css_path, 'w', encoding='utf-8') as f:
    f.writelines(css_lines)
    
with open(js_path, 'w', encoding='utf-8') as f:
    f.writelines(js_lines)

with open(html_path, 'w', encoding='utf-8') as f:
    f.writelines(new_html)

print(f"Extracted {len(css_lines)} lines to css")
print(f"Extracted {len(js_lines)} lines to js")
print(f"New HTML is {len(new_html)} lines")
