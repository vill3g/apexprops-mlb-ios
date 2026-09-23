import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    text = f.read()

head = text.split('<!-- AI Popup -->')[0]
tail = text.split('<!-- API Config -->')[1]

# Make sure we don't duplicate <main> or other tags.
# head ends with:
#         <!-- Right: Stats -->
#         <div class="flex gap-4 text-right">
#             <div>
#                 <div class="text-[9px] font-bold text-gray-500 uppercase tracking-widest">Net Profit</div>
#                 <div id="val-pnl" class="text-sm font-black tabular-nums tracking-tighter mt-0.5">$--.--</div>
#             </div>
#             <div>
#                 <div class="text-[9px] font-bold text-gray-500 uppercase tracking-widest">Win Rate</div>
#                 <div id="val-winrate" class="text-sm font-bold text-gray-300 mt-0.5">--%</div>
#             </div>
#         </div>
#     </div>

# Let's cleanly rebuild the middle section!
middle = """
    </div> <!-- Close Balance Card -->

    <!-- Mode Switcher -->
    <div class="mt-4 bg-[#131b2c] border border-kalshi-border rounded-lg p-1 relative flex items-center shadow-sm">
        <div id="mode-slider" class="absolute top-1 bottom-1 w-1/2 bg-kalshi-blue rounded-md transition-all shadow-sm transform translate-x-0"></div>
        <button id="btn-mode-paper" onclick="setTradingMode('PAPER')" class="flex-1 relative z-10 py-2 text-xs font-bold uppercase tracking-wider text-white">Paper</button>
        <button id="btn-mode-live" onclick="setTradingMode('LIVE')" class="flex-1 relative z-10 py-2 text-xs font-bold uppercase tracking-wider text-gray-400">Live</button>
    </div>

    <!-- Live Market & Chart -->
    <div class="bg-kalshi-dark border border-kalshi-border rounded-xl shadow-lg overflow-hidden mt-6 mb-4">
        <div class="px-4 py-3 border-b border-kalshi-border bg-[#131b2c] flex justify-between items-center relative">
            <div class="flex flex-col">
                <h2 class="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-0.5">Active Market (BTC 15M)</h2>
                <div class="flex items-center gap-2">
                    <span class="text-xs font-bold text-gray-400">STRIKE:</span>
                    <span id="kalshi-target" class="px-1.5 py-0.5 bg-black border border-kalshi-border rounded text-[10px] font-bold font-mono text-white animate-pulse">Loading...</span>
                </div>
            </div>
            <div class="text-right flex flex-col items-end gap-1 relative">
                <div class="flex items-center gap-2">
                    <div id="ml-status-bubble" onclick="toggleMLPopup(event)" class="cursor-pointer px-1.5 py-[2px] rounded text-[8px] font-bold uppercase tracking-widest bg-gray-800 text-gray-400 border border-gray-600 shadow-sm transition-colors duration-300 hover:scale-105 active:scale-95">AI: --</div>
                    <div id="kalshi-time" class="text-[11px] font-black text-kalshi-blue uppercase tracking-wider tabular-nums">--:-- LEFT</div>
                </div>
                <!-- AI Popup -->
                <div id="ml-details-popup" class="hidden absolute top-full right-0 mt-2 w-64 bg-black border border-kalshi-border rounded-lg shadow-[0_10px_30px_rgba(0,0,0,0.8)] z-50 p-4 text-left">
                    <div class="flex justify-between items-center mb-3">
                        <span class="text-xs font-bold text-gray-400 uppercase tracking-widest">Primary Bias</span>
                        <span id="popup-bias" class="text-sm font-black text-white">--</span>
                    </div>
                    <div class="flex justify-between items-center mb-3">
                        <span class="text-xs font-bold text-gray-400 uppercase tracking-widest">Confidence</span>
                        <span id="popup-conf" class="text-sm font-bold text-kalshi-green">--%</span>
                    </div>
                    <div class="flex justify-between items-center mb-4">
                        <span class="text-xs font-bold text-gray-400 uppercase tracking-widest">Raw Prob</span>
                        <span id="popup-prob" class="text-sm font-bold text-kalshi-blue">--%</span>
                    </div>
                    <div id="popup-summary" class="text-xs text-gray-400 leading-relaxed mb-4">Loading ML data...</div>
                    <button onclick="forceMLTrade()" class="w-full py-2 bg-purple-900/40 hover:bg-purple-800 text-purple-400 font-bold text-[10px] uppercase tracking-widest rounded transition-colors border border-purple-500/30">Force ML Signal</button>
                </div>
            </div>
        </div>

        <div class="p-4 bg-black relative flex flex-col items-center justify-center py-8 border-b border-kalshi-border">
            <div class="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-1">Live BTC Price</div>
            <div id="live-btc-price" class="text-4xl font-black tabular-nums tracking-tighter text-white animate-pulse">$--.--</div>
        </div>

        <div class="grid grid-cols-2 divide-x divide-kalshi-border bg-[#131b2c]">
            <div class="p-3 text-center">
                <div class="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-1">YES PROB</div>
                <div id="kalshi-yes" class="text-xl font-black text-kalshi-green tabular-nums">--</div>
            </div>
            <div class="p-3 text-center">
                <div class="text-[10px] font-bold uppercase tracking-widest text-gray-500 mb-1">NO PROB</div>
                <div id="kalshi-no" class="text-xl font-black text-kalshi-red tabular-nums">--</div>
            </div>
        </div>
    </div>

    <!-- Manual Trade -->
    <div class="grid grid-cols-2 gap-3 mb-6">
        <button id="btn-buy-yes" onclick="executeManualTrade('yes')" class="py-3 bg-kalshi-green/20 hover:bg-kalshi-green/40 border border-kalshi-green/50 text-kalshi-green font-black rounded-lg shadow-[0_0_15px_rgba(0,255,128,0.15)] transition-all active:scale-95">BUY YES</button>
        <button id="btn-buy-no" onclick="executeManualTrade('no')" class="py-3 bg-kalshi-red/20 hover:bg-kalshi-red/40 border border-kalshi-red/50 text-kalshi-red font-black rounded-lg shadow-[0_0_15px_rgba(255,64,64,0.15)] transition-all active:scale-95">BUY NO</button>
    </div>
    
    <!-- Hidden input so JS doesn't break when looking for trade-amount -->
    <input type="hidden" id="trade-amount" value="50">

    <div class="flex justify-between items-end mb-3 px-1">
        <h3 class="text-xs font-bold text-gray-500 uppercase tracking-widest">Recent Trades</h3>
        <a href="/trades.html" class="text-[10px] font-bold text-kalshi-blue uppercase hover:underline">View All &rarr;</a>
    </div>
    
    <div class="bg-[#131b2c] border border-kalshi-border rounded-xl shadow-lg overflow-hidden mb-6">
        <table class="w-full text-left text-xs">
            <thead class="bg-black/50 text-gray-500 text-[9px] uppercase tracking-widest">
                <tr>
                    <th class="py-2 px-3 font-bold">Time</th>
                    <th class="py-2 px-3 font-bold">Side</th>
                    <th class="py-2 px-3 font-bold">Strike</th>
                    <th class="py-2 px-3 font-bold text-right">PnL</th>
                </tr>
            </thead>
            <tbody id="trades-body" class="divide-y divide-kalshi-border/50">
            </tbody>
        </table>
    </div>

</main>

<div id="settings-modal" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-sm justify-center items-end">
    <div id="settings-panel" class="bg-kalshi-dark w-full max-w-md rounded-t-2xl border-t border-kalshi-border p-5 transform translate-y-full transition-transform duration-300 max-h-[90vh] overflow-y-auto">
        <div class="flex justify-between items-center mb-6">
            <h2 class="text-lg font-black text-white uppercase tracking-widest">SaaS Settings</h2>
            <button onclick="toggleSettings()" class="text-gray-500 hover:text-white">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
            </button>
        </div>

        <div class="space-y-4 mb-6">
            <div class="flex justify-between items-center border-b border-kalshi-border pb-3">
                <div>
                    <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">AI Copy Size ($)</label>
                    <div class="text-[9px] text-gray-500 uppercase">Dollar amount per trade</div>
                </div>
                <input type="number" id="trade-size-dollars" class="w-20 bg-[#131b2c] border border-kalshi-border rounded py-1 px-2 text-xs text-white font-bold text-center focus:outline-none" min="1" max="10000">
            </div>
            <div class="flex justify-between items-center border-b border-kalshi-border pb-3">
                <div>
                    <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">Trading Style</label>
                    <div class="text-[9px] text-gray-500 uppercase">AI execution strategy</div>
                </div>
                <select id="trading-style" class="w-28 bg-[#131b2c] border border-kalshi-border rounded py-1 px-2 text-[10px] text-white font-bold focus:outline-none">
                    <option value="AUTO">Auto</option>
                    <option value="SNIPER">Sniper</option>
                    <option value="MOMENTUM_SURFER">Momentum</option>
                    <option value="CHOP">Chop</option>
                </select>
            </div>
            <div class="flex justify-between items-center border-b border-kalshi-border pb-3">
                <div>
                    <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">Signal Source</label>
                    <div class="text-[9px] text-gray-500 uppercase">Primary prediction engine</div>
                </div>
                <select id="signal-source" class="w-28 bg-[#131b2c] border border-kalshi-border rounded py-1 px-2 text-[10px] text-white font-bold focus:outline-none">
                    <option value="ML_ENSEMBLE">GodTier ML</option>
                    <option value="TECHNICAL_ONLY">Technical Only</option>
                </select>
            </div>

            <div class="flex justify-between items-center border-b border-kalshi-border pb-3">
                <div>
                    <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">AI Stop Loss (%)</label>
                    <div class="text-[9px] text-gray-500 uppercase">Auto-close if loss exceeds %</div>
                </div>
                <input type="number" id="stop-loss-pct" class="w-16 bg-[#131b2c] border border-kalshi-border rounded py-1 px-2 text-xs text-white font-bold text-center focus:outline-none" min="1" max="100">
            </div>
            <div class="flex justify-between items-center border-b border-kalshi-border pb-3">
                <div>
                    <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">Auto Force Trade</label>
                    <div class="text-[9px] text-purple-400 uppercase">Always copy AI (Ignore Confidence)</div>
                </div>
                <label class="relative inline-flex items-center cursor-pointer gap-2">
                  <span id="force-trade-text" class="text-[10px] font-bold text-gray-500 uppercase">OFF</span>
                  <input type="checkbox" id="force-trade-toggle" class="sr-only peer" onchange="document.getElementById('force-trade-text').innerText = this.checked ? 'ON' : 'OFF'; document.getElementById('force-trade-text').className = this.checked ? 'text-[10px] font-bold text-purple-400 uppercase' : 'text-[10px] font-bold text-gray-500 uppercase';">
                  <div class="w-9 h-5 bg-gray-700 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[35px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-500"></div>
                </label>
            </div>
            <div class="flex justify-between items-center border-b border-kalshi-border pb-3">
                <div>
                    <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">1-Click Trading</label>
                    <div class="text-[9px] text-gray-500 uppercase">Skip confirmation popups</div>
                </div>
                <label class="relative inline-flex items-center cursor-pointer gap-2">
                  <span id="one-click-text" class="text-[10px] font-bold text-gray-500 uppercase">OFF</span>
                  <input type="checkbox" id="one-click-toggle" class="sr-only peer" onchange="document.getElementById('one-click-text').innerText = this.checked ? 'ON' : 'OFF'; document.getElementById('one-click-text').className = this.checked ? 'text-[10px] font-bold text-kalshi-green uppercase' : 'text-[10px] font-bold text-gray-500 uppercase';">
                  <div class="w-9 h-5 bg-gray-700 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[35px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-kalshi-blue"></div>
                </label>
            </div>
            <button onclick="saveUserConfig()" class="w-full py-2 bg-kalshi-blue/10 hover:bg-kalshi-blue/20 text-kalshi-blue font-bold text-[10px] uppercase tracking-widest rounded transition-colors border border-kalshi-blue/30 mt-2">Save Preferences</button>
        </div>
        <!-- API Config -->
"""

# Be sure not to duplicate <!-- API Config --> in tail!
new_text = head + middle + "\n" + tail
with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(new_text)

print("SUCCESS")
