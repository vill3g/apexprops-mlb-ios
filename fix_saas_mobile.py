import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Fix 1: CVD Gauge visibility on mobile
old_cvd = """                    <div class="hidden sm:flex items-center gap-1 bg-black/60 border border-kalshi-border/50 rounded-full px-2 py-0.5 h-5 w-20">
                      <span class="text-[7px] font-bold text-gray-500 uppercase shrink-0">CVD</span>
                      <div class="h-1 flex-1 bg-[#0d131f] rounded-full overflow-hidden flex items-center relative border border-kalshi-border">
                        <div id="cvdGaugeFillSaaS" class="h-full bg-kalshi-blue transition-all duration-300" style="width: 50%;"></div>
                        <div class="absolute w-[1px] h-full bg-gray-600 left-1/2"></div>
                      </div>
                    </div>"""
new_cvd = """                    <div class="flex items-center gap-1 bg-black/60 border border-kalshi-border/50 rounded-full px-1.5 py-0.5 h-4 w-12 sm:w-20 sm:h-5 sm:px-2">
                      <span class="text-[6px] sm:text-[7px] font-bold text-gray-500 uppercase shrink-0 hidden sm:inline-block">CVD</span>
                      <div class="h-1 flex-1 bg-[#0d131f] rounded-full overflow-hidden flex items-center relative border border-kalshi-border">
                        <div id="cvdGaugeFillSaaS" class="h-full bg-kalshi-blue transition-all duration-300" style="width: 50%;"></div>
                        <div class="absolute w-[1px] h-full bg-gray-600 left-1/2"></div>
                      </div>
                    </div>"""
html = html.replace(old_cvd, new_cvd)

# Fix 2: Inject Matrix Telemetry
old_actions = """            <div class="px-3 pb-3 grid grid-cols-2 gap-2">
                <button onclick="forceMLTrade()" class="py-1.5 border border-purple-500/40 text-purple-400 font-bold text-[9px] uppercase tracking-widest rounded-lg transition-all active:scale-95 bg-purple-600/15 hover:bg-purple-600/25">FORCE AI</button>
                <button onclick="closeAllTrades()" class="py-1.5 bg-red-600/15 hover:bg-red-600/25 border border-red-500/40 text-white font-bold text-[9px] uppercase tracking-widest rounded-lg transition-all active:scale-95">CLOSE ALL</button>
            </div>
        </div>"""
new_actions = """            <div class="px-3 pb-3 grid grid-cols-2 gap-2">
                <button onclick="forceMLTrade()" class="py-1.5 border border-purple-500/40 text-purple-400 font-bold text-[9px] uppercase tracking-widest rounded-lg transition-all active:scale-95 bg-purple-600/15 hover:bg-purple-600/25">FORCE AI</button>
                <button onclick="closeAllTrades()" class="py-1.5 bg-red-600/15 hover:bg-red-600/25 border border-red-500/40 text-white font-bold text-[9px] uppercase tracking-widest rounded-lg transition-all active:scale-95">CLOSE ALL</button>
            </div>

            <!-- Matrix Telemetry Feed -->
            <div class="mx-3 mb-3 p-2 rounded-lg bg-black/80 border border-kalshi-blue/30 shadow-inner font-mono text-[9px] overflow-hidden relative">
              <div class="absolute top-0 left-0 w-full h-full bg-gradient-to-b from-transparent to-black/90 pointer-events-none z-10"></div>
              <div class="flex items-center justify-between mb-1 opacity-80 z-20 relative">
                 <div class="flex items-center gap-1.5">
                   <span class="w-1 h-1 rounded-full bg-kalshi-blue animate-ping"></span>
                   <span class="uppercase font-bold tracking-widest text-kalshi-blue">Live AI Telemetry</span>
                 </div>
              </div>
              <div id="matrixTelemetryConsoleSaaS" class="h-[3.5rem] overflow-hidden flex flex-col justify-end opacity-90 text-gray-300 z-0 relative">
                <div class="truncate opacity-50">> <span class="text-emerald-400">SYS:</span> Awaiting model forecasts...</div>
              </div>
            </div>
        </div>"""
if old_actions in html:
    html = html.replace(old_actions, new_actions)
    print("Matrix telemetry successfully injected.")
else:
    print("Could not find quick actions div!")

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
