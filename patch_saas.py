import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_filter = """            const list = all.filter(e => {
                if (!isSportMatch(e, f)) return false;
                const startEpoch = parseFloat(e.start_epoch) || 0;
                const isLive = startEpoch > 0 && startEpoch < nowSec && !/KX(?:NFL|NBA|MLB|NHL)WINS|TOTAL WINS|WINS-\d/i.test(String(evt.event_ticker||evt.ticker||'')+' '+String(evt.title||''));
                if (isLive && !includeLive) return false;
                return true;
            });"""

new_filter = """            const list = all.filter(e => {
                if (!isSportMatch(e, f)) return false;
                if (e.market_type === 'Futures' || e.prop_type === 'Futures') return false; // Exclude Futures from default list
                const startEpoch = parseFloat(e.start_epoch) || 0;
                const isLive = startEpoch > 0 && startEpoch < nowSec && !/KX(?:NFL|NBA|MLB|NHL)WINS|TOTAL WINS|WINS-\d/i.test(String(e.event_ticker||e.ticker||'')+' '+String(e.title||''));
                if (isLive && !includeLive) return false;
                return true;
            });"""

content = content.replace(old_filter, new_filter)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched saas_dashboard.html")
