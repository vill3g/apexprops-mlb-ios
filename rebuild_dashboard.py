import re

with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
    html = f.read()

# Fix JS Cents to Percent using generic regex instead of literal cent character to avoid unicode errors
html = re.sub(r'\$\{data\.yes_ask\}.', r'%', html)
html = re.sub(r'\$\{data\.no_ask\}.', r'%', html)

new_execution_block = '''
        <!-- Active Market & Execution -->
        <div class="mx-4 mb-5 bg-[#131b2c] border border-kalshi-border rounded-xl overflow-hidden shadow-lg">
            <div class="bg-black/40 px-3 py-1.5 flex items-center justify-between border-b border-kalshi-border">
                <div class="text-[9px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                    BTC 15M <div class="w-1.5 h-1.5 rounded-full bg-kalshi-blue animate-pulse"></div>
                </div>
                <div class="flex items-center gap-1 text-kalshi-blue">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    <span id="kalshi-time" class="text-[10px] font-black uppercase tabular-nums">--:--</span>
                </div>
            </div>
            
            <div class="px-3 pt-3 pb-2 flex items-baseline justify-between">
                <div class="flex items-baseline gap-2">
                    <span id="live-btc-price" class="text-xl font-black text-white tabular-nums tracking-tighter">$--.--</span>
                    <span class="text-[10px] text-gray-500 font-bold uppercase tracking-widest">LIVE</span>
                </div>
                <div class="flex items-baseline gap-2">
                    <span class="text-[10px] text-gray-500 font-bold uppercase tracking-widest">STRIKE</span>
                    <span id="kalshi-target" class="text-sm font-mono font-bold text-kalshi-blue tabular-nums">$--.--</span>
                </div>
            </div>

            <div class="px-3 pb-3 grid grid-cols-2 gap-2">
                <button id="btn-buy-yes" onclick="executeManualTrade('yes')" class="flex justify-between items-center px-3 py-2 bg-kalshi-green/10 border border-kalshi-green/30 text-kalshi-green rounded-lg active:scale-95 transition-all shadow-[0_0_10px_rgba(0,255,128,0.05)] active:bg-kalshi-green/30">
                    <span class="text-xs font-black tracking-widest uppercase">YES</span>
                    <span id="kalshi-yes" class="text-xs font-bold opacity-90">--%</span>
                </button>
                <button id="btn-buy-no" onclick="executeManualTrade('no')" class="flex justify-between items-center px-3 py-2 bg-kalshi-red/10 border border-kalshi-red/30 text-kalshi-red rounded-lg active:scale-95 transition-all shadow-[0_0_10px_rgba(255,0,0,0.05)] active:bg-kalshi-red/30">
                    <span class="text-xs font-black tracking-widest uppercase">NO</span>
                    <span id="kalshi-no" class="text-xs font-bold opacity-90">--%</span>
                </button>
            </div>
        </div>
'''

html = re.sub(r'<!-- Active Market & Execution -->.*?<!-- Recent Executions Widget -->', new_execution_block + '\n        <!-- Recent Executions Widget -->', html, flags=re.DOTALL)

new_balance_card = '''
        <!-- Balance Card -->
        <div class="mx-4 mb-2 bg-gradient-to-br from-[#1a233a] to-[#131b2c] border border-kalshi-border rounded-xl p-4 shadow-lg flex justify-between items-center">
            <div>
                <div class="text-[9px] text-gray-400 uppercase tracking-widest font-bold flex gap-1.5 items-center mb-0.5">
                    <span id="bal-mode-badge" class="px-1.5 py-0.5 rounded bg-kalshi-blue text-white leading-none">PAPER</span> BALANCE
                </div>
                <div id="val-balance" class="text-2xl font-black tabular-nums text-white tracking-tighter">$--.--</div>
            </div>
            <button onclick="closeAllTrades()" class="px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-500 border border-red-500/30 rounded text-[9px] font-bold uppercase tracking-wider transition-colors">Close All</button>
        </div>

        <!-- Stats Row -->
        <div class="mx-4 mb-4 grid grid-cols-2 gap-2">
            <div class="bg-[#131b2c] border border-kalshi-border rounded-xl p-2.5 flex justify-between items-center shadow-sm">
                <span class="text-[9px] text-gray-500 font-bold uppercase tracking-widest">Net PnL</span>
                <span id="val-pnl" class="text-xs font-black text-gray-400 tabular-nums">$--.--</span>
            </div>
            <div class="bg-[#131b2c] border border-kalshi-border rounded-xl p-2.5 flex justify-between items-center shadow-sm">
                <span class="text-[9px] text-gray-500 font-bold uppercase tracking-widest">Win Rate</span>
                <span id="val-winrate" class="text-xs font-black text-gray-300 tabular-nums">--%</span>
            </div>
        </div>
'''

html = re.sub(r'<!-- Balance Card -->.*?<!-- TradingView Chart -->', new_balance_card + '\n        <!-- TradingView Chart -->', html, flags=re.DOTALL)

new_recent_trades_html = '''
        <!-- Recent Executions Widget -->
        <div class="mx-4 mb-6">
            <div class="flex justify-between items-end mb-2 px-1">
                <h3 class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Recent Executions</h3>
                <a href="#" onclick="const t = localStorage.getItem('saas_token'); const id = t ? JSON.parse(atob(t.split('.')[1])).user_id : ''; window.open('/trades' + (id ? '?guest=' + id : ''), '_blank'); return false;" class="text-[9px] font-bold text-kalshi-blue uppercase tracking-wider">View All</a>
            </div>
            
            <div id="tradesContainer" class="space-y-2">
                <div class="text-center py-6 text-[10px] text-gray-500 font-mono bg-[#131b2c] rounded-xl border border-kalshi-border">Loading trades...</div>
            </div>
        </div>
'''

html = re.sub(r'<!-- Recent Executions Widget -->.*?<!-- SaaS Configuration -->', new_recent_trades_html + '\n        <!-- SaaS Configuration -->', html, flags=re.DOTALL)

with open("static/saas_dashboard.html", "w", encoding="utf-8") as f:
    f.write(html)
