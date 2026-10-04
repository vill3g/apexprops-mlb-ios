with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

part1 = html.split('        async function loadSportsEvents() {')[0]
part2 = html.split('        function selectDashboardAsset(asset)')[1]

correct_js = '''        async function loadSportsEvents() {
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
                    el.innerHTML = `
                        <div class="flex justify-between items-center">
                            <span class="text-xs font-black text-gray-400 bg-gray-800 px-2 py-0.5 rounded">${evt.sport}</span>
                            <span class="text-xs font-mono text-cyan-400">AI Edge: ${evt.edge_pct}%</span>
                        </div>
                        <div class="text-sm font-bold text-white mt-1">${evt.game}</div>
                        <div class="text-xs text-gray-400">Prediction: <span class="text-emerald-400 font-bold">${evt.predicted_team}</span></div>
                        <div class="flex justify-between items-center mt-2 pt-2 border-t border-white/5">
                            <div class="flex flex-col">
                                <span class="text-[9px] text-gray-500 uppercase">Confidence</span>
                                <span class="text-xs font-mono font-bold text-white">${evt.confidence_pct}%</span>
                            </div>
                            <div class="flex flex-col text-right">
                                <span class="text-[9px] text-gray-500 uppercase">Implied Odds</span>
                                <span class="text-xs font-mono font-bold text-gray-300">${evt.implied_odds_pct}%</span>
                            </div>
                        </div>
                    `;
                    container.appendChild(el);
                });
            } catch(e) {
                container.innerHTML = '<div class="col-span-full text-center text-red-500 py-10">Failed to load events: ' + e.message + '</div>';
            }
        }
'''

new_html = part1 + correct_js + '        function selectDashboardAsset(asset)' + part2

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(new_html)
print("done")
