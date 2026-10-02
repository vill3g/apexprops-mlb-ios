import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace any corrupted emoji in the AI coach modal
content = re.sub(r'<div class="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-lg shadow-\[0_0_15px_rgba\(245,158,11,0\.2\)\]">.*?</div>', '<div class="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-lg shadow-[0_0_15px_rgba(245,158,11,0.2)]">??</div>', content)

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Replaced modal emoji!")
