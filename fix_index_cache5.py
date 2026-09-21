with open('static/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('app.js?v=7', 'app.js?v=8')

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
