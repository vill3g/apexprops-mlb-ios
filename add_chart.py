with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace('<head>', '<head>\n  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>')

chart_html = """
    <!-- Live Market & Chart -->
    <div class="bg-kalshi-dark border border-kalshi-border rounded-xl shadow-lg overflow-hidden mt-6 mb-4">
        <div class="px-4 py-3 border-b border-kalshi-border bg-[#131b2c] flex justify-between items-center">
            <h2 class="text-xs font-bold uppercase tracking-widest text-gray-300">Active Market (BTC 15M)</h2>
            <div id="kalshi-time" class="text-[10px] font-bold text-kalshi-blue uppercase tracking-wider animate-pulse">--:-- LEFT</div>
        </div>
        <div class="p-4 grid grid-cols-2 gap-4 border-b border-kalshi-border">
            <div>
                <div class="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-1">Target Strike</div>
                <div id="kalshi-target" class="text-xl font-black tabular-nums tracking-tighter text-white">Loading...</div>
            </div>
            <div class="text-right">
                <div class="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-1">Current Odds</div>
                <div class="flex items-center justify-end gap-2 text-xs font-bold mt-1">
                    <span class="text-kalshi-green bg-green-900/30 px-2 py-1 rounded">YES <span id="kalshi-yes">--</span>¢</span>
                    <span class="text-kalshi-red bg-red-900/30 px-2 py-1 rounded">NO <span id="kalshi-no">--</span>¢</span>
                </div>
            </div>
        </div>
        <div class="w-full h-[250px] relative">
            <div id="tv_chart_container" class="absolute inset-0"></div>
        </div>
    </div>
"""

c = c.replace('<!-- Live Trades Ledger -->', chart_html + '\n    <!-- Live Trades Ledger -->')

js_inject = """
    // Load TradingView Chart
    setTimeout(() => {
        if(window.TradingView) {
            new TradingView.widget({
                autosize: true,
                symbol: "BINANCE:BTCUSDT",
                interval: "15",
                timezone: "America/New_York",
                theme: "dark",
                style: "1",
                locale: "en",
                toolbar_bg: "#0b0f19",
                enable_publishing: false,
                allow_symbol_change: false,
                hide_side_toolbar: true,
                withdateranges: false,
                hide_top_toolbar: true,
                save_image: false,
                container_id: "tv_chart_container",
                studies: []
            });
        }
    }, 500);

    // Poll public Kalshi data
    async function pollKalshi() {
        try {
            const res = await fetch('/api/engine/btc/kalshi');
            if(res.ok) {
                const data = await res.json();
                if(data.target) {
                    document.getElementById('kalshi-target').innerText = data.target;
                    document.getElementById('kalshi-yes').innerText = Math.round(data.yes_price * 100);
                    document.getElementById('kalshi-no').innerText = Math.round(data.no_price * 100);
                    if(data.time_left) document.getElementById('kalshi-time').innerText = data.time_left.toUpperCase();
                } else {
                    document.getElementById('kalshi-target').innerText = "NO ACTIVE MARKET";
                    document.getElementById('kalshi-time').innerText = "WAITING";
                    document.getElementById('kalshi-yes').innerText = "--";
                    document.getElementById('kalshi-no').innerText = "--";
                }
            }
        } catch(e){}
    }
    pollKalshi();
    setInterval(pollKalshi, 5000);
"""

c = c.replace('// Load immediately and refresh every 5 seconds', js_inject + '\n    // Load immediately and refresh every 5 seconds')

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
