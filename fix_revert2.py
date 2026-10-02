with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

target = """if (isManual) {
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

new_block = """if (isManual) {
                                badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-amber-500/15 text-amber-300 border border-amber-500/35">MANUAL</span>');
                            } else {
                                const styleStr = (t.trading_style && t.trading_style !== "REVERSAL") ? String(t.trading_style).replace(/_/g, ' ') : "🤖 AUTO";
                                badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-blue-500/20 text-blue-300 border border-blue-500/35">' + styleStr + '</span>');
                            }"""

if target in content:
    content = content.replace(target, new_block)
    with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Reverted to exact original!")
else:
    print("Could not find target!")
