import re
with open('backend/btc/ml_engine.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('"vol_regime_percentile",,\n', '"vol_regime_percentile",\n')

with open('backend/btc/ml_engine.py', 'w', encoding='utf-8') as f:
    f.write(code)
