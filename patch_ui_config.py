with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

# Let's insert the new settings UI right before the Apply Configuration button in the modal.

old_apply_btn = """        <!-- Apply / Reset Buttons -->
        <div class="flex gap-3">
            <button onclick="toggleSettings()" class="flex-1 py-3 bg-kalshi-blue/10 hover:bg-kalshi-blue/20 text-kalshi-blue font-bold uppercase tracking-widest rounded-lg transition-colors border border-kalshi-blue/30">Close</button>
        </div>"""

new_settings_ui = """        <!-- AI & Trade Preferences -->
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
            <button onclick="saveUserConfig()" class="w-full py-2 bg-kalshi-blue/10 hover:bg-kalshi-blue/20 text-kalshi-blue font-bold text-[10px] uppercase tracking-widest rounded transition-colors border border-kalshi-blue/30 mt-2">Save AI Preferences</button>
        </div>

        <!-- Apply / Reset Buttons -->
        <div class="flex gap-3">
            <button onclick="toggleSettings()" class="flex-1 py-3 bg-kalshi-blue/10 hover:bg-kalshi-blue/20 text-kalshi-blue font-bold uppercase tracking-widest rounded-lg transition-colors border border-kalshi-blue/30">Close</button>
        </div>"""

c = c.replace(old_apply_btn, new_settings_ui)


# Update JavaScript
old_manual_trade = """    async function executeManualTrade(direction) {
        const amt = parseFloat(document.getElementById('trade-amount').value || 50);
        if(!confirm(`Execute $${amt} manual trade for ${direction} in ${currentMode} mode?`)) return;"""

new_manual_trade = """    async function executeManualTrade(direction) {
        const amt = parseFloat(document.getElementById('trade-amount').value || 50);
        const oneClick = document.getElementById('one-click-toggle').checked;
        if(!oneClick && !confirm(`Execute $${amt} manual trade for ${direction} in ${currentMode} mode?`)) return;"""

c = c.replace(old_manual_trade, new_manual_trade)

new_js = """
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
                alert("AI & Trade Preferences Saved!");
            }
        } catch(e) {}
    }
"""

old_load_dashboard = """                document.getElementById('mode-slider').style.transform = currentMode === 'LIVE' ? 'translateX(100%)' : 'translateX(0)';
                
                // Update Quick Status"""

new_load_dashboard = """                document.getElementById('mode-slider').style.transform = currentMode === 'LIVE' ? 'translateX(100%)' : 'translateX(0)';
                
                // Set form values
                if(data.trade_size_pct) document.getElementById('trade-size-pct').value = data.trade_size_pct;
                if(data.stop_loss_pct) document.getElementById('stop-loss-pct').value = data.stop_loss_pct;
                document.getElementById('one-click-toggle').checked = !!data.one_click_trade;
                
                // Update Quick Status"""

c = c.replace(old_load_dashboard, new_load_dashboard)
c = c.replace("</script>", new_js + "\n</script>")

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
