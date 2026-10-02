import re

filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Replace the Live User Activity Feed Bar with the Selectable Asset Buttons Bar
old_feed_bar = """        <!-- Live User Activity Stream Bar -->
        <div id="battleTapeBar" class="bg-[#0b101d] border-b border-kalshi-border/60 px-3 py-2 flex items-center gap-2.5 overflow-hidden shadow-inner">
            <div class="flex items-center gap-1.5 shrink-0">
                <span class="flex h-2 w-2 relative">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
            </div>

            <!-- Rotating User Text Stream -->
            <div id="battleTapeFeed" class="flex-1 min-w-0 flex items-center gap-2 overflow-hidden text-xs">
                <span class="text-[10px] text-gray-500 font-mono animate-pulse">Syncing user executions...</span>
            </div>
        </div>"""

new_asset_bar = """        <!-- Asset Selector Bar (Replaced Live User Activity Feed) -->
        <div id="assetSelectorBar" class="bg-[#0b101d] border-b border-kalshi-border/60 px-3 py-2 flex items-center justify-between gap-3 shadow-inner">
            <div class="flex items-center gap-2 shrink-0">
                <span class="flex h-2 w-2 relative">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
                </span>
                <span class="text-[10px] font-black uppercase tracking-wider text-gray-400">Market</span>
            </div>

            <!-- Selectable Asset Buttons (Left to Right) -->
            <div class="flex items-center gap-1.5 flex-1 justify-end max-w-sm">
                <button type="button" id="btn-asset-btc" onclick="selectDashboardAsset('BTC')" class="asset-btn flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 border cursor-pointer bg-orange-500/25 text-orange-300 border-orange-500/50 shadow-[0_0_12px_rgba(249,115,22,0.2)]">
                    <span class="text-[11px]">₿</span> <span>BTC</span>
                </button>
                <button type="button" id="btn-asset-eth" onclick="selectDashboardAsset('ETH')" class="asset-btn flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 border cursor-pointer bg-white/5 text-gray-400 border-white/5 hover:bg-white/10 hover:text-gray-200">
                    <span class="text-[11px]">Ξ</span> <span>ETH</span>
                </button>
                <button type="button" id="btn-asset-gold" onclick="selectDashboardAsset('GOLD')" class="asset-btn flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 border cursor-pointer bg-white/5 text-gray-400 border-white/5 hover:bg-white/10 hover:text-gray-200">
                    <span class="text-[11px]">🪙</span> <span>GOLD</span>
                </button>
            </div>
        </div>"""

if old_feed_bar in content:
    content = content.replace(old_feed_bar, new_asset_bar)
    print("Replaced Live Feed Bar with Asset Selector Bar")
elif "id=\"battleTapeBar\"" in content:
    # Regex fallback if whitespace differs slightly
    content = re.sub(r'<!-- Live User Activity Stream Bar -->\s*<div id="battleTapeBar"[\s\S]*?</div>\s*</div>', new_asset_bar, content)
    print("Replaced Live Feed Bar via regex fallback")

# 2. Add selectDashboardAsset function and window.currentAsset definition
js_asset_function = """
        window.currentAsset = 'BTC';

        function selectDashboardAsset(asset) {
            asset = (asset || 'BTC').toUpperCase();
            if (window.currentAsset === asset && window.lastCandle) return;
            window.currentAsset = asset;
            
            // Visual styles
            const activeStyles = {
                'BTC': 'bg-orange-500/25 text-orange-300 border-orange-500/50 shadow-[0_0_12px_rgba(249,115,22,0.2)]',
                'ETH': 'bg-purple-500/25 text-purple-300 border-purple-500/50 shadow-[0_0_12px_rgba(168,85,247,0.2)]',
                'GOLD': 'bg-yellow-500/25 text-yellow-300 border-yellow-500/50 shadow-[0_0_12px_rgba(234,179,8,0.2)]'
            };
            const inactiveStyle = 'bg-white/5 text-gray-400 border-white/5 hover:bg-white/10 hover:text-gray-200';
            
            ['BTC', 'ETH', 'GOLD'].forEach(a => {
                const btn = document.getElementById('btn-asset-' + a.toLowerCase());
                if (!btn) return;
                btn.className = 'asset-btn flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 border cursor-pointer ' + 
                    (a === asset ? activeStyles[a] : inactiveStyle);
            });
            
            // Clear chart series
            if (typeof candleSeries !== 'undefined' && candleSeries) candleSeries.setData([]);
            if (typeof lineSeries !== 'undefined' && lineSeries) lineSeries.setData([]);
            if (typeof volumeSeries !== 'undefined' && volumeSeries) volumeSeries.setData([]);
            window.lastSpotPrice = null;
            window.lastCandle = null;
            window.currentKalshiTarget = null;
            lastBidTs = 0;
            bidsQueue = [];
            const bidsBox = document.getElementById('live-bids-container');
            if (bidsBox) bidsBox.innerHTML = '';
            
            // Reset HUD items while new asset loads
            const strikeEl = document.getElementById('exec-strike');
            if (strikeEl) strikeEl.textContent = '$--,---';
            const spotEl = document.getElementById('exec-spot');
            if (spotEl) spotEl.textContent = '$--,---';
            const yesBid = document.getElementById('kalshi-yes');
            if (yesBid) yesBid.textContent = '--%';
            const noBid  = document.getElementById('kalshi-no');
            if (noBid) noBid.textContent = '--%';
            const cdEl = document.getElementById('exec-countdown');
            if (cdEl) cdEl.textContent = '--:--';
            
            // Show loader briefly
            const loader = document.getElementById('chart-loader');
            if (loader) {
                loader.style.opacity = '1';
                loader.style.display = 'flex';
                loader.classList.remove('pointer-events-none');
            }
            
            // Immediately fetch fresh chart and contract data
            if (typeof fetchChartData === 'function') fetchChartData();
            if (typeof fetchKalshiData === 'function') fetchKalshiData();
            if (typeof fetchLiveBids === 'function') fetchLiveBids();
        }
"""

if "function selectDashboardAsset" not in content:
    content = content.replace("async function fetchChartData() {", js_asset_function + "\n        async function fetchChartData() {")
    print("Injected selectDashboardAsset function")

# 3. Parameterize fetchChartData
content = content.replace(
    "const res = await fetch(`/api/engine/btc/chart?timeframe=${tf}&limit=200`);",
    "const curA = (window.currentAsset || 'BTC').toLowerCase();\n                const res = await fetch(`/api/engine/${curA}/chart?timeframe=${tf}&limit=200`);"
)

# 4. Parameterize fetchLiveBids
content = content.replace(
    "const res = await fetch('/api/engine/btc/kalshi/trades?since=' + lastBidTs);",
    "const curA = (window.currentAsset || 'BTC').toLowerCase();\n                const res = await fetch('/api/engine/' + curA + '/kalshi/trades?since=' + lastBidTs);"
)

# 5. Parameterize fetchKalshiData
old_kalshi_fetches = """                const [kRes, cRes, tickerRes] = await Promise.all([
                    fetch('/api/engine/btc/kalshi'),
                    fetch('/api/engine/btc/countdown'),
                    fetch('/api/engine/btc/ticker'),
                ]);"""

new_kalshi_fetches = """                const curA = (window.currentAsset || 'BTC').toLowerCase();
                const [kRes, cRes, tickerRes] = await Promise.all([
                    fetch('/api/engine/' + curA + '/kalshi'),
                    fetch('/api/engine/' + curA + '/countdown'),
                    fetch('/api/engine/' + curA + '/ticker'),
                ]);"""

content = content.replace(old_kalshi_fetches, new_kalshi_fetches)

# 6. Parameterize placeManualTrade
content = content.replace(
    "const res = await fetch(`/api/engine/btc/trade/manual?direction=${direction}&lots=${size}`, {",
    "const curA = (window.currentAsset || 'BTC').toLowerCase();\n                const res = await fetch(`/api/engine/${curA}/trade/manual?direction=${direction}&lots=${size}`, {"
)

# 7. Parameterize toggleAutoTrader
content = content.replace(
    "const res = await fetch(`/api/engine/btc/trade/toggle?enabled=${enabled}`, {",
    "const curA = (window.currentAsset || 'BTC').toLowerCase();\n                const res = await fetch(`/api/engine/${curA}/trade/toggle?enabled=${enabled}`, {"
)

# 8. Guard spot update in loadDashboardStats so BTC price doesn't overwrite ETH/GOLD spot price
content = content.replace(
    "if (s.btc_price && spot) spot.textContent = '$' + Number(s.btc_price).toLocaleString(undefined,{maximumFractionDigits:0});",
    "if (s.btc_price && spot && (window.currentAsset || 'BTC') === 'BTC') spot.textContent = '$' + Number(s.btc_price).toLocaleString(undefined,{maximumFractionDigits:0});"
)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Successfully updated saas_dashboard.html")
