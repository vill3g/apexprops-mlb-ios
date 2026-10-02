with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

# Replace the forceMLTrade button with a toggle
old_btn = '<button onclick="forceMLTrade()" class="w-full py-2 bg-purple-900/40 hover:bg-purple-800 text-purple-400 font-bold text-[10px] uppercase tracking-widest rounded transition-colors border border-purple-500/50 mt-2 shadow-[0_0_10px_rgba(168,85,247,0.2)]">⚡ Force Copy ML Signal Now</button>'

new_toggle = """<div class="flex justify-between items-center border-b border-kalshi-border pb-3">
                <div>
                    <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">Auto Force Trade</label>
                    <div class="text-[9px] text-purple-400 uppercase">Always copy AI (Ignore Confidence)</div>
                </div>
                <label class="relative inline-flex items-center cursor-pointer gap-2">
                  <span id="force-trade-text" class="text-[10px] font-bold text-gray-500 uppercase">OFF</span>
                  <input type="checkbox" id="force-trade-toggle" class="sr-only peer" onchange="document.getElementById('force-trade-text').innerText = this.checked ? 'ON' : 'OFF'; document.getElementById('force-trade-text').className = this.checked ? 'text-[10px] font-bold text-purple-400 uppercase' : 'text-[10px] font-bold text-gray-500 uppercase';">
                  <div class="w-9 h-5 bg-gray-700 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[35px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-500"></div>
                </label>
            </div>"""

if old_btn in c:
    c = c.replace(old_btn, new_toggle)

# Update saveUserConfig to handle auto_force_trade
old_save = """const oneClick = toggleEl ? toggleEl.checked : false;
        
        try {
            const res = await fetch('/api/auth/user/config', {
                method: "POST",
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ trade_size_pct: size, stop_loss_pct: sl, one_click_trade: oneClick })
            });"""

new_save = """const oneClick = toggleEl ? toggleEl.checked : false;
        const forceEl = document.getElementById('force-trade-toggle');
        const autoForce = forceEl ? forceEl.checked : false;
        
        try {
            const res = await fetch('/api/auth/user/config', {
                method: "POST",
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ trade_size_pct: size, stop_loss_pct: sl, one_click_trade: oneClick, auto_force_trade: autoForce })
            });"""

if old_save in c:
    c = c.replace(old_save, new_save)

# Update load to populate toggle
old_load = """const toggleEl = document.getElementById('one-click-toggle');
                if (toggleEl) {
                    toggleEl.checked = !!data.one_click_trade;
                    document.getElementById('one-click-text').innerText = toggleEl.checked ? 'ON' : 'OFF';
                    document.getElementById('one-click-text').className = toggleEl.checked ? 'text-[10px] font-bold text-kalshi-green uppercase' : 'text-[10px] font-bold text-gray-500 uppercase';
                }"""

new_load = """const toggleEl = document.getElementById('one-click-toggle');
                if (toggleEl) {
                    toggleEl.checked = !!data.one_click_trade;
                    document.getElementById('one-click-text').innerText = toggleEl.checked ? 'ON' : 'OFF';
                    document.getElementById('one-click-text').className = toggleEl.checked ? 'text-[10px] font-bold text-kalshi-green uppercase' : 'text-[10px] font-bold text-gray-500 uppercase';
                }
                const forceEl = document.getElementById('force-trade-toggle');
                if (forceEl) {
                    forceEl.checked = !!data.auto_force_trade;
                    document.getElementById('force-trade-text').innerText = forceEl.checked ? 'ON' : 'OFF';
                    document.getElementById('force-trade-text').className = forceEl.checked ? 'text-[10px] font-bold text-purple-400 uppercase' : 'text-[10px] font-bold text-gray-500 uppercase';
                }"""

if old_load in c:
    c = c.replace(old_load, new_load)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
