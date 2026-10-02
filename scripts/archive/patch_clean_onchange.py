import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('onchange="saveUserConfig()"\n', '')
content = content.replace('onchange="saveUserConfig()">', '>')
content = content.replace('oninput="saveUserConfig()" class="w-16 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-xs text-white font-bold text-center focus:border-kalshi-blue focus:outline-none" min="1" max="100" inputmode="numeric" >', 'oninput="saveUserConfig()" class="w-16 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-xs text-white font-bold text-center focus:border-kalshi-blue focus:outline-none" min="1" max="100" inputmode="numeric">')
content = content.replace('oninput="saveUserConfig()" class="w-16 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-xs text-white font-bold text-center focus:border-kalshi-blue focus:outline-none" min="1" max="1000" inputmode="numeric" >', 'oninput="saveUserConfig()" class="w-16 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-xs text-white font-bold text-center focus:border-kalshi-blue focus:outline-none" min="1" max="1000" inputmode="numeric">')

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
