import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

match = re.search(r'Strategy Performance.*?</label>.*?<div class="grid grid-cols-2 gap-3 text-\[10px\] font-mono">(.*?)</div>\s*</div>', content, re.DOTALL)
if match:
    # Print the raw content but encode emojis to unicode escapes so powershell doesn't crash
    print(match.group(1).encode('unicode_escape').decode('utf-8'))
