fpath = 'static/js/admin_users.js'
with open(fpath, 'r', encoding='utf-8') as f:
    text = f.read()

# Strategy & Signals
text = text.replace(
    '<span class="flex items-center gap-1.5 text-cyan-400">\n                <span>🎯</span> Strategy Archetype & Sizing\n              </span>',
    '<span class="flex items-center gap-1.5 text-cyan-400 cursor-pointer group" onclick="toggleAdminGlassInfo(\'strategy\', event)">\n                <span>🎯</span> Strategy Archetype & Sizing\n                <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-cyan-500/20 border border-white/10 flex items-center justify-center text-[9px] font-bold text-gray-400 transition-all ml-1">i</span>\n              </span>'
)

# Technical Confluence (We need to check where this is)
# Let's verify where Technical Confluence is or if it's Section 4.
with open('fix2.py', 'w') as f:
    f.write('done')
