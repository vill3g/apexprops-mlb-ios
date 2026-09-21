import re

with open('static/js/app.js', 'r', encoding='utf-8') as f:
    app = f.read()

idx = app.find("function initAccuracyTooltip")
with open('out.txt', 'w', encoding='utf-8') as f:
    f.write(app[idx:idx+2000])
