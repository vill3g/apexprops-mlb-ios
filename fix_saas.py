import re
import os

target_file = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html"

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Replace renderEquitySvgChart
new_render_equity = """        function renderEquitySvgChart(points) {
            const wrapper = document.getElementById('equity-chart-wrapper');
            if (!wrapper) return;
            if (points.length < 2) {
                wrapper.innerHTML = '<div class="text-[10px] text-gray-500 font-mono">Need at least 2 closed trades to chart equity curve</div>';
                return;
            }
            wrapper.innerHTML = '';
            
            const chart = LightweightCharts.createChart(wrapper, {
                width: wrapper.clientWidth,
                height: 240,
                layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#9ca3af' },
                grid: { vertLines: { color: 'rgba(255, 255, 255, 0.05)' }, horzLines: { color: 'rgba(255, 255, 255, 0.05)' } },
                rightPriceScale: { borderVisible: false },
                timeScale: { borderVisible: false, timeVisible: true }
            });
            const lineSeries = chart.addAreaSeries({
                lineColor: points[points.length-1].pnl >= 0 ? '#10b981' : '#f43f5e',
                topColor: points[points.length-1].pnl >= 0 ? 'rgba(16, 185, 129, 0.4)' : 'rgba(244, 63, 94, 0.4)',
                bottomColor: 'rgba(0, 0, 0, 0.0)',
                lineWidth: 2
            });
            
            const data = [];
            let lastTime = 0;
            for (let i = 0; i < points.length; i++) {
                let p = points[i];
                let ts = p.ts ? Math.floor(p.ts) : (Math.floor(Date.now() / 1000) - (points.length - i) * 60);
                if (ts <= lastTime) { ts = lastTime + 1; }
                data.push({ time: ts, value: p.pnl });
                lastTime = ts;
            }
            lineSeries.setData(data);
            chart.timeScale().fitContent();
        }"""

pattern = re.compile(r"function renderEquitySvgChart\(points\)\s*\{.*?(?=\s*// Update execution panel from status data)", re.DOTALL)
content = pattern.sub(new_render_equity + "\n\n", content)

# 2. Fix the button text
button_pattern = re.compile(r"<button onclick=\"openBacktestModal\(\)\".*?>\s*<span>.*?</span>.*?</button>", re.DOTALL)
new_button = """<button onclick="openBacktestModal()" class="w-full py-2 bg-cyan-950/40 hover:bg-cyan-900/60 text-cyan-300 rounded-lg active:scale-95 transition-all border border-cyan-800/40 font-bold uppercase tracking-wider text-[10px] flex items-center justify-center gap-2 cursor-pointer">
            <span>⏪</span> AI Backtester (Time Machine)
        </button>"""
content = button_pattern.sub(new_button, content)

# 3. Remove backtester.js import
content = content.replace('<script src="./js/backtester.js?v=1791013020"></script>', '')

# 4. Inject #backtest-modal and JS at the end before </body>
backtest_modal_html = """
<div id="backtest-modal" class="hidden fixed inset-0 z-[1000] flex flex-col bg-[#0a0e17]">
    <div class="shrink-0 z-10 bg-black/80 border-b border-kalshi-border px-4 py-3 flex justify-between items-center gap-2" style="padding-top: calc(0.75rem + env(safe-area-inset-top, 0px));">
        <h2 class="text-white font-black tracking-wider uppercase text-sm">⏪ AI Backtester (Time Machine)</h2>
        <button onclick="closeBacktestModal()" class="px-3 py-1.5 bg-gray-800 text-gray-300 rounded-lg hover:bg-gray-700 font-bold uppercase text-xs">Back</button>
    </div>
    <div class="flex-1 overflow-y-auto p-4 max-w-4xl mx-auto w-full space-y-4">
        <div class="bg-[#0c0c10] border border-kalshi-border rounded-xl p-4 shadow-md space-y-4">
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="text-xs text-gray-400 font-bold">TP% (<span id="sim-tp-val">20</span>%)</label>
                    <input type="range" id="sim-tp" min="0" max="100" value="20" class="w-full accent-cyan-500" oninput="document.getElementById('sim-tp-val').innerText = this.value">
                </div>
                <div>
                    <label class="text-xs text-gray-400 font-bold">SL% (<span id="sim-sl-val">50</span>%)</label>
                    <input type="range" id="sim-sl" min="0" max="100" value="50" class="w-full accent-rose-500" oninput="document.getElementById('sim-sl-val').innerText = this.value">
                </div>
            </div>
            <button onclick="runBacktestSim()" class="w-full py-3 bg-cyan-600 hover:bg-cyan-500 text-white font-black uppercase text-xs rounded-lg">Run Simulation</button>
        </div>
        
        <div id="sim-results" class="hidden space-y-4">
            <div class="grid grid-cols-2 gap-4">
                <div class="bg-black/30 border border-white/5 p-4 rounded-xl text-center">
                    <div class="text-[10px] text-gray-500 uppercase font-bold mb-1">Simulated PnL</div>
                    <div id="sim-pnl" class="text-xl font-black tabular-nums">$0.00</div>
                </div>
                <div class="bg-black/30 border border-white/5 p-4 rounded-xl text-center">
                    <div class="text-[10px] text-gray-500 uppercase font-bold mb-1">Simulated Win Rate</div>
                    <div id="sim-wr" class="text-xl font-black tabular-nums">0%</div>
                </div>
            </div>
            <div class="bg-black/30 border border-white/5 p-4 rounded-xl">
                <div id="sim-chart-container" class="w-full h-48"></div>
            </div>
        </div>
    </div>
</div>

<script>
    function openBacktestModal() {
        document.getElementById('profileDropdown')?.classList.add('hidden');
        document.getElementById('backtest-modal').classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }
    
    function closeBacktestModal() {
        document.getElementById('backtest-modal').classList.add('hidden');
        document.body.style.overflow = 'auto';
    }
    
    let simChart = null;
    let simLineSeries = null;
    
    async function runBacktestSim() {
        const tp = parseFloat(document.getElementById('sim-tp').value);
        const sl = parseFloat(document.getElementById('sim-sl').value);
        
        try {
            const token = localStorage.getItem('saas_token') || '';
            const res = await fetch((window.API_BASE_URL || '') + '/api/engine/backtest/simulate', {
                method: 'POST',
                headers: {
                    'Authorization': 'Bearer ' + token,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ tp_pct: tp, sl_pct: sl })
            });
            if (!res.ok) throw new Error("Simulation failed");
            const data = await res.json();
            
            document.getElementById('sim-results').classList.remove('hidden');
            
            const pnlEl = document.getElementById('sim-pnl');
            pnlEl.innerText = (data.net_pnl >= 0 ? '+$' : '-$') + Math.abs(data.net_pnl).toFixed(2);
            pnlEl.className = 'text-xl font-black tabular-nums ' + (data.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400');
            
            const wrEl = document.getElementById('sim-wr');
            wrEl.innerText = data.win_rate.toFixed(1) + '%';
            wrEl.className = 'text-xl font-black tabular-nums ' + (data.win_rate >= 50 ? 'text-emerald-400' : 'text-rose-400');
            
            const container = document.getElementById('sim-chart-container');
            container.innerHTML = '';
            
            simChart = LightweightCharts.createChart(container, {
                width: container.clientWidth,
                height: container.clientHeight,
                layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#9ca3af' },
                grid: { vertLines: { color: 'rgba(255,255,255,0.05)' }, horzLines: { color: 'rgba(255,255,255,0.05)' } },
                rightPriceScale: { borderVisible: false },
                timeScale: { borderVisible: false, timeVisible: true }
            });
            simLineSeries = simChart.addAreaSeries({
                lineColor: data.net_pnl >= 0 ? '#10b981' : '#f43f5e',
                topColor: data.net_pnl >= 0 ? 'rgba(16, 185, 129, 0.4)' : 'rgba(244, 63, 94, 0.4)',
                bottomColor: 'rgba(0, 0, 0, 0.0)',
                lineWidth: 2
            });
            
            const pts = [];
            let lastTime = 0;
            const points = data.points || [];
            for (let i = 0; i < points.length; i++) {
                let p = points[i];
                let ts = p.ts ? Math.floor(p.ts) : (Math.floor(Date.now() / 1000) - (points.length - i) * 60);
                if (ts <= lastTime) ts = lastTime + 1;
                pts.push({ time: ts, value: p.pnl });
                lastTime = ts;
            }
            if (pts.length > 0) {
                simLineSeries.setData(pts);
                simChart.timeScale().fitContent();
            }
        } catch (e) {
            console.error(e);
            alert("Error running simulation");
        }
    }
</script>
"""

content = content.replace("</body>", backtest_modal_html + "\n</body>")

with open(target_file, "w", encoding="utf-8") as f:
    f.write(content)
