
import os
path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\kalshi_client.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
with open(path, 'w', encoding='utf-8') as f:
    for line in lines:
        if 'time.sleep(1.0)' in line or 'Rate limit exceeded (429)' in line:
            continue
        f.write(line)

