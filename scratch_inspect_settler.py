import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('backend/saas_settler.py', 'r', encoding='utf-8') as f:
    text = f.read()

pos = text.find('def settle_user_trades')
if pos == -1:
    pos = text.find('settle_user')
if pos == -1:
    pos = text.find('def settle')
print('pos:', pos)
print(text[pos:pos+2500])
