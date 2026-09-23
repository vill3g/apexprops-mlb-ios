import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

injection = """
                if (s.trade_size_pct !== undefined) document.getElementById('trade-size-pct').value = s.trade_size_pct;
                if (s.stop_loss_pct !== undefined) document.getElementById('stop-loss-pct').value = s.stop_loss_pct;
                
                const oneClickEl = document.getElementById('one-click-toggle');
                if (oneClickEl && s.one_click_trade !== undefined) {
                    oneClickEl.checked = !!s.one_click_trade;
                    document.getElementById('one-click-text').innerText = oneClickEl.checked ? 'ON' : 'OFF';
                    document.getElementById('one-click-text').className = oneClickEl.checked ? 'text-[10px] font-bold text-kalshi-green uppercase' : 'text-[10px] font-bold text-gray-500 uppercase';
                }
                
                const forceEl = document.getElementById('force-trade-toggle');
                if (forceEl && s.auto_force_trade !== undefined) {
                    forceEl.checked = !!s.auto_force_trade;
                    document.getElementById('force-trade-text').innerText = forceEl.checked ? 'ON' : 'OFF';
                    document.getElementById('force-trade-text').className = forceEl.checked ? 'text-[10px] font-bold text-purple-400 uppercase' : 'text-[10px] font-bold text-gray-500 uppercase';
                }
"""

# Insert right after `aiEnabled = s.ai_enabled;`
c = re.sub(
    r'(aiEnabled = s\.ai_enabled;)',
    r'\1' + injection,
    c
)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
