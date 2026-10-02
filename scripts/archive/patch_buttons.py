with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Remove Close All button from Activity Ledger header
old_activity_header = """        <div class="px-4 py-3 border-b border-kalshi-border bg-[#131b2c] flex justify-between items-center">
            <h2 class="text-xs font-bold uppercase tracking-widest text-gray-300">Activity Ledger</h2>
            <div class="flex items-center gap-2">
                <button onclick="closeAllTrades()" class="px-2 py-1 bg-red-900/60 hover:bg-red-800 text-[10px] text-red-200 font-bold uppercase tracking-widest rounded transition-colors border border-red-500/30">Close All</button>
                <div class="flex items-center gap-1">
                    <span class="w-2 h-2 rounded-full bg-kalshi-green animate-pulse"></span>
                    <span class="text-[10px] text-kalshi-green font-bold uppercase tracking-wider">Live</span>
                </div>
            </div>
        </div>"""

new_activity_header = """        <div class="px-4 py-3 border-b border-kalshi-border bg-[#131b2c] flex justify-between items-center">
            <h2 class="text-xs font-bold uppercase tracking-widest text-gray-300">Activity Ledger</h2>
            <div class="flex items-center gap-1">
                <span class="w-2 h-2 rounded-full bg-kalshi-green animate-pulse"></span>
                <span class="text-[10px] text-kalshi-green font-bold uppercase tracking-wider">Live</span>
            </div>
        </div>"""

c = c.replace(old_activity_header, new_activity_header)

# 2. Re-arrange the Chart Card to put Chart above Trade Panel, and add Close All.
old_panel_and_chart = """        <!-- Manual Trading Panel -->
        <div class="p-3 bg-black border-b border-kalshi-border">
            <div class="flex justify-between items-center mb-2">
                <div class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Manual Trade Entry</div>
                <div class="flex items-center gap-1">
                    <span class="text-[10px] font-bold text-gray-500 uppercase">Size ($)</span>
                    <input type="number" id="trade-amount" value="50" min="1" step="1" class="w-16 bg-[#131b2c] border border-kalshi-border rounded py-1 px-2 text-xs text-white font-bold text-center focus:outline-none focus:border-kalshi-blue transition-colors">
                </div>
            </div>
            <div class="flex gap-2">
                <button onclick="executeManualTrade('YES')" class="flex-1 py-2 bg-green-600 hover:bg-green-500 text-white font-bold text-sm uppercase rounded shadow-[0_0_10px_rgba(0,255,136,0.2)] transition-colors active:scale-95">Buy YES</button>
                <button onclick="executeManualTrade('NO')" class="flex-1 py-2 bg-red-600 hover:bg-red-500 text-white font-bold text-sm uppercase rounded shadow-[0_0_10px_rgba(255,68,68,0.2)] transition-colors active:scale-95">Buy NO</button>
            </div>
        </div>
        
        <div class="w-full h-[250px] relative">
            <div id="tv_chart_container" class="absolute inset-0"></div>
        </div>"""

new_panel_and_chart = """        <div class="w-full h-[250px] relative border-b border-kalshi-border">
            <div id="tv_chart_container" class="absolute inset-0"></div>
        </div>
        
        <!-- Manual Trading Panel -->
        <div class="p-3 bg-[#0d1320]">
            <div class="flex justify-between items-center mb-2">
                <div class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Trade Controls</div>
                <div class="flex items-center gap-1">
                    <span class="text-[10px] font-bold text-gray-500 uppercase">Size ($)</span>
                    <input type="number" id="trade-amount" value="50" min="1" step="1" class="w-14 bg-black border border-kalshi-border rounded py-0.5 px-1 text-xs text-white font-bold text-center focus:outline-none focus:border-kalshi-blue transition-colors">
                </div>
            </div>
            <div class="flex gap-2 mb-2">
                <button onclick="executeManualTrade('YES')" class="flex-1 py-2.5 bg-green-600 hover:bg-green-500 text-white font-bold text-sm uppercase rounded shadow-[0_0_10px_rgba(0,255,136,0.2)] transition-colors active:scale-95 border border-green-500/50">Buy YES</button>
                <button onclick="executeManualTrade('NO')" class="flex-1 py-2.5 bg-red-600 hover:bg-red-500 text-white font-bold text-sm uppercase rounded shadow-[0_0_10px_rgba(255,68,68,0.2)] transition-colors active:scale-95 border border-red-500/50">Buy NO</button>
            </div>
            <button onclick="closeAllTrades()" class="w-full py-2 bg-gray-800 hover:bg-red-900/80 text-gray-300 hover:text-white font-bold text-xs uppercase tracking-widest rounded transition-colors active:scale-95 border border-gray-700 hover:border-red-500/50">
                Close All Open Positions
            </button>
        </div>"""

c = c.replace(old_panel_and_chart, new_panel_and_chart)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
