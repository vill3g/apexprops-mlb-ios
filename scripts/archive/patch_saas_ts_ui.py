import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. UI Blocks
old_ui_block = '''                <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                    <div>
                        <label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest">Take Profit (%)</label>
                        <div class="text-[8px] text-gray-500 uppercase font-bold">Auto-close target</div>
                    </div>
                    <input type="number" id="take-profit-pct" class="w-16 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-xs text-white font-bold text-center focus:border-kalshi-blue focus:outline-none" min="1" max="1000" inputmode="numeric">
                </div>'''

new_ui_block = '''                <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                    <div>
                        <label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest">Take Profit (%)</label>
                        <div class="text-[8px] text-gray-500 uppercase font-bold">Auto-close target</div>
                    </div>
                    <input type="number" id="take-profit-pct" class="w-16 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-xs text-white font-bold text-center focus:border-kalshi-blue focus:outline-none" min="1" max="1000" inputmode="numeric" onchange="saveUserConfig()">
                </div>
                <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                    <div>
                        <label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest">Trailing Stop</label>
                        <div class="text-[8px] text-gray-500 uppercase font-bold">Lock in secured profits</div>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer gap-2">
                      <span id="trailing-stop-text" class="text-[9px] font-bold text-gray-500 uppercase tracking-widest">OFF</span>
                      <input type="checkbox" id="trailing-stop-toggle" class="sr-only peer" onchange="document.getElementById('trailing-stop-text').innerText = this.checked ? 'ON' : 'OFF'; document.getElementById('trailing-stop-text').className = this.checked ? 'text-[9px] font-bold text-emerald-400 uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest'; saveUserConfig();">
                      <div class="w-10 h-5 bg-gray-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[41px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-500"></div>
                    </label>
                </div>
                <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                    <div>
                        <label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest">Trail Activation (%)</label>
                        <div class="text-[8px] text-gray-500 uppercase font-bold">Minimum profit before trailing begins</div>
                    </div>
                    <input type="number" id="trailing-stop-activation-pct" class="w-16 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-xs text-white font-bold text-center focus:border-kalshi-blue focus:outline-none" min="1" max="1000" inputmode="numeric" onchange="saveUserConfig()">
                </div>
                <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                    <div>
                        <label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest">Trail Distance (%)</label>
                        <div class="text-[8px] text-gray-500 uppercase font-bold">Max drawback from peak</div>
                    </div>
                    <input type="number" id="trailing-stop-distance-pct" class="w-16 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-xs text-white font-bold text-center focus:border-kalshi-blue focus:outline-none" min="1" max="100" inputmode="numeric" onchange="saveUserConfig()">
                </div>'''
content = content.replace(old_ui_block, new_ui_block)

# Add onchange to other inputs while we are at it
content = content.replace('''id="trade-size-dollars" class="w-16 bg-black''', '''id="trade-size-dollars" onchange="saveUserConfig()" class="w-16 bg-black''')
content = content.replace('''id="stop-loss-pct" class="w-16 bg-black''', '''id="stop-loss-pct" onchange="saveUserConfig()" class="w-16 bg-black''')
content = content.replace('''id="max-daily-trades" class="w-16 bg-black''', '''id="max-daily-trades" onchange="saveUserConfig()" class="w-16 bg-black''')
content = content.replace('''id="max-daily-risk" class="w-16 bg-black''', '''id="max-daily-risk" onchange="saveUserConfig()" class="w-16 bg-black''')
content = content.replace('''id="trading-style" class="w-28 bg-black''', '''id="trading-style" onchange="saveUserConfig()" class="w-28 bg-black''')
content = content.replace('''id="signal-source" class="w-28 bg-black''', '''id="signal-source" onchange="saveUserConfig()" class="w-28 bg-black''')

# 2. saveUserConfig
old_save_js = '''            const tStyle = document.getElementById('trading-style').value;
            const sSource = document.getElementById('signal-source').value;
            
            try {
                const res = await fetch('/api/auth/user/config', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        trade_size_dollars: size,
                        stop_loss_pct: sl,
                        take_profit_pct: tp,
                        max_daily_trades: mdt,
                        max_daily_risk: mdr,
                        one_click_trade: oneClick,
                        auto_force_trade: autoForce,
                        trading_style: tStyle,
                        signal_source: sSource
                    })
                });'''

new_save_js = '''            const tStyle = document.getElementById('trading-style').value;
            const sSource = document.getElementById('signal-source').value;
            
            const tsToggle = document.getElementById('trailing-stop-toggle');
            const tsEnabled = tsToggle ? tsToggle.checked : false;
            const tsAct = parseFloat(document.getElementById('trailing-stop-activation-pct').value) || 35.0;
            const tsDist = parseFloat(document.getElementById('trailing-stop-distance-pct').value) || 6.0;
            
            try {
                const res = await fetch('/api/auth/user/config', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        trade_size_dollars: size,
                        stop_loss_pct: sl,
                        take_profit_pct: tp,
                        max_daily_trades: mdt,
                        max_daily_risk: mdr,
                        one_click_trade: oneClick,
                        auto_force_trade: autoForce,
                        trading_style: tStyle,
                        signal_source: sSource,
                        trailing_stop_enabled: tsEnabled,
                        trailing_stop_activation_pct: tsAct,
                        trailing_stop_distance_pct: tsDist
                    })
                });'''
content = content.replace(old_save_js, new_save_js)

# 3. loadDashboard
old_load_js = '''                if (document.activeElement.id !== 'take-profit-pct' && s.take_profit_pct !== undefined) document.getElementById('take-profit-pct').value = s.take_profit_pct;
                if (document.activeElement.id !== 'max-daily-trades' && s.max_daily_trades !== undefined) document.getElementById('max-daily-trades').value = s.max_daily_trades;
                if (document.activeElement.id !== 'max-daily-risk' && s.max_daily_risk !== undefined) document.getElementById('max-daily-risk').value = s.max_daily_risk;'''

new_load_js = '''                if (document.activeElement.id !== 'take-profit-pct' && s.take_profit_pct !== undefined) document.getElementById('take-profit-pct').value = s.take_profit_pct;
                if (document.activeElement.id !== 'max-daily-trades' && s.max_daily_trades !== undefined) document.getElementById('max-daily-trades').value = s.max_daily_trades;
                if (document.activeElement.id !== 'max-daily-risk' && s.max_daily_risk !== undefined) document.getElementById('max-daily-risk').value = s.max_daily_risk;
                
                if (document.activeElement.id !== 'trailing-stop-activation-pct' && s.trailing_stop_activation_pct !== undefined) document.getElementById('trailing-stop-activation-pct').value = s.trailing_stop_activation_pct;
                if (document.activeElement.id !== 'trailing-stop-distance-pct' && s.trailing_stop_distance_pct !== undefined) document.getElementById('trailing-stop-distance-pct').value = s.trailing_stop_distance_pct;
                
                const tsEl = document.getElementById('trailing-stop-toggle');
                if (tsEl && s.trailing_stop_enabled !== undefined && document.activeElement.id !== 'trailing-stop-toggle') {
                    tsEl.checked = !!s.trailing_stop_enabled;
                    document.getElementById('trailing-stop-text').innerText = tsEl.checked ? 'ON' : 'OFF';
                    document.getElementById('trailing-stop-text').className = tsEl.checked ? 'text-[9px] font-bold text-emerald-400 uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';
                }'''
content = content.replace(old_load_js, new_load_js)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
