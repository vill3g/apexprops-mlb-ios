import re

html_path = r'C:\Users\Vill3\Desktop\ShadowTraderAi\static\saas_dashboard.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# Fix the base classes in the JS script
html = html.replace('btn.className = sset-btn flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 border cursor-pointer ;',
                    'btn.className = sset-btn flex-1 py-1 px-2 rounded-md text-[11px] font-bold transition-all flex items-center justify-center gap-1 border cursor-pointer ;')

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated JS classes in saas_dashboard.html")
