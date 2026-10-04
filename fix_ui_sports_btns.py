import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace sports buttons
old_sports_btns = '''<button id="btn-asset-nfl" onclick="selectDashboardAsset('NFL')" class="asset-btn-sports hidden px-3 py-1.5 rounded-full text-xs font-bold transition-all bg-[#2a2b36] text-gray-400 hover:text-white border border-transparent">🏈 NFL</button>
        <button id="btn-asset-mlb" onclick="selectDashboardAsset('MLB')" class="asset-btn-sports hidden px-3 py-1.5 rounded-full text-xs font-bold transition-all bg-[#2a2b36] text-gray-400 hover:text-white border border-transparent">⚾ MLB</button>'''

new_sports_btns = '''<button id="btn-asset-nfl" onclick="selectDashboardAsset('NFL')" class="asset-btn-sports hidden px-2 py-1 rounded-md text-[11px] font-bold transition-all bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white border border-white/5">🏈 NFL</button>
<button id="btn-asset-mlb" onclick="selectDashboardAsset('MLB')" class="asset-btn-sports hidden px-2 py-1 rounded-md text-[11px] font-bold transition-all bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white border border-white/5">⚾ MLB</button>
<button id="btn-asset-nhl" onclick="selectDashboardAsset('NHL')" class="asset-btn-sports hidden px-2 py-1 rounded-md text-[11px] font-bold transition-all bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white border border-white/5">🏒 NHL</button>
<button id="btn-asset-nba" onclick="selectDashboardAsset('NBA')" class="asset-btn-sports hidden px-2 py-1 rounded-md text-[11px] font-bold transition-all bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white border border-white/5">🏀 NBA</button>
<button id="btn-asset-soccer" onclick="selectDashboardAsset('SOCCER')" class="asset-btn-sports hidden px-2 py-1 rounded-md text-[11px] font-bold transition-all bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white border border-white/5">⚽ SOC</button>
<button id="btn-asset-ufc" onclick="selectDashboardAsset('UFC')" class="asset-btn-sports hidden px-2 py-1 rounded-md text-[11px] font-bold transition-all bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white border border-white/5">🥊 UFC</button>
<button id="btn-asset-tennis" onclick="selectDashboardAsset('TENNIS')" class="asset-btn-sports hidden px-2 py-1 rounded-md text-[11px] font-bold transition-all bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white border border-white/5">🎾 TEN</button>'''

html = html.replace(old_sports_btns, new_sports_btns)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
