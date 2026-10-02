import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

target = """                            } else {
                                const styleStr = (t.trading_style && t.trading_style !== "REVERSAL") ? String(t.trading_style).replace(/_/g, ' ') : "🤖 AUTO";
                                    badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-blue-500/20 text-blue-300 border border-blue-500/35">' + styleStr + '</span>');
                            }"""
                            
# Wait, let's just use re to be safe with emojis
pattern = re.compile(r'\} else \{\s*const styleStr = \(t\.trading_style && t\.trading_style !== "REVERSAL"\) \? String\(t\.trading_style\)\.replace\(/_/g, \' \'\) : "[^"]*AUTO";\s*badges\.push\(\'<span class="text-\[8px\] font-bold px-1\.5 py-0\.5 rounded uppercase bg-blue-500/20 text-blue-300 border border-blue-500/35">\' \+ styleStr \+ \'</span>\'\);\s*\}')

new_block = """} else {
                                const styleStr = (t.trading_style && t.trading_style !== "REVERSAL") ? String(t.trading_style).replace(/_/g, ' ') : "&#129302; AUTO";
                                if (t.trading_style !== "SECOND_ENTRY" && t.trading_style !== "THIRD_ENTRY" && t.trading_style !== "STOP_LOSS_REENTRY") {
                                    badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-blue-500/20 text-blue-300 border border-blue-500/35">' + styleStr + '</span>');
                                } else {
                                    badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-blue-500/20 text-blue-300 border border-blue-500/35">&#129302; AUTO</span>');
                                }
                            }"""

if pattern.search(content):
    content = pattern.sub(new_block, content)
    with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced badge block.")
else:
    print("Could not find badge block with regex.")
