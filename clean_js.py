import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Remove all saveUserConfig blocks
c = re.sub(r'\s*async function saveUserConfig\(\) \{.*?\}\s*', '\n', c, flags=re.DOTALL)

# 2. Remove all toggleMLPopup blocks
c = re.sub(r'\s*let lastMLData = null;\s*function toggleMLPopup\(e\) \{.*?\}\s*function fillMLPopup\(\) \{.*?\}.*?\}\);\s*', '\n', c, flags=re.DOTALL)

# 3. Remove all forceMLTrade blocks
c = re.sub(r'\s*async function forceMLTrade\(\) \{.*?\}\s*', '\n', c, flags=re.DOTALL)

# Now add them exactly ONCE at the very bottom right before the LAST </script>
js_code = """
    async function saveUserConfig() {
        const size = parseFloat(document.getElementById('trade-size-pct').value) || 20.0;
        const sl = parseFloat(document.getElementById('stop-loss-pct').value) || 10.0;
        const toggleEl = document.getElementById('one-click-toggle');
        const oneClick = toggleEl ? toggleEl.checked : false;
        
        try {
            const res = await fetch('/api/auth/user/config', {
                method: "POST",
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ trade_size_pct: size, stop_loss_pct: sl, one_click_trade: oneClick })
            });
            if(res.ok) {
                alert("AI & Trade Preferences Saved!");
            }
        } catch(e) {}
    }

    let lastMLData = null;
    
    function toggleMLPopup(e) {
        if(e) e.stopPropagation();
        const popup = document.getElementById('ml-details-popup');
        popup.classList.toggle('hidden');
        fillMLPopup();
    }
    
    function fillMLPopup() {
        if(!lastMLData) return;
        document.getElementById('popup-bias').innerText = lastMLData.primary_bias || '--';
        document.getElementById('popup-conf').innerText = `${lastMLData.confidence_percent || 0}%`;
        document.getElementById('popup-prob').innerText = `${((lastMLData.predicted_probability || 0)*100).toFixed(1)}%`;
        
        let confColor = 'text-gray-400';
        if(lastMLData.confidence_percent >= 60) confColor = 'text-kalshi-green';
        else if(lastMLData.confidence_percent <= 40) confColor = 'text-kalshi-red';
        document.getElementById('popup-conf').className = `font-bold ${confColor}`;
        
        let summaryText = '';
        if(lastMLData.summary) {
            summaryText = lastMLData.summary;
        } else {
            summaryText = `Model predicts ${lastMLData.primary_bias} with ${((lastMLData.predicted_probability || 0)*100).toFixed(1)}% probability based on timeframe analysis.`;
        }
        document.getElementById('popup-summary').innerText = summaryText;
    }
    
    document.addEventListener('click', (e) => {
        const popup = document.getElementById('ml-details-popup');
        const bubble = document.getElementById('ml-status-bubble');
        if(popup && !popup.classList.contains('hidden') && !popup.contains(e.target) && !bubble.contains(e.target)) {
            popup.classList.add('hidden');
        }
    });

    async function forceMLTrade() {
        const toggleEl = document.getElementById('one-click-toggle');
        const oneClick = toggleEl ? toggleEl.checked : false;
        if(!oneClick && !confirm(`Are you sure you want to FORCE the AI's current signal using your configured trade size in ${currentMode} mode?`)) return;
        
        try {
            const res = await fetch('/api/auth/trade/force_ml', {
                method: "POST",
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            if(res.ok) {
                alert(`⚡ Success! ML forced a ${data.side} trade for ${data.count} contracts at $${data.price}`);
                loadDashboard();
                if(typeof toggleSettings === 'function') toggleSettings(); // Close modal
            } else {
                alert(`Action Failed: ${data.detail}`);
            }
        } catch(e) {
            alert('Network error executing force trade.');
        }
    }
"""

# Find the LAST </script> tag
parts = c.rsplit('</script>', 1)
c_new = parts[0] + js_code + '\n</script>' + parts[1]

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c_new)
