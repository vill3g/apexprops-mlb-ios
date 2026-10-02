import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('<span class="text-gray-400 font-bold tracking-wider">SNIPER</span>', '<span class="text-gray-400 font-bold tracking-wider">?? SNIPER</span>')
content = content.replace('<span class="text-gray-400 font-bold tracking-wider">AMBUSH</span>', '<span class="text-gray-400 font-bold tracking-wider">?? AMBUSH</span>')
content = content.replace('<span class="text-gray-400 font-bold tracking-wider">CHOP</span>', '<span class="text-gray-400 font-bold tracking-wider">?? CHOP</span>')
content = content.replace('<span class="text-gray-400 font-bold tracking-wider">MOMENTUM</span>', '<span class="text-gray-400 font-bold tracking-wider">?? MOMENTUM</span>')
content = content.replace('<span class="text-gray-400 font-bold tracking-wider">SCALPER</span>', '<span class="text-gray-400 font-bold tracking-wider">? SCALPER</span>')

# Also fix PREDICTION just in case the emoji was corrupted or missing
content = re.sub(r'<span class="text-gray-400 font-bold tracking-wider">.*?PREDICTION</span>', '<span class="text-gray-400 font-bold tracking-wider">?? PREDICTION</span>', content)

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Replaced!")
