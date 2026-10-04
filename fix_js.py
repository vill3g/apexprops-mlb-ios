import re
with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Fix the async syntax error
html = html.replace('async \nfunction toggleUniverse() {', 'function toggleUniverse() {')
html = html.replace('\nfunction selectDashboardAsset(asset) {', '\nasync function selectDashboardAsset(asset) {')

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Fixed JS Syntax Error')
