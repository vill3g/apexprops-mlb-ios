import re

with open('backend/main.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('from backend.saas_settler import settle_saas_trades', 'from backend.saas_settler import settle_saas_trades, process_auto_force_trades')
c = c.replace('settle_saas_trades()', 'settle_saas_trades()\n                    process_auto_force_trades()')

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(c)
