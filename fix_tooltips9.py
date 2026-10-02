fpath = 'static/index.html'
with open(fpath, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    'onclick="toggleAdminGlassInfo(\\\'risk_position\\\', event)"',
    'onclick="toggleAdminGlassInfo(\'risk_position\', event)"'
)
text = text.replace(
    'onclick="toggleAdminGlassInfo(\\\'pred_confidence\\\', event)"',
    'onclick="toggleAdminGlassInfo(\'pred_confidence\', event)"'
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(text)
