fpath = 'static/js/admin_users.js'
with open(fpath, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    '<span class="flex items-center gap-1.5 text-purple-400">\n                <span>🧠</span> AI Model & Reinforcement Learning\n              </span>',
    '<span class="flex items-center gap-1.5 text-purple-400 cursor-pointer group" onclick="toggleAdminGlassInfo(\'ai_model\', event)">\n                <span>🧠</span> AI Model & Reinforcement Learning\n                <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-purple-500/20 border border-white/10 flex items-center justify-center text-[9px] font-bold text-gray-400 transition-all ml-1">i</span>\n              </span>'
)

text = text.replace(
    '<span class="flex items-center gap-1.5 text-cyan-400">\n                <span>⚡</span> Autonomous Execution Toggles\n              </span>',
    '<span class="flex items-center gap-1.5 text-cyan-400 cursor-pointer group" onclick="toggleAdminGlassInfo(\'auto_trader\', event)">\n                <span>⚡</span> Autonomous Execution Toggles\n                <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-cyan-500/20 border border-white/10 flex items-center justify-center text-[9px] font-bold text-gray-400 transition-all ml-1">i</span>\n              </span>'
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(text)
