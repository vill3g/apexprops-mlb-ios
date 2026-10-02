with open('static/js/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('const cdPill = document.getElementById("btcCountdownPill");', 'const cdPill = document.getElementById("topBarCountdownCard") || document.getElementById("btcCountdownPill");')

with open('static/js/app.js', 'w', encoding='utf-8') as f:
    f.write(content)
