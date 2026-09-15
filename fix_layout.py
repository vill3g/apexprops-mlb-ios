import sys

with open('static/index.html', 'r', encoding='utf-8') as f:
    c = f.read()

b = """              <div class="flex items-center justify-between px-1.5 py-1 text-[9px] sm:text-[10px] border-t border-slate-800/60 text-slate-400 shrink-0">
                <div>Trades: <span id="kalshiTradesCount" class="font-bold text-white">0W - 0L</span> (<span id="kalshiWinRate" class="font-bold text-emerald-400">0%</span>)</div>
                <div>P&L: <span id="kalshiTotalPnl" class="font-bold text-white">$0.00</span></div>
                  </div>
                </div>
                <div id="kalshiTradesListContainer" class="space-y-1 flex-1 h-full overflow-y-auto pr-0.5 text-[9px] sm:text-[10px]">
                  <div class="text-[9px] text-slate-500 text-center py-2">Standing by for next 15M contract rollover...</div>
                </div>
              </div>

            </div>"""

f = """              <div class="flex items-center justify-between px-1.5 py-1 text-[9px] sm:text-[10px] border-t border-slate-800/60 text-slate-400 shrink-0">
                <div>Trades: <span id="kalshiTradesCount" class="font-bold text-white">0W - 0L</span> (<span id="kalshiWinRate" class="font-bold text-emerald-400">0%</span>)</div>
                <div>P&L: <span id="kalshiTotalPnl" class="font-bold text-white">$0.00</span></div>
              </div>

              <!-- Recent Trades Stream (Allocated 40% of Left Panel Height) -->
              <div class="flex flex-col flex-1 min-h-0 border-t border-slate-800/80 pt-1" style="height: 40%; min-height: 40%; max-height: 40%;">
                <div class="flex flex-col gap-0.5 pb-1 mb-1 text-[8px] sm:text-[9px] text-slate-400 font-bold uppercase tracking-wider shrink-0 border-b border-slate-800">
                  <div class="flex items-center justify-between">
                    <span>AI Trades</span>
                    <span class="text-cyan-400 text-[8px]">Live History</span>
                  </div>
                  <div class="flex items-center justify-between text-[7.5px] mt-0.5">
                    <span>Bal: <span id="tradeLogPaperBalance" class="text-white">$0.00</span></span>
                    <span>Risk: <span class="text-emerald-400">$25 Max</span></span>
                    <span>TP: <span class="text-emerald-400">+50%</span></span>
                  </div>
                </div>
                <div id="kalshiTradesListContainer" class="space-y-1 flex-1 h-full overflow-y-auto pr-0.5 text-[9px] sm:text-[10px]">
                  <div class="text-[9px] text-slate-500 text-center py-2">Standing by for next 15M contract rollover...</div>
                </div>
              </div>

            </div>"""

if b in c:
    c = c.replace(b, f)
    with open('static/index.html', 'w', encoding='utf-8') as file:
        file.write(c)
    print('Fixed!')
else:
    # Try normalizing newlines just in case
    b_norm = b.replace('\r\n', '\n')
    c_norm = c.replace('\r\n', '\n')
    if b_norm in c_norm:
        c_norm = c_norm.replace(b_norm, f.replace('\r\n', '\n'))
        with open('static/index.html', 'w', encoding='utf-8') as file:
            file.write(c_norm)
        print('Fixed with normalized newlines!')
    else:
        print('Block not found.')
