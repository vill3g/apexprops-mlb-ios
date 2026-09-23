with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

old_market_header = """        <div class="px-4 py-3 border-b border-kalshi-border bg-[#131b2c] flex justify-between items-center">
            <div class="flex flex-col">
                <h2 class="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-0.5">Active Market</h2>
                <div class="flex items-center gap-2">
                    <span class="text-xs font-bold text-white">BTC 15M</span>
                    <span id="live-btc-price" class="px-1.5 py-0.5 bg-black border border-kalshi-border rounded text-[10px] font-bold font-mono text-emerald-400 animate-pulse">Loading...</span>
                </div>
            </div>
            <div class="text-right">
                <div id="kalshi-time" class="text-[11px] font-black text-kalshi-blue uppercase tracking-wider tabular-nums">--:-- LEFT</div>
            </div>
        </div>
        <div class="p-4 grid grid-cols-2 gap-4 border-b border-kalshi-border">
            <div>
                <div class="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-1">Target Strike</div>
                <div id="kalshi-target" class="text-xl font-black tabular-nums tracking-tighter text-white">Loading...</div>
            </div>"""

new_market_header = """        <div class="px-4 py-3 border-b border-kalshi-border bg-[#131b2c] flex justify-between items-center">
            <div class="flex flex-col">
                <h2 class="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-0.5">Active Market (BTC 15M)</h2>
                <div class="flex items-center gap-2">
                    <span class="text-xs font-bold text-gray-400">STRIKE:</span>
                    <span id="kalshi-target" class="px-1.5 py-0.5 bg-black border border-kalshi-border rounded text-[10px] font-bold font-mono text-white animate-pulse">Loading...</span>
                </div>
            </div>
            <div class="text-right">
                <div id="kalshi-time" class="text-[11px] font-black text-kalshi-blue uppercase tracking-wider tabular-nums">--:-- LEFT</div>
            </div>
        </div>
        <div class="p-4 grid grid-cols-2 gap-4 border-b border-kalshi-border">
            <div>
                <div class="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-1">Live BTC Price</div>
                <div id="live-btc-price" class="text-xl font-black tabular-nums tracking-tighter text-emerald-400">Loading...</div>
            </div>"""

c = c.replace(old_market_header, new_market_header)


old_trade_controls = """            <button onclick="closeAllTrades()" class="w-full py-2 bg-gray-800 hover:bg-red-900/80 text-gray-300 hover:text-white font-bold text-xs uppercase tracking-widest rounded transition-colors active:scale-95 border border-gray-700 hover:border-red-500/50">
                Close All Open Positions
            </button>"""

new_trade_controls = """            <div class="flex gap-2">
                <button onclick="closeAllTrades()" class="flex-1 py-2 bg-gray-800 hover:bg-red-900/80 text-gray-300 hover:text-white font-bold text-[10px] uppercase tracking-widest rounded transition-colors active:scale-95 border border-gray-700 hover:border-red-500/50">
                    Close All Open
                </button>
                <button id="quick-ai-btn" onclick="toggleAI(!aiEnabled)" class="flex-1 py-2 bg-kalshi-green/20 text-kalshi-green font-bold text-[10px] uppercase tracking-widest rounded transition-colors active:scale-95 border border-kalshi-green/50 hover:bg-kalshi-green/40">
                    Copy AI: ON
                </button>
            </div>"""

c = c.replace(old_trade_controls, new_trade_controls)

# Update javascript to sync the quick button
js_update_status = """                if (!aiEnabled) {
                    statusEl.innerText = "Paused (AI Ignored)";
                    statusEl.className = "text-[10px] uppercase font-bold text-gray-500 tracking-wider";
                } else if (currentMode === "LIVE" && s.balance_dollars === null) {"""

new_js_update_status = """                
                const quickBtn = document.getElementById('quick-ai-btn');
                if (quickBtn) {
                    if (aiEnabled) {
                        quickBtn.innerText = "Copy AI: ON";
                        quickBtn.className = "flex-1 py-2 bg-kalshi-green/20 text-kalshi-green font-bold text-[10px] uppercase tracking-widest rounded transition-colors active:scale-95 border border-kalshi-green/50 hover:bg-kalshi-green/40";
                    } else {
                        quickBtn.innerText = "Copy AI: OFF";
                        quickBtn.className = "flex-1 py-2 bg-gray-800 text-gray-500 font-bold text-[10px] uppercase tracking-widest rounded transition-colors active:scale-95 border border-gray-700 hover:bg-gray-700";
                    }
                }

                if (!aiEnabled) {
                    statusEl.innerText = "Paused (AI Ignored)";
                    statusEl.className = "text-[10px] uppercase font-bold text-gray-500 tracking-wider";
                } else if (currentMode === "LIVE" && s.balance_dollars === null) {"""

c = c.replace(js_update_status, new_js_update_status)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
