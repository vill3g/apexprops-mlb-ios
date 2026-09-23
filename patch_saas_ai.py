with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

ai_toggle_html = """
        <!-- AI Listen Toggle -->
        <div class="mb-6 p-4 bg-black border border-kalshi-border rounded-lg flex justify-between items-center">
            <div>
                <label class="text-xs font-bold text-gray-300 uppercase tracking-widest block">AI Copy Trading</label>
                <span class="text-[9px] text-gray-500 uppercase tracking-wider">Listen for autonomous signals</span>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" id="ai-toggle-btn" class="sr-only peer" onchange="toggleAI(this.checked)">
                <div class="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-kalshi-green"></div>
            </label>
        </div>
"""

c = c.replace('<!-- API Config -->', ai_toggle_html + '        <!-- API Config -->')

js_funcs = """
    let aiEnabled = true;

    async function toggleAI(enabled) {
        try {
            const res = await fetch('/api/auth/ai_toggle', {
                method: "POST",
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ enabled: enabled })
            });
            if(res.ok) {
                aiEnabled = enabled;
                loadDashboard();
            }
        } catch(e) {}
    }
"""

c = c.replace('async function setTradingMode(mode) {', js_funcs + '\n    async function setTradingMode(mode) {')

# update loadDashboard to parse ai_enabled and set the toggle, and update connection status.
new_status_logic = """
                aiEnabled = s.ai_enabled;
                document.getElementById('ai-toggle-btn').checked = aiEnabled;

                const statusEl = document.getElementById('connection-status');
                if (!aiEnabled) {
                    statusEl.innerText = "Paused (AI Ignored)";
                    statusEl.className = "text-[10px] uppercase font-bold text-gray-500 tracking-wider";
                } else if (currentMode === "LIVE" && s.balance_dollars === null) {
                    statusEl.innerText = "Keys Required";
                    statusEl.className = "text-[10px] uppercase font-bold text-kalshi-red tracking-wider";
                } else {
                    statusEl.innerText = "Listening for Signals...";
                    statusEl.className = "text-[10px] uppercase font-bold text-kalshi-green tracking-wider";
                }
"""

c = c.replace("""                const statusEl = document.getElementById('connection-status');
                if (currentMode === "LIVE" && s.balance_dollars === null) {
                    statusEl.innerText = "Keys Required";
                    statusEl.className = "text-[10px] uppercase font-bold text-kalshi-red tracking-wider";
                } else {
                    statusEl.innerText = "Listening for Signals...";
                    statusEl.className = "text-[10px] uppercase font-bold text-kalshi-green tracking-wider";
                }""", new_status_logic)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
