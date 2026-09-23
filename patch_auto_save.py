import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Completely replace saveUserConfig
old_save_js_pattern = re.compile(r'async function saveUserConfig\(\) \{.*?\n        \}', re.DOTALL)

new_save_js = '''async function saveUserConfig() {
            const size = parseFloat(document.getElementById('trade-size-dollars').value) || 50.0;
            const sl = parseFloat(document.getElementById('stop-loss-pct').value) || 10.0;
            const tp = parseFloat(document.getElementById('take-profit-pct').value) || 50.0;
            const mdt = parseInt(document.getElementById('max-daily-trades').value) || 10;
            const mdr = parseFloat(document.getElementById('max-daily-risk').value) || 50.0;
            
            const toggleEl = document.getElementById('one-click-toggle');
            const oneClick = toggleEl ? toggleEl.checked : false;
            
            const forceEl = document.getElementById('force-trade-toggle');
            const autoForce = forceEl ? forceEl.checked : false;
            
            const tsToggle = document.getElementById('trailing-stop-toggle');
            const tsEnabled = tsToggle ? tsToggle.checked : false;
            const tsAct = parseFloat(document.getElementById('trailing-stop-activation-pct').value) || 35.0;
            const tsDist = parseFloat(document.getElementById('trailing-stop-distance-pct').value) || 6.0;
            
            const tStyle = document.getElementById('trading-style').value;
            const sSource = document.getElementById('signal-source').value;
            
            try {
                await fetch('/api/auth/user/config', {
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
                });
            } catch(e) {}
        }'''

content = old_save_js_pattern.sub(new_save_js, content, count=1)

# 2. Add onchange to trade-size-dollars
content = content.replace('id="trade-size-dollars" class="w-20 bg-black', 'id="trade-size-dollars" onchange="saveUserConfig()" oninput="saveUserConfig()" class="w-20 bg-black')

# 3. Add oninput to ALL numerical inputs to make it save IMMEDIATELY
content = content.replace('id="stop-loss-pct" onchange="saveUserConfig()"', 'id="stop-loss-pct" onchange="saveUserConfig()" oninput="saveUserConfig()"')
content = content.replace('id="take-profit-pct" class="w-16 bg-black', 'id="take-profit-pct" onchange="saveUserConfig()" oninput="saveUserConfig()" class="w-16 bg-black')
content = content.replace('id="take-profit-pct" onchange="saveUserConfig()" class="w-16 bg-black', 'id="take-profit-pct" onchange="saveUserConfig()" oninput="saveUserConfig()" class="w-16 bg-black')

content = content.replace('id="max-daily-trades" onchange="saveUserConfig()"', 'id="max-daily-trades" onchange="saveUserConfig()" oninput="saveUserConfig()"')
content = content.replace('id="max-daily-risk" onchange="saveUserConfig()"', 'id="max-daily-risk" onchange="saveUserConfig()" oninput="saveUserConfig()"')

content = content.replace('id="trailing-stop-activation-pct" class="w-16 bg-black', 'id="trailing-stop-activation-pct" onchange="saveUserConfig()" oninput="saveUserConfig()" class="w-16 bg-black')
content = content.replace('id="trailing-stop-activation-pct" onchange="saveUserConfig()" class="w-16 bg-black', 'id="trailing-stop-activation-pct" onchange="saveUserConfig()" oninput="saveUserConfig()" class="w-16 bg-black')

content = content.replace('id="trailing-stop-distance-pct" class="w-16 bg-black', 'id="trailing-stop-distance-pct" onchange="saveUserConfig()" oninput="saveUserConfig()" class="w-16 bg-black')
content = content.replace('id="trailing-stop-distance-pct" onchange="saveUserConfig()" class="w-16 bg-black', 'id="trailing-stop-distance-pct" onchange="saveUserConfig()" oninput="saveUserConfig()" class="w-16 bg-black')

# 4. Hide the "Save Configuration" button since it auto saves everything now
# Search for <button onclick="saveUserConfig()"
content = re.sub(r'<button onclick="saveUserConfig\(\)".*?</button>', '', content)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
