with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

new_js = """
    let globalCloseDate = null;
    let currentYesProb = '--';
    let currentNoProb = '--';

    // Standalone timer that updates the UI exactly every second
    setInterval(() => {
        if (globalCloseDate) {
            const diff = Math.max(0, globalCloseDate - new Date()) / 1000;
            const mins = Math.floor(diff / 60);
            const secs = Math.floor(diff % 60);
            document.getElementById('kalshi-time').innerText = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')} LEFT`;
        }
    }, 1000);

    async function pollKalshi() {
        try {
            const [kRes, tRes] = await Promise.all([
                fetch('/api/engine/btc/kalshi'),
                fetch('/api/engine/btc/ticker')
            ]);
            
            if(tRes.ok) {
                const tData = await tRes.json();
                if(tData && tData.price) {
                    document.getElementById('live-btc-price').innerText = '$' + parseFloat(tData.price).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    document.getElementById('live-btc-price').classList.remove('animate-pulse');
                }
            }

            if(kRes.ok) {
                const data = await kRes.json();
                if(data.target_price) {
                    document.getElementById('kalshi-target').innerText = '$' + data.target_price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    
                    currentYesProb = Math.round(data.yes_prob || 0);
                    currentNoProb = Math.round(data.no_prob || 0);
                    
                    document.getElementById('kalshi-yes').innerText = currentYesProb;
                    document.getElementById('kalshi-no').innerText = currentNoProb;
                    
                    // Update the Manual Trade buttons dynamically
                    document.getElementById('btn-buy-yes').innerText = `BUY YES (${currentYesProb}%)`;
                    document.getElementById('btn-buy-no').innerText = `BUY NO (${currentNoProb}%)`;
                    
                    if(data.close_time) {
                        globalCloseDate = new Date(data.close_time);
                    }
                } else {
                    document.getElementById('kalshi-target').innerText = "NO ACTIVE MARKET";
                    document.getElementById('kalshi-time').innerText = "WAITING";
                    document.getElementById('kalshi-yes').innerText = "--";
                    document.getElementById('kalshi-no').innerText = "--";
                    document.getElementById('btn-buy-yes').innerText = `BUY YES`;
                    document.getElementById('btn-buy-no').innerText = `BUY NO`;
                    globalCloseDate = null;
                }
            }
        } catch(e){}
    }
"""

old_poll = """    async function pollKalshi() {
        try {
            const [kRes, tRes] = await Promise.all([
                fetch('/api/engine/btc/kalshi'),
                fetch('/api/engine/btc/ticker')
            ]);
            
            if(tRes.ok) {
                const tData = await tRes.json();
                if(tData && tData.price) {
                    document.getElementById('live-btc-price').innerText = '$' + parseFloat(tData.price).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    document.getElementById('live-btc-price').classList.remove('animate-pulse');
                }
            }

            if(kRes.ok) {
                const data = await kRes.json();
                if(data.target_price) {
                    document.getElementById('kalshi-target').innerText = '$' + data.target_price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    document.getElementById('kalshi-yes').innerText = Math.round(data.yes_prob || 0);
                    document.getElementById('kalshi-no').innerText = Math.round(data.no_prob || 0);
                    
                    if(data.close_time) {
                        const closeDate = new Date(data.close_time);
                        const diff = Math.max(0, closeDate - new Date()) / 1000;
                        const mins = Math.floor(diff / 60);
                        const secs = Math.floor(diff % 60);
                        document.getElementById('kalshi-time').innerText = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')} LEFT`;
                    }
                } else {
                    document.getElementById('kalshi-target').innerText = "NO ACTIVE MARKET";
                    document.getElementById('kalshi-time').innerText = "WAITING";
                    document.getElementById('kalshi-yes').innerText = "--";
                    document.getElementById('kalshi-no').innerText = "--";
                }
            }
        } catch(e){}
    }"""

c = c.replace(old_poll, new_js)

# Give the buttons IDs so we can target them
old_btns = """            <div class="flex gap-2 mb-2">
                <button onclick="executeManualTrade('YES')" class="flex-1 py-2.5 bg-green-600 hover:bg-green-500 text-white font-bold text-sm uppercase rounded shadow-[0_0_10px_rgba(0,255,136,0.2)] transition-colors active:scale-95 border border-green-500/50">Buy YES</button>
                <button onclick="executeManualTrade('NO')" class="flex-1 py-2.5 bg-red-600 hover:bg-red-500 text-white font-bold text-sm uppercase rounded shadow-[0_0_10px_rgba(255,68,68,0.2)] transition-colors active:scale-95 border border-red-500/50">Buy NO</button>
            </div>"""

new_btns = """            <div class="flex gap-2 mb-2">
                <button id="btn-buy-yes" onclick="executeManualTrade('YES')" class="flex-1 py-2.5 bg-green-600 hover:bg-green-500 text-white font-bold text-sm uppercase rounded shadow-[0_0_10px_rgba(0,255,136,0.2)] transition-colors active:scale-95 border border-green-500/50">Buy YES</button>
                <button id="btn-buy-no" onclick="executeManualTrade('NO')" class="flex-1 py-2.5 bg-red-600 hover:bg-red-500 text-white font-bold text-sm uppercase rounded shadow-[0_0_10px_rgba(255,68,68,0.2)] transition-colors active:scale-95 border border-red-500/50">Buy NO</button>
            </div>"""

c = c.replace(old_btns, new_btns)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
