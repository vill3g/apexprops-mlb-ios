import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\backend\\saas_settler.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Paper trading
content = content.replace(
    'sl = max(0.01, float(user.get("stop_loss_pct", 50.0)) / 100.0)',
    'sl_enabled = bool(user.get("stop_loss_enabled", 1))\n        sl = max(0.01, float(user.get("stop_loss_pct", 50.0)) / 100.0)'
)
content = content.replace(
    'if ((entry - mid) / entry >= sl and age >= STOP_LOSS_GRACE_SECONDS) or \\',
    'if (sl_enabled and (entry - mid) / entry >= sl and age >= STOP_LOSS_GRACE_SECONDS) or \\'
)

# 2. Live trading setup
content = content.replace(
    'sl_pct = max(0.01, float(user.get("stop_loss_pct", 50.0)) / 100.0)',
    'sl_pct = max(0.01, float(user.get("stop_loss_pct", 50.0)) / 100.0)\n                        sl_enabled = bool(user.get("stop_loss_enabled", 1))'
)

# 3. Live trading eval
content = content.replace(
    'if loss_pct >= sl_pct and not in_grace_period:',
    'if sl_enabled and loss_pct >= sl_pct and not in_grace_period:'
)

# 4. Live trading fresh quote verification
content = content.replace(
    'still = f_loss >= sl_pct',
    'still = sl_enabled and f_loss >= sl_pct'
)


with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\backend\\saas_settler.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated saas_settler.py!")
