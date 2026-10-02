with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

old_load = """const forceEl = document.getElementById('force-trade-toggle');
                if (forceEl) {
                    forceEl.checked = !!data.auto_force_trade;
                    document.getElementById('force-trade-text').innerText = forceEl.checked ? 'ON' : 'OFF';
                    document.getElementById('force-trade-text').className = forceEl.checked ? 'text-[10px] font-bold text-purple-400 uppercase' : 'text-[10px] font-bold text-gray-500 uppercase';
                }"""

new_load = """const forceEl = document.getElementById('force-trade-toggle');
                if (forceEl) {
                    forceEl.checked = !!data.auto_force_trade;
                    document.getElementById('force-trade-text').innerText = forceEl.checked ? 'ON' : 'OFF';
                    document.getElementById('force-trade-text').className = forceEl.checked ? 'text-[10px] font-bold text-purple-400 uppercase' : 'text-[10px] font-bold text-gray-500 uppercase';
                }
                const sizeEl = document.getElementById('trade-size-pct');
                if (sizeEl && data.trade_size_pct !== undefined) sizeEl.value = data.trade_size_pct;
                const slEl = document.getElementById('stop-loss-pct');
                if (slEl && data.stop_loss_pct !== undefined) slEl.value = data.stop_loss_pct;"""

if old_load in c:
    c = c.replace(old_load, new_load)
else:
    print("Could not find insertion point!")

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
