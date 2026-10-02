import re

with open('backend/btc/train_rl_scalper.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('ap.add_argument("--epochs", type=int, default=5)', 'ap.add_argument("--epochs", type=int, default=15)')

with open('backend/btc/train_rl_scalper.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Epochs modified")
