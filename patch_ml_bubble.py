with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

# 1. HTML change
old_time_div = """            <div class="text-right">
                <div id="kalshi-time" class="text-[11px] font-black text-kalshi-blue uppercase tracking-wider tabular-nums">--:-- LEFT</div>
            </div>"""

new_time_div = """            <div class="text-right flex flex-col items-end gap-1">
                <div class="flex items-center gap-2">
                    <div id="ml-status-bubble" class="px-1.5 py-[2px] rounded text-[8px] font-bold uppercase tracking-widest bg-gray-800 text-gray-400 border border-gray-600 shadow-sm transition-colors duration-300">AI: --</div>
                    <div id="kalshi-time" class="text-[11px] font-black text-kalshi-blue uppercase tracking-wider tabular-nums">--:-- LEFT</div>
                </div>
            </div>"""

c = c.replace(old_time_div, new_time_div)

# 2. JS change
new_js_fn = """
    async function pollML() {
        try {
            const res = await fetch('/api/engine/btc/analyze');
            if(res.ok) {
                const data = await res.json();
                const bubble = document.getElementById('ml-status-bubble');
                if(data.direction === 'ABOVE') {
                    bubble.innerText = 'AI: BUY YES';
                    bubble.className = 'px-1.5 py-[2px] rounded text-[8px] font-bold uppercase tracking-widest bg-green-900/40 text-emerald-400 border border-green-500/50 shadow-sm transition-colors duration-300 animate-pulse';
                } else if(data.direction === 'BELOW') {
                    bubble.innerText = 'AI: BUY NO';
                    bubble.className = 'px-1.5 py-[2px] rounded text-[8px] font-bold uppercase tracking-widest bg-red-900/40 text-red-400 border border-red-500/50 shadow-sm transition-colors duration-300 animate-pulse';
                } else {
                    bubble.innerText = 'AI: HOLD (CHOP)';
                    bubble.className = 'px-1.5 py-[2px] rounded text-[8px] font-bold uppercase tracking-widest bg-gray-800 text-gray-400 border border-gray-600 shadow-sm transition-colors duration-300';
                }
            }
        } catch(e) {}
    }
    
    pollML();
    setInterval(pollML, 8000);

    async function pollKalshi() {"""

c = c.replace("    async function pollKalshi() {", new_js_fn)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
