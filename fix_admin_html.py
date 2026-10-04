import re
with open('static/admin_mobile.html', 'r', encoding='utf-8') as f:
    html = f.read()

def replace_parse(match):
    parse_type, id_str, fallback = match.groups()
    return f"(!isNaN({parse_type}(document.getElementById('{id_str}').value)) ? {parse_type}(document.getElementById('{id_str}').value) : {fallback})"

html = re.sub(r"(parseFloat|parseInt)\(document\.getElementById\('([^']+)'\)\.value\) \|\| ([0-9.]+)", replace_parse, html)

with open('static/admin_mobile.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Fixed admin_mobile.html defaults')
