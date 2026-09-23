import re

with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
    html = f.read()

new_js = '''
                      const container = document.getElementById('tradesContainer');
                      const recent = (s.recent_trades || []).slice(0, 15);
                      if (recent.length === 0) {
                          container.innerHTML = '<div class="text-center py-6 text-[10px] text-gray-500 font-mono bg-[#131b2c] rounded-xl border border-kalshi-border">No recent trades found</div>';
                      } else {
                          let htmlString = '';
                          recent.forEach(t => {
                              const isWin = (t.status || "").toUpperCase().includes("WIN") || parseFloat(t.pnl_dollars || 0) > 0;
                              const isLoss = (t.status || "").toUpperCase().includes("LOSS") || parseFloat(t.pnl_dollars || 0) < 0;
                              
                              let borderClass = "border-l-2 border-l-kalshi-blue";
                              let statusBadge = '<span class="text-[9px] font-bold text-kalshi-blue">OPEN</span>';
                              
                              if (t.status === 'OPEN') {
                                  statusBadge = 
                                      <div class="flex items-center gap-1">
                                          <span class="text-[9px] font-bold text-yellow-400 animate-pulse">OPEN</span>
                                          <button onclick="closeTrade('')" class="px-1.5 py-0.5 bg-red-600/20 text-red-500 rounded text-[8px] font-bold border border-red-500/30 transition-colors">CLOSE</button>
                                      </div>
                                  ;
                              } else if (isWin) {
                                  borderClass = "border-l-2 border-l-emerald-500";
                                  statusBadge = '<span class="text-[9px] font-bold text-emerald-400">WIN</span>';
                              } else if (isLoss) {
                                  borderClass = "border-l-2 border-l-red-500";
                                  statusBadge = '<span class="text-[9px] font-bold text-red-400">LOSS</span>';
                              } else {
                                  borderClass = "border-l-2 border-l-gray-500";
                                  statusBadge = '<span class="text-[9px] font-bold text-gray-400">CLOSED</span>';
                              }

                              const pnlVal = parseFloat(t.pnl_dollars || 0);
                              const pnlColor = pnlVal > 0 ? "text-emerald-400" : (pnlVal < 0 ? "text-red-400" : "text-gray-400");
                              const pnlStr = pnlVal > 0 ? "+$" + pnlVal.toFixed(2) : (pnlVal < 0 ? "-$" + Math.abs(pnlVal).toFixed(2) : ".00");

                              const dir = String(t.side || "").toUpperCase();
                              const dirColor = dir === "YES" ? "text-kalshi-green" : "text-kalshi-red";

                              let badges = [];
                              const mode = String(t.mode || "PAPER").toUpperCase();
                              if (mode === "LIVE") {
                                  badges.push('<span class="text-[8px] font-black px-1.5 py-0.5 rounded uppercase bg-red-500/20 text-red-300 border border-red-500/40">LIVE</span>');
                              } else {
                                  badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">PAPER</span>');
                              }

                              const exitReason = String(t.exit_reason || t.reason || "").toUpperCase();
                              const isManual = t.is_manual === true || exitReason === "MANUAL" || exitReason === "MANUAL_CLOSE";

                              if (isManual) {
                                  badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-amber-500/15 text-amber-300 border border-amber-500/35">MANUAL</span>');
                              } else {
                                  const styleStr = t.trading_style ? String(t.trading_style).replace(/_/g, ' ') : "AUTO";
                                  badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-blue-500/20 text-blue-300 border border-blue-500/35">' + styleStr + '</span>');
                              }
                              
                              if (t.is_profit_reentry) {
                                  badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/35">2ND ENTRY</span>');
                              }
                              if (t.is_reversal || t.is_reverse) {
                                  badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-purple-500/20 text-purple-400 border border-purple-500/35">REVERSAL</span>');
                              }

                              if (exitReason && exitReason !== 'KALSHI_POSITION_RECONCILED' && exitReason !== 'AI_SIGNAL' && exitReason !== 'SETTLEMENT' && !isManual) {
                                  let exitStr = exitReason.replace(/_/g, ' ');
                                  let exitColor = 'bg-slate-500/20 text-slate-400 border-slate-500/35';
                                  if (exitStr.includes('PROFIT') || exitStr.includes('TP')) exitColor = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/35';
                                  else if (exitStr.includes('STOP LOSS') || exitStr.includes('STOP_LOSS') || exitStr.includes('SL') || exitStr.includes('STOP')) exitColor = 'bg-red-500/20 text-red-400 border-red-500/35';
                                  badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase border ' + exitColor + '">' + exitStr + '</span>');
                              }

                              htmlString += 
                                  <div class="bg-[#131b2c] rounded-xl p-2.5 shadow-sm border border-kalshi-border  flex flex-col gap-1.5">
                                      <div class="flex justify-between items-center">
                                          <div class="flex items-center gap-2">
                                              <span class="text-[10px] font-bold text-white"></span>
                                              <span class="text-[10px] font-black "></span>
                                          </div>
                                          <div class="flex items-center gap-2">
                                              
                                              <span class="text-[11px] font-mono font-bold "></span>
                                          </div>
                                      </div>
                                      <div class="flex justify-between items-center text-[9px] text-gray-500">
                                          <span></span>
                                          <span> Cont. @ {(t.entry_price || 0).toFixed(2)}</span>
                                      </div>
                                      <div class="flex flex-wrap gap-1 mt-0.5">
                                          
                                      </div>
                                  </div>
                              ;
                          });
                          container.innerHTML = htmlString;
                      }
'''

# The previous block was:
# const tbody = document.getElementById('trades-body');
# ...
# tbody.innerHTML = htmlString;
# }

html = re.sub(
    r"const tbody = document\.getElementById\('trades-body'\);.*?tbody\.innerHTML = htmlString;\s*\}",
    new_js,
    html,
    flags=re.DOTALL
)

with open("static/saas_dashboard.html", "w", encoding="utf-8") as f:
    f.write(html)
