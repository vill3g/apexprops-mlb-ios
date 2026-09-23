with open("static/trades.html", "r", encoding="utf-8") as f:
    html = f.read()

idx_start = html.find("function getTradeIdentifierPills(t) {")
idx_end = html.find("return pills.join(\" \");\n    }", idx_start)
if idx_start != -1 and idx_end != -1:
    idx_end += len("return pills.join(\" \");\n    }")
    replacement = '''function getTradeIdentifierPills(t) {
      const pills = [];
      const mode = String(t.mode || "PAPER").toUpperCase();
      const src = String(t.trade_source || "").toUpperCase();
      const rec = String(t.recommendation || "").toUpperCase();
      const grade = String(t.conviction_grade || "").toUpperCase();
      const badge = String(t.conviction_badge || "").toUpperCase();
      const exitReason = String(t.exit_reason || t.reason || "").toUpperCase();
      const catalysts = Array.isArray(t.catalysts) ? t.catalysts.map(c => String(c).toUpperCase()) : [];

      if (mode === "LIVE") {
        pills.push(<span class="text-[8px] font-black px-1.5 py-0.2 rounded uppercase bg-red-500/20 text-red-300 border border-red-500/40 shadow-sm shadow-red-950/40" title="Real Money Live Order">LIVE</span>);
      } else {
        pills.push(<span class="text-[8px] font-bold px-1.5 py-0.2 rounded uppercase bg-cyan-500/20 text-cyan-300 border border-cyan-500/40" title="Simulated Paper Order">PAPER</span>);
      }

      const isManual = t.is_manual === true || src.includes("MANUAL") || rec.includes("MANUAL") || grade.includes("MANUAL") || exitReason === "MANUAL";
      if (isManual) {
        pills.push(<span class="text-[8px] font-bold px-1.5 py-0.2 rounded uppercase bg-amber-500/15 text-amber-300 border border-amber-500/35" title="Manually Executed by Trader">MANUAL</span>);
      } else {
        const styleStr = t.trading_style ? String(t.trading_style).replace(/_/g, ' ') : "AUTO";
        pills.push(<span class="text-[8px] font-bold px-1.5 py-0.2 rounded uppercase bg-blue-500/20 text-blue-300 border border-blue-500/35" title="Autonomous AI Execution"></span>);
      }

      if (t.is_profit_reentry) {
        pills.push(<span class="text-[8px] font-bold px-1.5 py-0.2 rounded uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/35">2ND ENTRY</span>);
      }
      if (t.is_reversal || t.is_reverse) {
        pills.push(<span class="text-[8px] font-bold px-1.5 py-0.2 rounded uppercase bg-amber-500/20 text-amber-400 border border-amber-500/35">REVERSAL</span>);
      }

      if (exitReason && exitReason !== 'KALSHI_POSITION_RECONCILED' && exitReason !== 'AI_SIGNAL' && exitReason !== 'SETTLEMENT' && !isManual) {
        let exitStr = exitReason.replace(/_/g, ' ');
        let exitColor = 'bg-slate-500/20 text-slate-400 border-slate-500/35';
        if (exitStr.includes('PROFIT') || exitStr.includes('TP')) exitColor = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/35';
        else if (exitStr.includes('STOP LOSS') || exitStr.includes('STOP_LOSS') || exitStr.includes('SL') || exitStr.includes('STOP')) exitColor = 'bg-red-500/20 text-red-400 border-red-500/35';
        pills.push(<span class="text-[8px] font-bold px-1.5 py-0.2 rounded uppercase border "></span>);
      }

      return pills.join(" ");
    }'''
    new_html = html[:idx_start] + replacement + html[idx_end:]
    with open("static/trades.html", "w", encoding="utf-8") as f:
        f.write(new_html)
    print("Success")
else:
    print("Indices not found", idx_start, idx_end)
