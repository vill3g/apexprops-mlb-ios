import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# I will replace the stop_loss section with a toggle + pct input, identical to take_profit

old_stop_loss = '''                    <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                        <div class="cursor-pointer select-none group" onclick="toggleGlassInfo('stop_loss', this, event)">
                            <div class="flex items-center gap-1.5">
                                <label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest cursor-pointer group-hover:text-purple-300 transition-colors">Stop Loss</label>
                                <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-purple-500/20 border border-white/10 group-hover:border-purple-500/40 flex items-center justify-center text-[9px] font-bold text-gray-400 group-hover:text-purple-300 transition-all">i</span>
                            </div>
                            <div class="text-[10px] text-gray-500 uppercase font-bold mt-0.5">Exit if loss reaches this %</div>
                        </div>
                        <div class="flex items-center gap-1">
                            <input type="number" id="stop-loss-pct" onchange="saveUserConfig(true)" oninput="saveUserConfig()" class="w-16 bg-black border border-red-500/40 rounded-lg py-1.5 px-2 text-xs text-red-300 font-bold text-center focus:border-red-400 focus:outline-none" min="1" max="100" step="1" placeholder="30" inputmode="numeric">
                            <span class="text-xs font-bold text-red-400">%</span>
                        </div>
                    </div>'''

new_stop_loss = '''                    <div class="flex flex-col border-b border-kalshi-border/50 pb-3 gap-3">
                        <div class="flex justify-between items-center">
                            <div class="flex items-center gap-1.5 cursor-pointer select-none group" onclick="toggleGlassInfo('stop_loss', this, event)">
                                <label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest cursor-pointer group-hover:text-purple-300 transition-colors">Enable Stop Loss</label>
                                <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-purple-500/20 border border-white/10 group-hover:border-purple-500/40 flex items-center justify-center text-[9px] font-bold text-gray-400 group-hover:text-purple-300 transition-all">i</span>
                            </div>
                            <label class="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" id="stop-loss-enabled" class="sr-only peer" onchange="saveUserConfig(true); toggleStopLossPctVisibility()">
                                <div class="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-500"></div>
                            </label>
                        </div>
                        <div id="stop-loss-pct-row" class="flex justify-between items-center transition-all duration-300 overflow-hidden">
                            <div class="flex items-center gap-1.5 cursor-pointer select-none group" onclick="toggleGlassInfo('stop_loss', this, event)">
                                <label class="text-[11px] font-bold text-gray-400 uppercase tracking-widest cursor-pointer transition-colors">Target (%)</label>
                            </div>
                            <div class="flex items-center gap-1">
                                <input type="number" id="stop-loss-pct" onchange="saveUserConfig(true)" oninput="saveUserConfig()" class="w-16 bg-black border border-red-500/40 rounded-lg py-1.5 px-2 text-xs text-red-300 font-bold text-center focus:border-red-400 focus:outline-none" min="1" max="100" step="1" placeholder="30" inputmode="numeric">
                                <span class="text-xs font-bold text-red-400">%</span>
                            </div>
                        </div>
                    </div>'''

if old_stop_loss in content:
    content = content.replace(old_stop_loss, new_stop_loss)
    with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\saas_dashboard.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced HTML block!")
else:
    print("Could not find old_stop_loss HTML!")
