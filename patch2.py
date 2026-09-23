import re
with open('static/saas_dashboard.html', 'r') as f:
    html = f.read()

html = re.sub(
    r'alert\(`Failed: \$\{(.+?)\}`\);',
    r'let _err = \1; if (typeof _err === "object") _err = JSON.stringify(_err); alert(`Failed: ${_err}`);',
    html
)
html = re.sub(
    r'alert\(`Failed to save keys: \$\{(.+?)\}`\);',
    r'let _err = \1; if (typeof _err === "object") _err = JSON.stringify(_err); alert(`Failed to save keys: ${_err}`);',
    html
)

with open('static/saas_dashboard.html', 'w') as f:
    f.write(html)
