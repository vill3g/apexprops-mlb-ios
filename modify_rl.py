import re

with open('backend/btc/rl_scalper.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Increase hidden dim
content = content.replace('def __init__(self, input_dim: int, action_dim: int = 4, hidden_dim: int = 128):', 
                          'def __init__(self, input_dim: int, action_dim: int = 4, hidden_dim: int = 512):')

with open('backend/btc/rl_scalper.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("rl_scalper.py modified")
