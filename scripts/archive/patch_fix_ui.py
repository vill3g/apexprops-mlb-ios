with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

old_block = """        <!-- API Config -->"""

new_block = """        <!-- AI & Trade Preferences -->
        <div class="mb-6 p-4 bg-black border border-kalshi-border rounded-lg space-y-4">
            <div class="flex justify-between items-center border-b border-kalshi-border pb-3">
                <div>
                    <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">1-Click Manual Trade</label>
                    <div class="text-[9px] text-gray-500 uppercase">Remove confirmation dialogs</div>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" id="one-click-toggle" class="sr-only peer">
                  <div class="w-9 h-5 bg-gray-700 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-kalshi-green"></div>
                </label>
            </div>
            
            <div class="flex justify-between items-center border-b border-kalshi-border pb-3">
                <div>
                    <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">AI Copy Size (%)</label>
                    <div class="text-[9px] text-gray-500 uppercase">Percent of balance per trade</div>
                </div>
                <input type="number" id="trade-size-pct" class="w-16 bg-[#131b2c] border border-kalshi-border rounded py-1 px-2 text-xs text-white font-bold text-center focus:outline-none" min="1" max="100">
            </div>

            <div class="flex justify-between items-center">
                <div>
                    <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">AI Stop Loss (%)</label>
                    <div class="text-[9px] text-gray-500 uppercase">Auto-close if loss exceeds %</div>
                </div>
                <input type="number" id="stop-loss-pct" class="w-16 bg-[#131b2c] border border-kalshi-border rounded py-1 px-2 text-xs text-white font-bold text-center focus:outline-none" min="1" max="100">
            </div>
            <button onclick="saveUserConfig()" class="w-full py-2 bg-kalshi-blue/10 hover:bg-kalshi-blue/20 text-kalshi-blue font-bold text-[10px] uppercase tracking-widest rounded transition-colors border border-kalshi-blue/30 mt-2">Save Preferences</button>
        </div>

        <!-- API Config -->"""

if "AI & Trade Preferences" not in c:
    c = c.replace(old_block, new_block)

# And inject JavaScript if it's missing
js_code = """
    async function saveUserConfig() {
        const size = parseFloat(document.getElementById('trade-size-pct').value) || 20.0;
        const sl = parseFloat(document.getElementById('stop-loss-pct').value) || 10.0;
        const oneClick = document.getElementById('one-click-toggle').checked;
        
        try {
            const res = await fetch('/api/auth/user/config', {
                method: "POST",
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ trade_size_pct: size, stop_loss_pct: sl, one_click_trade: oneClick })
            });
            if(res.ok) {
                alert("Preferences Saved!");
            }
        } catch(e) {}
    }
"""

if "saveUserConfig" not in c:
    c = c.replace("</script>", js_code + "\n</script>")


# And executeManualTrade needs one-click integration
old_manual = """    async function executeManualTrade(direction) {
        const amt = parseFloat(document.getElementById('trade-amount').value || 50);
        if(!confirm(`Execute $${amt} manual trade for ${direction} in ${currentMode} mode?`)) return;"""

new_manual = """    async function executeManualTrade(direction) {
        const amt = parseFloat(document.getElementById('trade-amount').value || 50);
        const toggleEl = document.getElementById('one-click-toggle');
        const oneClick = toggleEl ? toggleEl.checked : false;
        if(!oneClick && !confirm(`Execute $${amt} manual trade for ${direction} in ${currentMode} mode?`)) return;"""

if "oneClick &&" not in c:
    c = c.replace(old_manual, new_manual)

# And loadDashboard needs to populate the form
old_load = """                document.getElementById('mode-slider').style.transform = currentMode === 'LIVE' ? 'translateX(100%)' : 'translateX(0)';
                
                // Update Quick Status"""

new_load = """                document.getElementById('mode-slider').style.transform = currentMode === 'LIVE' ? 'translateX(100%)' : 'translateX(0)';
                
                if (data.trade_size_pct) document.getElementById('trade-size-pct').value = data.trade_size_pct;
                if (data.stop_loss_pct) document.getElementById('stop-loss-pct').value = data.stop_loss_pct;
                const toggleEl = document.getElementById('one-click-toggle');
                if (toggleEl) toggleEl.checked = !!data.one_click_trade;
                
                // Update Quick Status"""

if "data.trade_size_pct" not in c:
    c = c.replace(old_load, new_load)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
