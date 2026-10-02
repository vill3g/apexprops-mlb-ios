import re

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Replace risk_amount calculation with trade_size_dollars
# OLD: risk_amount = avail_bal * (float(user.get("trade_size_pct", 20.0)) / 100.0)
c = re.sub(
    r'risk_amount = avail_bal \* \(float\(user\.get\("trade_size_pct", 20\.0\)\) / 100\.0\)',
    r'risk_amount = float(user.get("trade_size_dollars", 50.0))',
    c
)

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(c)
    
with open('backend/saas_settler.py', 'r', encoding='utf-8') as f:
    s = f.read()
    
# OLD: trade_size_pct = float(user.get("trade_size_pct", 20.0)) / 100.0
# OLD: risk_amount = avail_bal * trade_size_pct
s = re.sub(
    r'trade_size_pct = float\(user\.get\("trade_size_pct", 20\.0\)\) / 100\.0\n.*?risk_amount = avail_bal \* trade_size_pct',
    r'risk_amount = float(user.get("trade_size_dollars", 50.0))',
    s, flags=re.DOTALL
)

with open('backend/saas_settler.py', 'w', encoding='utf-8') as f:
    f.write(s)
