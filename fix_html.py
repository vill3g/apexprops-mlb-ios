import os
filepath = 'static/saas_dashboard.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('src="js/app.js?v=2.6"', 'src="js/app.js?v=2.7"')
content = content.replace('src="js/app.js?v=2.5"', 'src="js/app.js?v=2.7"')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("done html")
