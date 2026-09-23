with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

new_ui = """
        <!-- AI & Trade Preferences -->
        <div class="mb-6 p-4 bg-black border border-kalshi-border rounded-lg space-y-4">
            <div class="flex justify-between items-center border-b border-kalshi-border pb-3">
                <div>
                    <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">1-Click Manual Trade</label>
                    <div class="text-[9px] text-gray-500 uppercase">Remove confirmation dialogs</div>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" id="one-click-toggle" class="sr-only peer">
                  <div class="w-9 h-5 bg-gray-700 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-kalshi-green"></div>
                </label>
            </div>
            
            <div class="flex justify-between items-center border-b border-kalshi-border pb-3">
                <div>
                    <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">AI Copy Size (%)</label>
                    <div class="text-[9px] text-gray-500 uppercase">Percent of balance per trade</div>
                </div>
                <input type="number" id="trade-size-pct" class="w-16 bg-[#131b2c] border border-kalshi-border rounded py-1 px-2 text-xs text-white font-bold text-center focus:outline-none" min="1" max="100">
            </div>

            <div class="flex justify-between items-center">
                <div>
                    <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">AI Stop Loss (%)</label>
                    <div class="text-[9px] text-gray-500 uppercase">Auto-close if loss exceeds %</div>
                </div>
                <input type="number" id="stop-loss-pct" class="w-16 bg-[#131b2c] border border-kalshi-border rounded py-1 px-2 text-xs text-white font-bold text-center focus:outline-none" min="1" max="100">
            </div>
            <button onclick="saveUserConfig()" class="w-full py-2 bg-kalshi-blue/10 hover:bg-kalshi-blue/20 text-kalshi-blue font-bold text-[10px] uppercase tracking-widest rounded transition-colors border border-kalshi-blue/30 mt-2">Save Preferences</button>
        </div>
"""

# Replace exactly this part
target = "<!-- API Config -->"
if "AI & Trade Preferences" not in c or c.count("AI & Trade Preferences") > 5:
    # clean out the old bad javascript additions if any
    c = c.replace(target, new_ui + "\n        " + target)
    with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
        f.write(c)
