with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

old_balance = """    <!-- Balance Card -->
    <div class="bg-kalshi-dark border border-kalshi-border rounded-xl p-5 shadow-lg relative overflow-hidden">
        <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-kalshi-blue to-kalshi-green"></div>
        <div class="flex justify-between items-start">
            <div>
                <div class="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-1 flex items-center gap-1">
                    <span id="bal-mode-badge" class="px-1.5 py-0.5 rounded bg-gray-800 text-gray-300">PAPER</span> Balance
                </div>
                <div id="val-balance" class="text-3xl font-black tabular-nums tracking-tighter">$--.--</div>
            </div>
            <div class="text-right">
                <div class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-1">Net Profit</div>
                <div id="val-pnl" class="text-lg font-black tabular-nums tracking-tighter">$--.--</div>
            </div>
        </div>
        
        <div class="mt-5 grid grid-cols-2 gap-4 border-t border-kalshi-border pt-4">
            <div>
                <div class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Win Rate</div>
                <div id="val-winrate" class="text-sm font-bold text-gray-300">--%</div>
            </div>
            <div class="text-right">
                <div class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Total Trades</div>
                <div id="val-trades" class="text-sm font-bold text-gray-300">-</div>
            </div>
        </div>
    </div>"""

new_balance = """    <!-- Balance Card -->
    <div class="bg-[#131b2c] border border-kalshi-border rounded-lg px-4 py-2 shadow-sm relative overflow-hidden flex items-center justify-between mt-2">
        <div class="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-kalshi-blue to-kalshi-green"></div>
        <!-- Left: Balance -->
        <div class="pl-1">
            <div class="text-[9px] font-bold text-gray-500 uppercase tracking-widest flex items-center gap-1">
                <span id="bal-mode-badge" class="px-1 py-[1px] rounded bg-gray-800/80 text-[8px] text-gray-300 leading-none">PAPER</span>
                BALANCE
            </div>
            <div id="val-balance" class="text-xl font-black tabular-nums tracking-tighter leading-none mt-1 text-white">$--.--</div>
        </div>
        <!-- Right: Stats -->
        <div class="flex gap-4 text-right">
            <div>
                <div class="text-[9px] font-bold text-gray-500 uppercase tracking-widest">Net Profit</div>
                <div id="val-pnl" class="text-sm font-black tabular-nums tracking-tighter mt-0.5">$--.--</div>
            </div>
            <div>
                <div class="text-[9px] font-bold text-gray-500 uppercase tracking-widest">Win Rate</div>
                <div id="val-winrate" class="text-sm font-bold text-gray-300 mt-0.5">--%</div>
            </div>
        </div>
    </div>"""

# Ensure js logic no longer tries to set val-trades
js_old = """document.getElementById('val-trades').innerText = (s.wins + s.losses) || 0;"""
js_new = """// document.getElementById('val-trades').innerText = (s.wins + s.losses) || 0;"""

c = c.replace(old_balance, new_balance)
c = c.replace(js_old, js_new)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
