with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace(
    '"balance_dollars": balance_dollars,',
    '"balance_dollars": balance_dollars,\n        "trading_mode": trading_mode,'
)

with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(c)
