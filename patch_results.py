import re

with open('static/js/dashboard.js', 'r', encoding='utf-8') as f:
    js = f.read()

target = """                                        <div class="flex flex-col gap-1.5 pr-20">
                                            <div class="flex items-center gap-2">
                                                <span class="text-[10px] font-bold text-white">Size $${sizeAmount}</span>
                                                <span class="text-[10px] font-black ${dirColor}">${dir}</span>
                                            </div>"""

replacement = """
                            let resultRow = "";
                            if (t.status !== "OPEN") {
                                let resText = "N/A";
                                let resColor = "text-gray-500";
                                if (t.official_result === "YES") {
                                    resText = "YES ABOVE";
                                    resColor = "text-emerald-400";
                                } else if (t.official_result === "NO") {
                                    resText = "NO BELOW";
                                    resColor = "text-rose-400";
                                } else if (t.exit_reason) {
                                    resText = "CLOSED EARLY";
                                    resColor = "text-amber-400";
                                }
                                resultRow = `
                                <div class="flex items-center gap-1.5 mt-0.5 mb-1">
                                    <span class="text-[9px] font-bold text-gray-500 uppercase">Result</span>
                                    <span class="text-[9px] font-black ${resColor}">${resText}</span>
                                </div>`;
                            } else {
                                resultRow = `
                                <div class="flex items-center gap-1.5 mt-0.5 mb-1">
                                    <span class="text-[9px] font-bold text-gray-500 uppercase">Result</span>
                                    <span class="text-[9px] font-black text-amber-500 animate-pulse">PENDING...</span>
                                </div>`;
                            }

"""
replacement += """                                        <div class="flex flex-col gap-1.5 pr-20">
                                            <div class="flex items-center gap-2">
                                                <span class="text-[10px] font-bold text-white">Size $${sizeAmount}</span>
                                                <span class="text-[10px] font-black ${dirColor}">${dir}</span>
                                            </div>
                                            ${resultRow}"""

if target in js:
    js = js.replace(target, replacement)
    
    # We must also bump the signature otherwise UI won't rerender the trades!
    sig_target = """const tradesSig = recent.map(t => `${t.id}_${t.status}_${t.status === 'OPEN' ? 'OPEN' : (t.pnl_dollars !== undefined ? t.pnl_dollars : (t.pnl || 0))}_${t.trading_style || ''}_${t.signal_source || ''}_${t.time || ''}`).join('|');"""
    sig_repl = """const tradesSig = recent.map(t => `${t.id}_${t.status}_${t.official_result || 'none'}_${t.status === 'OPEN' ? 'OPEN' : (t.pnl_dollars !== undefined ? t.pnl_dollars : (t.pnl || 0))}_${t.trading_style || ''}_${t.signal_source || ''}_${t.time || ''}`).join('|');"""
    js = js.replace(sig_target, sig_repl)
    
    with open('static/js/dashboard.js', 'w', encoding='utf-8') as f:
        f.write(js)
    print("dashboard.js patched successfully.")
else:
    print("Could not find target in dashboard.js")
