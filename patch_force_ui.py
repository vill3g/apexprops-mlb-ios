with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

# Insert the new "Force Copy ML Signal" button underneath "Save Preferences"
old_html = """            <button onclick="saveUserConfig()" class="w-full py-2 bg-kalshi-blue/10 hover:bg-kalshi-blue/20 text-kalshi-blue font-bold text-[10px] uppercase tracking-widest rounded transition-colors border border-kalshi-blue/30 mt-2">Save Preferences</button>
        </div>"""

new_html = """            <button onclick="saveUserConfig()" class="w-full py-2 bg-kalshi-blue/10 hover:bg-kalshi-blue/20 text-kalshi-blue font-bold text-[10px] uppercase tracking-widest rounded transition-colors border border-kalshi-blue/30 mt-2">Save Preferences</button>
            <button onclick="forceMLTrade()" class="w-full py-2 bg-purple-900/40 hover:bg-purple-800 text-purple-400 font-bold text-[10px] uppercase tracking-widest rounded transition-colors border border-purple-500/50 mt-2 shadow-[0_0_10px_rgba(168,85,247,0.2)]">⚡ Force Copy ML Signal Now</button>
        </div>"""

c = c.replace(old_html, new_html)

# Add the JavaScript function
js_code = """
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
                toggleSettings(); // Close modal
            } else {
                alert(`Action Failed: ${data.detail}`);
            }
        } catch(e) {
            alert('Network error executing force trade.');
        }
    }
"""

c = c.replace("</script>", js_code + "\n</script>")

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
