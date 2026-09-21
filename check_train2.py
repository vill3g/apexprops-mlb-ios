import re

with open('backend/btc/ml_engine.py', 'r', encoding='utf-8') as f:
    code = f.read()

idx = code.find("def self_train_on_historical_market")
with open('out.txt', 'w', encoding='utf-8') as f:
    f.write(code[idx+2000:idx+4500])
