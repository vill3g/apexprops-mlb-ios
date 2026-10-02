import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: ADD button
# The exact target to replace is inside the `if (t.status === 'OPEN') {` block.
target_open_block = """                                if (pnlVal > 0) {
                                    statusBadge = `
                                        <div class="flex items-center gap-1">
                                            <span class="text-[9px] font-bold text-yellow-400 animate-pulse">OPEN</span>
                                            <button onclick="event.stopPropagation(); takeProfitTrade('${t.id}')" class="px-1.5 py-0.5 bg-emerald-600/25 text-emerald-400 hover:bg-emerald-600/40 rounded text-[8px] font-bold border border-emerald-500/40 transition-all flex items-center gap-0.5 cursor-pointer"><span>🎯</span> TAKE PROFIT</button>
                                            <button onclick="event.stopPropagation(); closeTrade('${t.id}')" class="px-1.5 py-0.5 bg-red-600/20 text-red-500 hover:bg-red-600/30 rounded text-[8px] font-bold border border-red-500/30 transition-colors cursor-pointer">CLOSE</button>
                                        </div>
                                    `;
                                } else {
                                    statusBadge = `
                                        <div class="flex items-center gap-1">
                                            <span class="text-[9px] font-bold text-yellow-400 animate-pulse">OPEN</span>
                                            <button onclick="event.stopPropagation(); closeTrade('${t.id}')" class="px-1.5 py-0.5 bg-red-600/20 text-red-500 hover:bg-red-600/30 rounded text-[8px] font-bold border border-red-500/30 transition-colors cursor-pointer">CLOSE</button>
                                        </div>
                                    `;
                                }"""

new_open_block = """                                if (pnlVal > 0) {
                                    statusBadge = `
                                        <div class="flex items-center gap-1">
                                            <span class="text-[9px] font-bold text-yellow-400 animate-pulse">OPEN</span>
                                            <button onclick="event.stopPropagation(); executeManualTrade('${t.side}', '${t.asset || ''}')" class="px-1.5 py-0.5 bg-blue-600/25 text-blue-400 hover:bg-blue-600/40 rounded text-[8px] font-bold border border-blue-500/40 transition-all flex items-center gap-0.5 cursor-pointer"><span>&#10133;</span> ADD</button>
                                            <button onclick="event.stopPropagation(); takeProfitTrade('${t.id}')" class="px-1.5 py-0.5 bg-emerald-600/25 text-emerald-400 hover:bg-emerald-600/40 rounded text-[8px] font-bold border border-emerald-500/40 transition-all flex items-center gap-0.5 cursor-pointer"><span>&#127919;</span> TAKE PROFIT</button>
                                            <button onclick="event.stopPropagation(); closeTrade('${t.id}')" class="px-1.5 py-0.5 bg-red-600/20 text-red-500 hover:bg-red-600/30 rounded text-[8px] font-bold border border-red-500/30 transition-colors cursor-pointer">CLOSE</button>
                                        </div>
                                    `;
                                } else {
                                    statusBadge = `
                                        <div class="flex items-center gap-1">
                                            <span class="text-[9px] font-bold text-yellow-400 animate-pulse">OPEN</span>
                                            <button onclick="event.stopPropagation(); executeManualTrade('${t.side}', '${t.asset || ''}')" class="px-1.5 py-0.5 bg-blue-600/25 text-blue-400 hover:bg-blue-600/40 rounded text-[8px] font-bold border border-blue-500/40 transition-all flex items-center gap-0.5 cursor-pointer"><span>&#10133;</span> ADD</button>
                                            <button onclick="event.stopPropagation(); closeTrade('${t.id}')" class="px-1.5 py-0.5 bg-red-600/20 text-red-500 hover:bg-red-600/30 rounded text-[8px] font-bold border border-red-500/30 transition-colors cursor-pointer">CLOSE</button>
                                        </div>
                                    `;
                                }"""
if target_open_block in content:
    content = content.replace(target_open_block, new_open_block)
else:
    print("WARNING: Could not find target_open_block")

# Fix 2: Second entry badge duplication
target_badge_block = """                            if (isManual) {
                                badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-amber-500/15 text-amber-300 border border-amber-500/35">MANUAL</span>');
                            } else {
                                const styleStr = (t.trading_style && t.trading_style !== "REVERSAL") ? String(t.trading_style).replace(/_/g, ' ') : "🤖 AUTO";
                                badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-blue-500/20 text-blue-300 border border-blue-500/35">' + styleStr + '</span>');
                            }"""

new_badge_block = """                            if (isManual) {
                                badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-amber-500/15 text-amber-300 border border-amber-500/35">MANUAL</span>');
                            } else {
                                const styleStr = (t.trading_style && t.trading_style !== "REVERSAL") ? String(t.trading_style).replace(/_/g, ' ') : "AUTO";
                                // Suppress the blue AUTO/STYLE badge if it's a SECOND_ENTRY or THIRD_ENTRY, since those get their own dedicated purple/emerald reentry badges below.
                                if (t.trading_style !== "SECOND_ENTRY" && t.trading_style !== "THIRD_ENTRY" && t.trading_style !== "STOP_LOSS_REENTRY") {
                                    badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-blue-500/20 text-blue-300 border border-blue-500/35">&#129302; ' + styleStr + '</span>');
                                } else {
                                    // If we suppressed it, push a generic AUTO so it's not totally empty of model style
                                    badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-blue-500/20 text-blue-300 border border-blue-500/35">&#129302; AUTO</span>');
                                }
                            }"""
                            
if target_badge_block in content:
    content = content.replace(target_badge_block, new_badge_block)
else:
    # Try finding it with the robot emoji removed if it was mangled
    target_badge_block_mangled = """                            if (isManual) {
                                badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-amber-500/15 text-amber-300 border border-amber-500/35">MANUAL</span>');
                            } else {
                                const styleStr = (t.trading_style && t.trading_style !== "REVERSAL") ? String(t.trading_style).replace(/_/g, ' ') : " AUTO";
                                    badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-blue-500/20 text-blue-300 border border-blue-500/35">' + styleStr + '</span>');
                            }"""
    if target_badge_block_mangled in content:
        content = content.replace(target_badge_block_mangled, new_badge_block)
    else:
        # One more try with flexible spacing
        import re
        pattern = re.compile(r'if\s*\(isManual\)\s*\{\s*badges\.push\(\'<span.*?MANUAL</span>\'\);\s*\}\s*else\s*\{\s*const styleStr =.*?badges\.push\(\'<span.*?\' \+ styleStr \+ \'</span>\'\);\s*\}', re.DOTALL)
        if pattern.search(content):
            content = pattern.sub(new_badge_block, content)
        else:
            print("WARNING: Could not find target_badge_block")

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Success')
