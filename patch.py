with open('static/saas_dashboard.html', 'r') as f:
    html = f.read()

js_code = """
        async function closeAllTrades() {
            const toggleEl = document.getElementById('one-click-toggle');
            const oneClick = toggleEl ? toggleEl.checked : false;
            
            if(!oneClick && !confirm('Are you sure you want to close all open trades?')) return;

            try {
                const res = await fetch('/api/engine/btc/trade/close', {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + token }
                });
                if(res.ok) {
                    const data = await res.json();
                    if(!oneClick) alert(data.success ? 'Closed trades successfully.' : 'Failed to close trades: ' + data.error);
                    loadDashboard();
                } else {
                    const data = await res.json();
                    let errMsg = data.detail || data.error || 'Unknown Error';
                    if (typeof errMsg === 'object') errMsg = JSON.stringify(errMsg);
                    alert('Failed: ' + errMsg);
                }
            } catch(e) {
                alert('Error: ' + e);
            }
        }
"""

html = html.replace('async function executeManualTrade(direction)', js_code + '\n        async function executeManualTrade(direction)')

with open('static/saas_dashboard.html', 'w') as f:
    f.write(html)
