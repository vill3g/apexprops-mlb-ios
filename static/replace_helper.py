import sys

file_path = r'C:\Users\Vill3\Desktop\ShadowTraderAi\static\saas_dashboard.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Buttons
btn_ndq = '''                <button type="button" id="btn-asset-ndq" onclick="selectDashboardAsset('NDQ')" class="asset-btn flex-1 py-1 px-2 rounded-md text-[11px] font-bold transition-all flex items-center justify-center gap-1 border cursor-pointer bg-white/5 text-gray-400 border-white/5 hover:bg-white/10 hover:text-gray-200">
                    <span class="text-[11px]">📈</span> <span>NDQ</span>
                </button>'''
btn_repl = btn_ndq + '''
                <button type="button" id="btn-asset-sol" onclick="selectDashboardAsset('SOL')" class="asset-btn flex-1 py-1 px-2 rounded-md text-[11px] font-bold transition-all flex items-center justify-center gap-1 border cursor-pointer bg-white/5 text-gray-400 border-white/5 hover:bg-white/10 hover:text-gray-200">
                    <span class="text-[11px]">◎</span> <span>SOL</span>
                </button>
                <button type="button" id="btn-asset-doge" onclick="selectDashboardAsset('DOGE')" class="asset-btn flex-1 py-1 px-2 rounded-md text-[11px] font-bold transition-all flex items-center justify-center gap-1 border cursor-pointer bg-white/5 text-gray-400 border-white/5 hover:bg-white/10 hover:text-gray-200">
                    <span class="text-[11px]">🐕</span> <span>DOGE</span>
                </button>'''
content = content.replace(btn_ndq, btn_repl)

# 2. activeAssets.push
push_ndq = "            if(document.getElementById('asset-ndq-toggle')?.checked) activeAssets.push('NDQ');"
push_repl = push_ndq + '''
            if(document.getElementById('asset-sol-toggle')?.checked) activeAssets.push('SOL');
            if(document.getElementById('asset-doge-toggle')?.checked) activeAssets.push('DOGE');'''
content = content.replace(push_ndq, push_repl)

# 3. toggles var
togg_ndq = "                const ndqToggle = document.getElementById('asset-ndq-toggle');"
togg_repl = togg_ndq + '''
                const solToggle = document.getElementById('asset-sol-toggle');
                const dogeToggle = document.getElementById('asset-doge-toggle');'''
content = content.replace(togg_ndq, togg_repl)

# 4. toggles set
tset_ndq = "                if(ndqToggle) ndqToggle.checked = assets.includes('NDQ');"
tset_repl = tset_ndq + '''
                if(solToggle) solToggle.checked = assets.includes('SOL');
                if(dogeToggle) dogeToggle.checked = assets.includes('DOGE');'''
content = content.replace(tset_ndq, tset_repl)

# 5. badge 1
bdg_ndq = "                                        else if (assetType === 'NDQ') { assetBadgeClass = 'bg-blue-500/20 text-blue-300 border-blue-500/40'; assetIcon = '📈 '; }"
bdg_repl = bdg_ndq + '''
                                        else if (assetType === 'SOL') { assetBadgeClass = 'bg-purple-500/20 text-purple-300 border-purple-500/40'; assetIcon = '◎ '; }
                                        else if (assetType === 'DOGE') { assetBadgeClass = 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40'; assetIcon = '🐕 '; }'''
content = content.replace(bdg_ndq, bdg_repl)

# 6. assetSpotPrices
spot_ndq = "        window.assetSpotPrices = { 'BTC': null, 'ETH': null, 'GOLD': null, 'EURUSD': null, 'GBPUSD': null, 'USDJPY': null, 'AUDUSD': null, 'NDQ': null };"
spot_repl = "        window.assetSpotPrices = { 'BTC': null, 'ETH': null, 'GOLD': null, 'EURUSD': null, 'GBPUSD': null, 'USDJPY': null, 'AUDUSD': null, 'NDQ': null, 'SOL': null, 'DOGE': null };"
content = content.replace(spot_ndq, spot_repl)

# 7. forEach array
arr_ndq = "            ['BTC', 'ETH', 'GOLD', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'NDQ'].forEach(a => {"
arr_repl = "            ['BTC', 'ETH', 'GOLD', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'NDQ', 'SOL', 'DOGE'].forEach(a => {"
content = content.replace(arr_ndq, arr_repl)

# 8. badge 2
bdg2_ndq = "                else if (asset === 'NDQ') { assetBadgeClass = 'bg-blue-500/20 text-blue-300 border-blue-500/40'; assetIcon = '📈 '; }"
bdg2_repl = bdg2_ndq + '''
                else if (asset === 'SOL') { assetBadgeClass = 'bg-purple-500/20 text-purple-300 border-purple-500/40'; assetIcon = '◎ '; }
                else if (asset === 'DOGE') { assetBadgeClass = 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40'; assetIcon = '🐕 '; }'''
content = content.replace(bdg2_ndq, bdg2_repl)

# 9. settings UI
set_ndq = '''                            <!-- NDQ -->
                            <div class="flex flex-col items-center flex-1 bg-black/30 p-2 rounded-lg border border-white/[0.05]">
                                <span class="text-[10px] font-bold text-blue-400 mb-1.5">NDQ</span>
                                <label class="relative inline-flex items-center cursor-pointer scale-[0.75]">
                                    <input type="checkbox" id="asset-ndq-toggle" class="sr-only peer asset-toggle" value="NDQ" onchange="saveUserConfig()">
                                    <div class="w-11 h-6 bg-gray-700/80 rounded-full peer peer-checked:after:translate-x-5 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-500"></div>
                                </label>
                            </div>'''
set_repl = set_ndq + '''
                            <!-- SOL -->
                            <div class="flex flex-col items-center flex-1 bg-black/30 p-2 rounded-lg border border-white/[0.05]">
                                <span class="text-[10px] font-bold text-purple-400 mb-1.5">SOL</span>
                                <label class="relative inline-flex items-center cursor-pointer scale-[0.75]">
                                    <input type="checkbox" id="asset-sol-toggle" class="sr-only peer asset-toggle" value="SOL" onchange="saveUserConfig()">
                                    <div class="w-11 h-6 bg-gray-700/80 rounded-full peer peer-checked:after:translate-x-5 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-500"></div>
                                </label>
                            </div>
                            <!-- DOGE -->
                            <div class="flex flex-col items-center flex-1 bg-black/30 p-2 rounded-lg border border-white/[0.05]">
                                <span class="text-[10px] font-bold text-yellow-400 mb-1.5">DOGE</span>
                                <label class="relative inline-flex items-center cursor-pointer scale-[0.75]">
                                    <input type="checkbox" id="asset-doge-toggle" class="sr-only peer asset-toggle" value="DOGE" onchange="saveUserConfig()">
                                    <div class="w-11 h-6 bg-gray-700/80 rounded-full peer peer-checked:after:translate-x-5 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-yellow-500"></div>
                                </label>
                            </div>'''
content = content.replace(set_ndq, set_repl)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Replacement complete.')
