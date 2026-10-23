import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('static/js/admin_users.js', 'r', encoding='utf-8') as f:
    text = f.read()

pos = text.find('async function loadUserTrades')
print(text[pos:pos+2500])
