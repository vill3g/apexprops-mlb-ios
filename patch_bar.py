import re

html_path = r'C:\Users\Vill3\Desktop\ShadowTraderAi\static\saas_dashboard.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# Make the asset selector shorter and change buttons
html = html.replace('id="assetSelectorBar" class="sticky top-[calc(3.5rem+env(safe-area-inset-top,0px))] z-40 bg-[#0b101d] border-b border-kalshi-border/60 px-3 py-2 flex items-center justify-between gap-3 shadow-inner"',
                   'id="assetSelectorBar" class="sticky z-40 bg-[#0b101d] border-b border-white/5 px-2 py-1 flex items-center justify-between gap-2 shadow-inner" style="top: calc(3.6rem + env(safe-area-inset-top, 0px));"')

# Fix buttons padding
html = html.replace('class="asset-btn flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 border cursor-pointer bg-orange-500/25 text-orange-300 border-orange-500/50 shadow-[0_0_12px_rgba(249,115,22,0.2)]"',
                    'class="asset-btn flex-1 py-1 px-2 rounded-md text-[11px] font-bold transition-all flex items-center justify-center gap-1 border cursor-pointer bg-orange-500/25 text-orange-300 border-orange-500/50 shadow-[0_0_12px_rgba(249,115,22,0.2)]"')

html = html.replace('class="asset-btn flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 border cursor-pointer bg-white/5 text-gray-400 border-white/5 hover:bg-white/10 hover:text-gray-200"',
                    'class="asset-btn flex-1 py-1 px-2 rounded-md text-[11px] font-bold transition-all flex items-center justify-center gap-1 border cursor-pointer bg-white/5 text-gray-400 border-white/5 hover:bg-white/10 hover:text-gray-200"')

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated asset bar HTML.")
