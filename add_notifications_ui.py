import re
path = "static/saas_dashboard.html"
with open(path, "r", encoding="utf-8") as f:
    html = f.read()

# Add Notifications Card before Model & Training Controls Card
notifications_card = """
            <!-- Notifications & Alerts Card -->
            <div class="bg-[#131b2c] border border-kalshi-border rounded-2xl overflow-hidden shadow-lg mb-4">
                <div class="bg-black/40 px-4 py-3 border-b border-kalshi-border flex items-center gap-2 text-kalshi-blue text-[10px] sm:text-xs font-bold uppercase tracking-widest">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path></svg>
                    Notifications & Alerts
                </div>
                <div class="p-4 space-y-3.5">
                    <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                        <div class="flex flex-col">
                            <label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest">Trade Results</label>
                            <span class="text-[9px] text-gray-500 font-bold">Alert when trades win or lose</span>
                        </div>
                        <label class="relative inline-flex items-center cursor-pointer">
                            <input type="checkbox" id="notify-trade-results" onchange="saveUserConfig(true)" class="sr-only peer" checked>
                            <div class="w-9 h-5 bg-gray-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-gray-400 peer-checked:after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-kalshi-blue"></div>
                        </label>
                    </div>
                    <div class="flex justify-between items-center">
                        <div class="flex flex-col">
                            <label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest">Market Trends</label>
                            <span class="text-[9px] text-gray-500 font-bold">Alert when market regime shifts</span>
                        </div>
                        <label class="relative inline-flex items-center cursor-pointer">
                            <input type="checkbox" id="notify-market-trends" onchange="saveUserConfig(true)" class="sr-only peer" checked>
                            <div class="w-9 h-5 bg-gray-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-gray-400 peer-checked:after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-kalshi-blue"></div>
                        </label>
                    </div>
                </div>
            </div>
"""

# Insert before Model & Training Controls Card
html = html.replace('<!-- Model & Training Controls Card -->', notifications_card + '<!-- Model & Training Controls Card -->')

with open(path, "w", encoding="utf-8") as f:
    f.write(html)
print("Added UI settings for notifications")
