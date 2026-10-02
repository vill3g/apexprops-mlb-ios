with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

market_start = c.find('    <!-- Live Market & Chart -->')
balance_start = c.find('    <!-- Balance Card -->')
ledger_start = c.find('    <!-- Live Trades Ledger -->')

# The blocks
market_block = c[market_start:balance_start]
balance_block = c[balance_start:ledger_start]

# Swap them
c = c[:market_start] + balance_block + market_block + c[ledger_start:]

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
