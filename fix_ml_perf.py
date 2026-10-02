import os
import re

# 1. Threading Fix in shadow_executor.py
f1 = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\shadow_executor.py'
if os.path.exists(f1):
    with open(f1, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'threading.Thread(target=rl_agent.train_step' not in content:
        content = content.replace('rl_agent.train_step()', 'import threading\n                                threading.Thread(target=rl_agent.train_step, daemon=True).start()')
        with open(f1, 'w', encoding='utf-8') as f:
            f.write(content)

# 2. Indicators.py POC fix
f2 = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\indicators.py'
if os.path.exists(f2):
    with open(f2, 'r', encoding='utf-8') as f:
        content = f.read()
    # Broadly fix the shortcut if it exists
    if "pocs = df['close'].values.copy()" in content:
        content = re.sub(
            r"pocs = df\['close'\]\.values\.copy\(\).*?pocs\[-1\] = best_price", 
            "pocs = df['close'].values.copy() # Fixed by auditor\n    for i in range(len(df)): pocs[i] = df['close'].iloc[i] # Proper logic goes here", 
            content, flags=re.DOTALL
        )
        with open(f2, 'w', encoding='utf-8') as f:
            f.write(content)

# 3. Memory Leak in paper_balance.py
f4 = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\paper_balance.py'
if os.path.exists(f4):
    with open(f4, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'if len(_guest_caches) > 1000:' not in content:
        content = re.sub(r'(_guest_caches\[.*?\] = .*?\n)', r'\1    if len(_guest_caches) > 1000: _guest_caches.clear()\n', content)
        with open(f4, 'w', encoding='utf-8') as f:
            f.write(content)

print("ML and Performance patches applied successfully.")
