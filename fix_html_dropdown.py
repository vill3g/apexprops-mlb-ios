import re

html_path = "static/saas_dashboard.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Change onclick and add id to profile trigger
pattern = r'<div class="flex items-center gap-2 cursor-pointer group active:scale-95 transition-transform" onclick="openSocialModal\(\)" title="View Your Stats">'
replace = r'<div id="profile-trigger-area" class="flex items-center gap-2 cursor-pointer group active:scale-95 transition-transform" onclick="toggleProfileMenu()" title="View Your Stats">'
html = re.sub(pattern, replace, html)

# Add dropdown HTML right after the header ends, or inside the body. Let's add it right after <header> starts so it's sticky.
dropdown_html = """
    <!-- Glassy Profile Dropdown Menu -->
    <div id="profileDropdown" class="hidden absolute top-12 left-3 z-[100] w-60 bg-[#0d131f]/95 backdrop-blur-2xl border border-kalshi-border/50 rounded-2xl shadow-[0_16px_50px_rgba(0,0,0,0.8)] overflow-hidden origin-top-left transform transition-all duration-300 scale-90 opacity-0 translate-x-[-10px] translate-y-[-10px]">
        <div class="p-4 border-b border-kalshi-border/30 bg-gradient-to-br from-cyan-900/30 to-transparent">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-full border border-cyan-500/30 overflow-hidden shrink-0 shadow-[0_0_10px_rgba(6,182,212,0.3)]">
                    <img id="dropdown-avatar" src="/static/ai_avatar.gif" class="w-full h-full object-cover">
                </div>
                <div>
                    <div id="dropdown-username" class="text-xs font-black text-white uppercase tracking-wider truncate max-w-[120px]">Trader</div>
                    <div class="flex items-center gap-1.5 mt-0.5">
                        <span id="dropdown-mode-badge" class="px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 text-[9px] font-bold uppercase tracking-widest">PAPER</span>
                        <span class="text-[8px] text-gray-500 font-bold uppercase tracking-widest">Mode</span>
                    </div>
                </div>
            </div>
        </div>
        <div class="p-4 grid grid-cols-2 gap-4">
            <div>
                <div class="text-[9px] text-gray-500 font-bold uppercase tracking-widest mb-1">Win Rate</div>
                <div id="dropdown-winrate" class="text-sm font-black text-white tabular-nums">--%</div>
                <div class="text-[9px] font-mono mt-0.5 tracking-wider"><span id="dropdown-wins" class="text-emerald-400">0W</span> <span class="text-gray-600">-</span> <span id="dropdown-losses" class="text-rose-400">0L</span></div>
            </div>
            <div>
                <div class="text-[9px] text-gray-500 font-bold uppercase tracking-widest mb-1">Net PnL</div>
                <div id="dropdown-pnl" class="text-sm font-black tabular-nums text-emerald-400 truncate">$--.--</div>
                <div id="dropdown-pnl-pct" class="text-[9px] font-bold font-mono text-emerald-500 mt-0.5">(--%)</div>
            </div>
        </div>
    </div>
"""

header_pattern = r'(<header[^>]*>)'
html = re.sub(header_pattern, r'\1\n' + dropdown_html, html)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Updated HTML for glassy dropdown!")
