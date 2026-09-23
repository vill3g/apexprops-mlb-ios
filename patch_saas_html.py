import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add HTML inputs
stop_loss_block = '''                <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                    <div>
                        <label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest">Stop Loss (%)</label>
                        <div class="text-[8px] text-gray-500 uppercase font-bold">Auto-close threshold</div>
                    </div>
                    <input type="number" id="stop-loss-pct" class="w-16 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-xs text-white font-bold text-center focus:border-kalshi-blue focus:outline-none" min="1" max="100" inputmode="numeric">
                </div>'''

new_html_blocks = '''                <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                    <div>
                        <label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest">Stop Loss (%)</label>
                        <div class="text-[8px] text-gray-500 uppercase font-bold">Auto-close threshold</div>
                    </div>
                    <input type="number" id="stop-loss-pct" class="w-16 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-xs text-white font-bold text-center focus:border-kalshi-blue focus:outline-none" min="1" max="100" inputmode="numeric">
                </div>
                <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                    <div>
                        <label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest">Take Profit (%)</label>
                        <div class="text-[8px] text-gray-500 uppercase font-bold">Auto-close target</div>
                    </div>
                    <input type="number" id="take-profit-pct" class="w-16 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-xs text-white font-bold text-center focus:border-kalshi-blue focus:outline-none" min="1" max="1000" inputmode="numeric">
                </div>
                <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                    <div>
                        <label class="text-[11px] font-bold text-amber-500 uppercase tracking-widest">Max Daily Trades</label>
                        <div class="text-[8px] text-gray-500 uppercase font-bold">Limit overtrading</div>
                    </div>
                    <input type="number" id="max-daily-trades" class="w-16 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-xs text-white font-bold text-center focus:border-kalshi-blue focus:outline-none" min="1" max="500" inputmode="numeric">
                </div>
                <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                    <div>
                        <label class="text-[11px] font-bold text-red-500 uppercase tracking-widest">Max Daily Risk ($)</label>
                        <div class="text-[8px] text-gray-500 uppercase font-bold">Daily stop-loss limit</div>
                    </div>
                    <input type="number" id="max-daily-risk" class="w-16 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-xs text-white font-bold text-center focus:border-kalshi-blue focus:outline-none" min="1" max="5000" inputmode="numeric">
                </div>'''

content = content.replace(stop_loss_block, new_html_blocks)

# 2. Update saveUserConfig function
save_js_old = '''        async function saveUserConfig() {
            const size = parseFloat(document.getElementById('trade-size-dollars').value) || 50.0;
            const sl = parseFloat(document.getElementById('stop-loss-pct').value) || 10.0;
            const toggleEl = document.getElementById('one-click-toggle');
            const oneClick = toggleEl ? toggleEl.checked : false;
            const forceEl = document.getElementById('force-trade-toggle');
            const autoForce = forceEl ? forceEl.checked : false;
            const tStyle = document.getElementById('trading-style').value;
            const sSource = document.getElementById('signal-source').value;
            
            try {
                const res = await fetch('/api/auth/user/config', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        trade_size_dollars: size,
                        stop_loss_pct: sl,
                        one_click_trade: oneClick,
                        auto_force_trade: autoForce,
                        trading_style: tStyle,
                        signal_source: sSource
                    })
                });'''

save_js_new = '''        async function saveUserConfig() {
            const size = parseFloat(document.getElementById('trade-size-dollars').value) || 50.0;
            const sl = parseFloat(document.getElementById('stop-loss-pct').value) || 10.0;
            const tp = parseFloat(document.getElementById('take-profit-pct').value) || 50.0;
            const mdt = parseInt(document.getElementById('max-daily-trades').value) || 10;
            const mdr = parseFloat(document.getElementById('max-daily-risk').value) || 50.0;
            const toggleEl = document.getElementById('one-click-toggle');
            const oneClick = toggleEl ? toggleEl.checked : false;
            const forceEl = document.getElementById('force-trade-toggle');
            const autoForce = forceEl ? forceEl.checked : false;
            const tStyle = document.getElementById('trading-style').value;
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

content = content.replace(save_js_old, save_js_new)

# 3. Update loadDashboard function (the parts that pre-fill the inputs)
load_js_old = '''                if (document.activeElement.id !== 'stop-loss-pct' && s.stop_loss_pct !== undefined) document.getElementById('stop-loss-pct').value = s.stop_loss_pct;'''

load_js_new = '''                if (document.activeElement.id !== 'stop-loss-pct' && s.stop_loss_pct !== undefined) document.getElementById('stop-loss-pct').value = s.stop_loss_pct;
                if (document.activeElement.id !== 'take-profit-pct' && s.take_profit_pct !== undefined) document.getElementById('take-profit-pct').value = s.take_profit_pct;
                if (document.activeElement.id !== 'max-daily-trades' && s.max_daily_trades !== undefined) document.getElementById('max-daily-trades').value = s.max_daily_trades;
                if (document.activeElement.id !== 'max-daily-risk' && s.max_daily_risk !== undefined) document.getElementById('max-daily-risk').value = s.max_daily_risk;'''

content = content.replace(load_js_old, load_js_new)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)

