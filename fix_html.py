import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

new_html = html.replace('<!-- Lightweight Chart & Live Bids -->', '''<!-- Lightweight Chart & Live Bids -->
                    <div id="sports-event-list" class="hidden absolute inset-0 z-20 w-full h-full overflow-y-auto p-4 bg-[#0b101a] text-gray-300">
                        <div class="flex items-center justify-between mb-4 sticky top-0 bg-[#0b101a] z-30 pb-2 border-b border-white/5">
                            <h2 class="text-sm font-bold text-gray-200 uppercase tracking-widest">Active Predictions</h2>
                            <button onclick="loadSportsEvents()" class="px-3 py-1 bg-white/5 hover:bg-white/10 border border-white/10 rounded text-xs transition-colors">REFRESH</button>
                        </div>
                        <div id="sports-events-container" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                            <!-- Events populated here -->
                        </div>
                    </div>''')

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(new_html)
print('added html')
