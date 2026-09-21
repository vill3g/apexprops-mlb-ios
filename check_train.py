import re

with open('backend/btc/ml_engine.py', 'r', encoding='utf-8') as f:
    code = f.read()

idx = code.find("def self_train_on_historical_market")
if idx != -1:
    with open('out.txt', 'w', encoding='utf-8') as f:
        f.write(code[idx:idx+2500])
