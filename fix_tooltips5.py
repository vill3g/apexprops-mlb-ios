import re
fpath = 'static/js/admin_users.js'
with open(fpath, 'r', encoding='utf-8') as f:
    text = f.read()

# Fix the escaped quotes
text = text.replace(
    'onclick="toggleAdminGlassInfo(\\\'auto_trader\\\', event)"',
    'onclick="toggleAdminGlassInfo(\'auto_trader\', event)"'
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(text)
