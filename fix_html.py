import re
with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Fix the malformed HTML
bad_html = '''<button type="button" 
        <button id="btn-asset-nfl"'''
good_html = '''        <button id="btn-asset-nfl"'''
html = html.replace(bad_html, good_html)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Fixed Malformed HTML')
