import re
import os

html_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html'
if os.path.exists(html_path):
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # Fix: res.json() before res.ok
    # Let's do a broader fix if we can't easily regex it.
    html = html.replace('const data = await res.json();\n                if (!res.ok)', 'if (!res.ok) { console.error("HTTP Error:", res.status); return; }\n                const data = await res.json();\n                if (false)')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

dash_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\dashboard.js'
if os.path.exists(dash_path):
    with open(dash_path, 'r', encoding='utf-8') as f:
        dash = f.read()
    dash = dash.replace(
        "fetch('/api/engine/btc/countdown').then(r => r.json())",
        "fetch('/api/engine/btc/countdown').then(r => { if(!r.ok) throw new Error('HTTP error'); return r.json(); })"
    )
    with open(dash_path, 'w', encoding='utf-8') as f:
        f.write(dash)

stat_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\strategy_stats.js'
if os.path.exists(stat_path):
    with open(stat_path, 'r', encoding='utf-8') as f:
        stat = f.read()
    stat = re.sub(r'setInterval\(load,\s*5\s*\*\s*60\s*\*\s*1000\);', r'if(window._strategyStatsInterval) clearInterval(window._strategyStatsInterval); window._strategyStatsInterval = setInterval(load, 5 * 60 * 1000);', stat)
    with open(stat_path, 'w', encoding='utf-8') as f:
        f.write(stat)
print('Frontend fixes applied.')
