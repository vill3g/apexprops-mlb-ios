import re

filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. HTML Insertion
asset_html = """
                    <!-- Asset Selection -->
                    <div class="mt-3 bg-[#131b2c] border border-white/[0.05] rounded-xl p-3">
                        <span class="text-[11px] font-bold text-white tracking-tight mb-2 block uppercase text-gray-400">Active Trading Assets</span>
                        <div class="flex items-center justify-between gap-2">
                            <!-- BTC -->
                            <div class="flex flex-col items-center flex-1 bg-black/30 p-2 rounded-lg border border-white/[0.05]">
                                <span class="text-[10px] font-bold text-orange-400 mb-1.5">BTC</span>
                                <label class="relative inline-flex items-center cursor-pointer scale-[0.75]">
                                    <input type="checkbox" id="asset-btc-toggle" class="sr-only peer asset-toggle" value="BTC" onchange="saveUserConfig()">
                                    <div class="w-11 h-6 bg-gray-700/80 rounded-full peer peer-checked:after:translate-x-5 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-orange-500"></div>
                                </label>
                            </div>
                            <!-- ETH -->
                            <div class="flex flex-col items-center flex-1 bg-black/30 p-2 rounded-lg border border-white/[0.05]">
                                <span class="text-[10px] font-bold text-purple-400 mb-1.5">ETH</span>
                                <label class="relative inline-flex items-center cursor-pointer scale-[0.75]">
                                    <input type="checkbox" id="asset-eth-toggle" class="sr-only peer asset-toggle" value="ETH" onchange="saveUserConfig()">
                                    <div class="w-11 h-6 bg-gray-700/80 rounded-full peer peer-checked:after:translate-x-5 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-500"></div>
                                </label>
                            </div>
                            <!-- GOLD -->
                            <div class="flex flex-col items-center flex-1 bg-black/30 p-2 rounded-lg border border-white/[0.05]">
                                <span class="text-[10px] font-bold text-yellow-400 mb-1.5">GOLD</span>
                                <label class="relative inline-flex items-center cursor-pointer scale-[0.75]">
                                    <input type="checkbox" id="asset-gold-toggle" class="sr-only peer asset-toggle" value="GOLD" onchange="saveUserConfig()">
                                    <div class="w-11 h-6 bg-gray-700/80 rounded-full peer peer-checked:after:translate-x-5 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-yellow-500"></div>
                                </label>
                            </div>
                        </div>
                    </div>
"""

pattern_html = r'(<input type="checkbox" id="header-auto-toggle" class="sr-only peer" onchange="toggleAutoTrader\(this\.checked\)">[\s\S]*?</div>\s*</label>\s*</div>)'
if 'id="asset-btc-toggle"' not in content:
    content = re.sub(pattern_html, r'\1\n' + asset_html, content)
    print("Added HTML UI")

# 2. Extract state in `saveUserConfig`
js_extract = """
            const xgbLR       = parseFloat(xgbLRRaw)       || 0.1;

            const activeAssets = [];
            if(document.getElementById('asset-btc-toggle')?.checked) activeAssets.push('BTC');
            if(document.getElementById('asset-eth-toggle')?.checked) activeAssets.push('ETH');
            if(document.getElementById('asset-gold-toggle')?.checked) activeAssets.push('GOLD');
            const targetAssetStr = activeAssets.length > 0 ? activeAssets.join(',') : 'BTC';
"""
if "const activeAssets = [];" not in content:
    content = content.replace("            const xgbLR       = parseFloat(xgbLRRaw)       || 0.1;", js_extract)
    print("Added state extraction")

# 3. Inject to `configPayload`
if "target_asset: targetAssetStr," not in content:
    content = content.replace("trading_style: tStyle,", "target_asset: targetAssetStr,\n                    trading_style: tStyle,")
    print("Added to configPayload")

# 4. Load state in `fetch('/api/auth/user/config')` callback
js_load = """
            if (s.target_asset !== undefined) {
                const assets = s.target_asset.split(',').map(a => a.trim().toUpperCase());
                const btcToggle = document.getElementById('asset-btc-toggle');
                const ethToggle = document.getElementById('asset-eth-toggle');
                const goldToggle = document.getElementById('asset-gold-toggle');
                if(btcToggle) btcToggle.checked = assets.includes('BTC');
                if(ethToggle) ethToggle.checked = assets.includes('ETH');
                if(goldToggle) goldToggle.checked = assets.includes('GOLD');
            }
"""
if "const btcToggle = document.getElementById('asset-btc-toggle');" not in content:
    # Find place to inject. Look for "if (oneClickEl && s.one_click_trade !== undefined)"
    content = content.replace("            const oneClickEl = document.getElementById('one-click-toggle');", js_load + "\n            const oneClickEl = document.getElementById('one-click-toggle');")
    print("Added load state")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
