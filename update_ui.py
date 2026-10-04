import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add Universe Toggle in Header (Near User Balance)
header_injection = '''
            <div class="flex items-center space-x-2 mr-4">
                <span class="text-xs font-semibold text-gray-400">UNIVERSE:</span>
                <select id="universe-select" onchange="toggleUniverse()" class="bg-[#1a1b23] border border-gray-700 text-xs font-bold rounded px-2 py-1 focus:outline-none">
                    <option value="FINANCIAL">📈 FINANCIALS</option>
                    <option value="SPORTS">🏈 SPORTS</option>
                </select>
            </div>
'''
if 'id="universe-select"' not in html:
    html = html.replace('<div class="flex items-center space-x-3">', '<div class="flex items-center space-x-3">\n' + header_injection)

# 2. Add Javascript toggleUniverse logic
js_injection = '''
function toggleUniverse() {
    const universe = document.getElementById('universe-select').value;
    const finAssets = document.querySelectorAll('.asset-btn-financial');
    const sportsAssets = document.querySelectorAll('.asset-btn-sports');
    const stopLossDiv = document.getElementById('stop-loss-container');
    const sportsConfDiv = document.getElementById('sports-confidence-container');
    
    if(universe === 'SPORTS') {
        finAssets.forEach(el => el.classList.add('hidden'));
        sportsAssets.forEach(el => el.classList.remove('hidden'));
        if(stopLossDiv) stopLossDiv.classList.add('hidden');
        if(sportsConfDiv) sportsConfDiv.classList.remove('hidden');
    } else {
        finAssets.forEach(el => el.classList.remove('hidden'));
        sportsAssets.forEach(el => el.classList.add('hidden'));
        if(stopLossDiv) stopLossDiv.classList.remove('hidden');
        if(sportsConfDiv) sportsConfDiv.classList.add('hidden');
    }
}
'''
if 'function toggleUniverse' not in html:
    html = html.replace('function selectDashboardAsset(asset) {', js_injection + '\nfunction selectDashboardAsset(asset) {')

# 3. Mark existing asset buttons as financial, add sports buttons
html = html.replace('id="btn-asset-btc" class="', 'id="btn-asset-btc" class="asset-btn-financial ')
html = html.replace('id="btn-asset-eth" class="', 'id="btn-asset-eth" class="asset-btn-financial ')
html = html.replace('id="btn-asset-gold" class="', 'id="btn-asset-gold" class="asset-btn-financial ')
# Add sports buttons
sports_btns = '''
        <button id="btn-asset-nfl" onclick="selectDashboardAsset('NFL')" class="asset-btn-sports hidden px-3 py-1.5 rounded-full text-xs font-bold transition-all bg-[#2a2b36] text-gray-400 hover:text-white border border-transparent">🏈 NFL</button>
        <button id="btn-asset-mlb" onclick="selectDashboardAsset('MLB')" class="asset-btn-sports hidden px-3 py-1.5 rounded-full text-xs font-bold transition-all bg-[#2a2b36] text-gray-400 hover:text-white border border-transparent">⚾ MLB</button>
'''
if 'btn-asset-nfl' not in html:
    html = html.replace('id="btn-asset-gold"', sports_btns + '\n        <button id="btn-asset-gold"')

# 4. Add Sports Confidence Setting UI
sports_conf_ui = '''
                            <!-- Sports Confidence -->
                            <div id="sports-confidence-container" class="hidden bg-[#1f2029] p-3 rounded-lg border border-gray-800">
                                <div class="flex justify-between items-center mb-1">
                                    <label class="text-xs font-bold text-gray-300">Minimum Pick Confidence (%)</label>
                                    <span id="sports-conf-val" class="text-xs font-mono text-[#00ff88]">70.0%</span>
                                </div>
                                <span class="text-[10px] text-gray-400 block mb-3">Only take sports bets where AI confidence exceeds this threshold.</span>
                                <input type="range" id="sports-conf-slider" min="50" max="95" step="1" value="70" class="w-full h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer" oninput="document.getElementById('sports-conf-val').innerText = this.value + '.0%'">
                            </div>
'''
if 'sports-confidence-container' not in html:
    html = html.replace('<!-- Stop Loss -->', sports_conf_ui + '\n                            <div id="stop-loss-container">\n                            <!-- Stop Loss -->')
    html = html.replace('<!-- Take Profit -->', '</div>\n                            <!-- Take Profit -->') # close stop loss container

# 5. Fix Javascript Config Save/Load
html = html.replace('const useKelly = document.getElementById(\'kelly-criterion-toggle\') ? document.getElementById(\'kelly-criterion-toggle\').checked : false;', 'const useKelly = document.getElementById(\'kelly-criterion-toggle\') ? document.getElementById(\'kelly-criterion-toggle\').checked : false;\n    const universe = document.getElementById(\'universe-select\') ? document.getElementById(\'universe-select\').value : "FINANCIAL";\n    const minSportsConf = document.getElementById(\'sports-conf-slider\') ? parseFloat(document.getElementById(\'sports-conf-slider\').value) : 70.0;')
html = html.replace('use_kelly_criterion: useKelly', 'use_kelly_criterion: useKelly,\n        trading_universe: universe,\n        min_sports_confidence: minSportsConf')
html = html.replace('document.getElementById(\'kelly-criterion-toggle\').checked = config.use_kelly_criterion || false;', 'document.getElementById(\'kelly-criterion-toggle\').checked = config.use_kelly_criterion || false;\n        if(document.getElementById(\'universe-select\') && config.trading_universe) { document.getElementById(\'universe-select\').value = config.trading_universe; toggleUniverse(); }\n        if(document.getElementById(\'sports-conf-slider\') && config.min_sports_confidence) { document.getElementById(\'sports-conf-slider\').value = config.min_sports_confidence; document.getElementById(\'sports-conf-val\').innerText = config.min_sports_confidence + "%"; }')

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Updated frontend UI')
