import re
with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

load_old = '''            if (s.paper_trade_size_dollars !== undefined && document.getElementById('paper-trade-size-dollars')) {'''
load_new = '''            if (s.trading_universe !== undefined && document.getElementById('universe-select')) {
                document.getElementById('universe-select').value = s.trading_universe;
                if (typeof toggleUniverse === 'function') toggleUniverse();
            }
            if (s.min_sports_confidence !== undefined && document.getElementById('sports-conf-slider')) {
                document.getElementById('sports-conf-slider').value = s.min_sports_confidence;
                if (document.getElementById('sports-conf-val')) {
                    document.getElementById('sports-conf-val').innerText = s.min_sports_confidence + '.0%';
                }
            }
            if (s.paper_trade_size_dollars !== undefined && document.getElementById('paper-trade-size-dollars')) {'''
html = html.replace(load_old, load_new)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Fixed loadUserConfig')
