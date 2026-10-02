import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Inject CVD Gauge into the Active Market Panel Header
cvd_html = """                <div class="flex items-center gap-1">
                    <span id="kalshi-market-ticker" class="text-[10px] font-mono font-bold text-gray-400 uppercase tracking-wider tabular-nums truncate max-w-[170px] sm:max-w-none" title="Active Kalshi Contract">--</span>
                </div>
            </div>"""
cvd_injected = """                <div class="flex items-center gap-2">
                    <div class="hidden sm:flex items-center gap-1 bg-black/60 border border-kalshi-border/50 rounded-full px-2 py-0.5 h-5 w-20">
                      <span class="text-[7px] font-bold text-gray-500 uppercase shrink-0">CVD</span>
                      <div class="h-1 flex-1 bg-[#0d131f] rounded-full overflow-hidden flex items-center relative border border-kalshi-border">
                        <div id="cvdGaugeFillSaaS" class="h-full bg-kalshi-blue transition-all duration-300" style="width: 50%;"></div>
                        <div class="absolute w-[1px] h-full bg-gray-600 left-1/2"></div>
                      </div>
                    </div>
                    <span id="kalshi-market-ticker" class="text-[10px] font-mono font-bold text-gray-400 uppercase tracking-wider tabular-nums truncate max-w-[170px] sm:max-w-none" title="Active Kalshi Contract">--</span>
                </div>
            </div>"""
html = html.replace(cvd_html, cvd_injected)

# 2. Inject Matrix Telemetry below the YES/NO buttons
# Look for the closing div of the grid grid-cols-2 gap-3
telemetry_html = """                        </div>
                    </div>
                </button>
            </div>
        </div>"""
telemetry_injected = """                        </div>
                    </div>
                </button>
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
html = html.replace(telemetry_html, telemetry_injected)

# 3. Inject PnL Heatmap into Settings Tab
# Place it right above the "Signal Source" dropdown
heatmap_target = """                <div>
                  <label class="block text-[9px] font-mono uppercase text-slate-400 mb-1">Signal Source</label>"""
heatmap_injected = """
                <!-- Strategy Heatmap -->
                <div class="col-span-1 sm:col-span-2 lg:col-span-3 bg-black/40 border border-kalshi-border/60 rounded-xl p-3 mb-1">
                  <label class="block text-[9px] font-mono uppercase text-slate-400 mb-2">📊 Strategy Performance</label>
                  <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 text-[9px] sm:text-[10px] font-mono">
                    <div class="flex flex-col gap-1">
                      <div class="flex justify-between"><span class="text-gray-400">SNIPER</span><span class="text-emerald-400 font-bold">78%</span></div>
                      <div class="h-1 bg-gray-800 rounded-full flex overflow-hidden"><div class="h-full bg-emerald-500 w-[78%]"></div><div class="h-full bg-red-500/80 w-[22%]"></div></div>
                    </div>
                    <div class="flex flex-col gap-1">
                      <div class="flex justify-between"><span class="text-gray-400">AMBUSH</span><span class="text-emerald-400 font-bold">65%</span></div>
                      <div class="h-1 bg-gray-800 rounded-full flex overflow-hidden"><div class="h-full bg-emerald-500 w-[65%]"></div><div class="h-full bg-red-500/80 w-[35%]"></div></div>
                    </div>
                    <div class="flex flex-col gap-1">
                      <div class="flex justify-between"><span class="text-gray-400">CHOP</span><span class="text-emerald-400 font-bold">82%</span></div>
                      <div class="h-1 bg-gray-800 rounded-full flex overflow-hidden"><div class="h-full bg-emerald-500 w-[82%]"></div><div class="h-full bg-red-500/80 w-[18%]"></div></div>
                    </div>
                    <div class="flex flex-col gap-1">
                      <div class="flex justify-between"><span class="text-gray-400">MOMENTUM</span><span class="text-emerald-400 font-bold">71%</span></div>
                      <div class="h-1 bg-gray-800 rounded-full flex overflow-hidden"><div class="h-full bg-emerald-500 w-[71%]"></div><div class="h-full bg-red-500/80 w-[29%]"></div></div>
                    </div>
                  </div>
                </div>

                <div>
                  <label class="block text-[9px] font-mono uppercase text-slate-400 mb-1">Signal Source</label>"""
html = html.replace(heatmap_target, heatmap_injected)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("saas_dashboard.html patched with new UI widgets.")
