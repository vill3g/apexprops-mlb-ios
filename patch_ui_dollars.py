import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

# Replace input UI
old_ui = """<div class="flex justify-between items-center">
                  <div>
                      <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">AI Copy Size (%)</label>
                      <div class="text-[9px] text-gray-500 uppercase">Percent of balance per trade</div>
                  </div>
                  <input type="number" id="trade-size-pct" class="w-16 bg-[#131b2c] border border-kalshi-border rounded py-1 px-2 text-xs text-white font-bold text-center focus:outline-none" min="1" max="100">
              </div>"""

new_ui = """<div class="flex justify-between items-center border-b border-kalshi-border pb-3">
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
              </div>"""

if old_ui in c:
    c = c.replace(old_ui, new_ui)

# Update loadDashboard populator
old_pop = """if (s.trade_size_pct !== undefined) document.getElementById('trade-size-pct').value = s.trade_size_pct;"""
new_pop = """if (s.trade_size_dollars !== undefined) document.getElementById('trade-size-dollars').value = s.trade_size_dollars;
                if (s.trading_style !== undefined) document.getElementById('trading-style').value = s.trading_style;
                if (s.signal_source !== undefined) document.getElementById('signal-source').value = s.signal_source;"""

if old_pop in c:
    c = c.replace(old_pop, new_pop)
    
# Update save logic
old_save = """const size = parseFloat(document.getElementById('trade-size-pct').value) || 20.0;
        const sl = parseFloat(document.getElementById('stop-loss-pct').value) || 10.0;
        const toggleEl = document.getElementById('one-click-toggle');
        const oneClick = toggleEl ? toggleEl.checked : false;
        const forceEl = document.getElementById('force-trade-toggle');
        const autoForce = forceEl ? forceEl.checked : false;
        
        try {
            const res = await fetch('/api/auth/user/config', {
                method: "POST",
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ trade_size_pct: size, stop_loss_pct: sl, one_click_trade: oneClick, auto_force_trade: autoForce })
            });"""
            
new_save = """const size = parseFloat(document.getElementById('trade-size-dollars').value) || 50.0;
        const sl = parseFloat(document.getElementById('stop-loss-pct').value) || 10.0;
        const toggleEl = document.getElementById('one-click-toggle');
        const oneClick = toggleEl ? toggleEl.checked : false;
        const forceEl = document.getElementById('force-trade-toggle');
        const autoForce = forceEl ? forceEl.checked : false;
        const tStyle = document.getElementById('trading-style').value;
        const sSource = document.getElementById('signal-source').value;
        
        try {
            const res = await fetch('/api/auth/user/config', {
                method: "POST",
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ trade_size_dollars: size, stop_loss_pct: sl, one_click_trade: oneClick, auto_force_trade: autoForce, trading_style: tStyle, signal_source: sSource })
            });"""
            
if old_save in c:
    c = c.replace(old_save, new_save)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
