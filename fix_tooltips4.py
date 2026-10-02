import re
fpath = 'static/js/admin_users.js'
with open(fpath, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace Autonomous Execution Toggles
text = re.sub(
    r'<span class="flex items-center gap-1.5 text-cyan-400">\s*<span>[^<]*</span>\s*Autonomous Execution Toggles\s*</span>',
    r'<span class="flex items-center gap-1.5 text-cyan-400 cursor-pointer group" onclick="toggleAdminGlassInfo(\'auto_trader\', event)">\n                <span>⚡</span> Autonomous Execution Toggles\n                <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-cyan-500/20 border border-white/10 flex items-center justify-center text-[9px] font-bold text-gray-400 transition-all ml-1">i</span>\n              </span>',
    text
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(text)
