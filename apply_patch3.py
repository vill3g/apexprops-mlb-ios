with open('backend/sports_bridge/executor.py', 'r') as f:
    code = f.read()

if 'order_intents' not in code[:1000]:
    code = code.replace('from backend.database.models import (', 'from backend.database import order_intents\nfrom backend.btc.fees import kalshi_order_fee, net_pnl\nfrom backend.database.models import (')

with open('backend/sports_bridge/executor.py', 'w') as f:
    f.write(code)
