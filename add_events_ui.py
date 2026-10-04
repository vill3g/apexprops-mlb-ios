import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# We need to hide #lw-chart-container and #stats-bar and show #sports-event-list when SPORTS is selected.
html = html.replace('<!-- TradingView / Lightweight Charts Area -->', '''<!-- TradingView / Lightweight Charts Area -->
                    <div id="sports-event-list" class="hidden w-full h-full overflow-y-auto p-4 bg-[#0b101a] text-gray-300">
                        <div class="flex items-center justify-between mb-4">
                            <h2 class="text-sm font-bold text-gray-200">ACTIVE KALSHI SPORTS EVENTS</h2>
                            <button onclick="loadSportsEvents()" class="px-3 py-1 bg-gray-800 hover:bg-gray-700 rounded text-xs">REFRESH</button>
                        </div>
                        <div id="sports-events-container" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            <!-- Events populated here -->
                        </div>
                    </div>''')

# Now in selectUniverse
html = html.replace('''                const sportsConf = document.getElementById('sports-confidence-container');
                if (sportsConf) sportsConf.classList.remove('hidden');''', '''                const sportsConf = document.getElementById('sports-confidence-container');
                if (sportsConf) sportsConf.classList.remove('hidden');
                
                document.getElementById('lw-chart-container').style.display = 'none';
                document.getElementById('stats-bar').style.display = 'none';
                document.getElementById('sports-event-list').style.display = 'block';
                document.getElementById('sports-event-list').classList.remove('hidden');
                loadSportsEvents();''')

html = html.replace('''                const sportsConf = document.getElementById('sports-confidence-container');
                if (sportsConf) sportsConf.classList.add('hidden');''', '''                const sportsConf = document.getElementById('sports-confidence-container');
                if (sportsConf) sportsConf.classList.add('hidden');
                
                document.getElementById('lw-chart-container').style.display = 'block';
                document.getElementById('stats-bar').style.display = 'flex';
                document.getElementById('sports-event-list').style.display = 'none';''')

# Add the JS to load events
js_code = '''
        async function loadSportsEvents() {
            const container = document.getElementById('sports-events-container');
            container.innerHTML = '<div class="col-span-full text-center text-gray-500 py-10">Scanning Kalshi APIs for active games...</div>';
            try {
                const res = await fetch((window.API_BASE_URL||'') + '/api/engine/sports/events');
                if (!res.ok) throw new Error("HTTP " + res.status);
                const data = await res.json();
                
                if (!data.events || data.events.length === 0) {
                    container.innerHTML = '<div class="col-span-full text-center text-gray-500 py-10">No active AI picks found for Kalshi markets currently.</div>';
                    return;
                }
                
                container.innerHTML = '';
                data.events.forEach(evt => {
                    const el = document.createElement('div');
                    el.className = 'bg-black/40 border border-white/5 rounded-xl p-4 flex flex-col gap-2 hover:border-cyan-500/30 transition-colors';
                    el.innerHTML = 
                        <div class="flex justify-between items-center">
                            <span class="text-xs font-black text-gray-400 bg-gray-800 px-2 py-0.5 rounded"></span>
                            <span class="text-xs font-mono text-cyan-400">AI Edge: %</span>
                        </div>
                        <div class="text-sm font-bold text-white mt-1"></div>
                        <div class="text-xs text-gray-400">Prediction: <span class="text-emerald-400 font-bold"></span></div>
                        <div class="flex justify-between items-center mt-2 pt-2 border-t border-white/5">
                            <div class="flex flex-col">
                                <span class="text-[9px] text-gray-500 uppercase">Confidence</span>
                                <span class="text-xs font-mono font-bold text-white">%</span>
                            </div>
                            <div class="flex flex-col text-right">
                                <span class="text-[9px] text-gray-500 uppercase">Implied Odds</span>
                                <span class="text-xs font-mono font-bold text-gray-300">%</span>
                            </div>
                        </div>
                    ;
                    container.appendChild(el);
                });
            } catch(e) {
                container.innerHTML = <div class="col-span-full text-center text-red-500 py-10">Failed to load events: </div>;
            }
        }
'''

html = html.replace('function selectDashboardAsset(asset)', js_code + '\n        function selectDashboardAsset(asset)')
html = html.replace('async function selectDashboardAsset(asset)', js_code + '\n        async function selectDashboardAsset(asset)')


with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Added sports event listing UI')
