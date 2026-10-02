import re
import os

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

target = "<!-- Active Trading Mode Selector Card -->"
heatmap = """<!-- Strategy Heatmap -->
            <div class="bg-[#131b2c] border border-kalshi-border rounded-2xl overflow-hidden shadow-lg mb-4 p-4">
              <label class="block text-[11px] font-black text-gray-200 uppercase tracking-widest mb-3 flex items-center gap-2">
                <svg class="w-4 h-4 text-kalshi-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                Strategy Performance
              </label>
              <div class="grid grid-cols-2 gap-3 text-[10px] font-mono">
                <div class="flex flex-col gap-1.5">
                  <div class="flex justify-between items-center"><span class="text-gray-400 font-bold tracking-wider">SNIPER</span><span class="text-emerald-400 font-black">78%</span></div>
                  <div class="h-1.5 bg-black/80 rounded-full flex overflow-hidden shadow-inner border border-kalshi-border/30"><div class="h-full bg-emerald-500 w-[78%]"></div><div class="h-full bg-red-500/80 w-[22%]"></div></div>
                </div>
                <div class="flex flex-col gap-1.5">
                  <div class="flex justify-between items-center"><span class="text-gray-400 font-bold tracking-wider">AMBUSH</span><span class="text-emerald-400 font-black">65%</span></div>
                  <div class="h-1.5 bg-black/80 rounded-full flex overflow-hidden shadow-inner border border-kalshi-border/30"><div class="h-full bg-emerald-500 w-[65%]"></div><div class="h-full bg-red-500/80 w-[35%]"></div></div>
                </div>
                <div class="flex flex-col gap-1.5">
                  <div class="flex justify-between items-center"><span class="text-gray-400 font-bold tracking-wider">CHOP</span><span class="text-emerald-400 font-black">82%</span></div>
                  <div class="h-1.5 bg-black/80 rounded-full flex overflow-hidden shadow-inner border border-kalshi-border/30"><div class="h-full bg-emerald-500 w-[82%]"></div><div class="h-full bg-red-500/80 w-[18%]"></div></div>
                </div>
                <div class="flex flex-col gap-1.5">
                  <div class="flex justify-between items-center"><span class="text-gray-400 font-bold tracking-wider">MOMENTUM</span><span class="text-emerald-400 font-black">71%</span></div>
                  <div class="h-1.5 bg-black/80 rounded-full flex overflow-hidden shadow-inner border border-kalshi-border/30"><div class="h-full bg-emerald-500 w-[71%]"></div><div class="h-full bg-red-500/80 w-[29%]"></div></div>
                </div>
              </div>
            </div>

            <!-- Active Trading Mode Selector Card -->"""

if target in html:
    html = html.replace(target, heatmap)
    with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("SaaS Heatmap injected!")
else:
    print("Could not find target in saas_dashboard.html!")
