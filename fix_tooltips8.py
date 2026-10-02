import re

fpath = 'static/index.html'
with open(fpath, 'r', encoding='utf-8') as f:
    text = f.read()

# Fix the already broken ones first
text = text.replace(
    'onclick="toggleAdminGlassInfo(\\\'model_training\\\', event)"',
    'onclick="toggleAdminGlassInfo(\'model_training\', event)"'
)
text = text.replace(
    'onclick="toggleAdminGlassInfo(\\\'signal_isolation\\\', event)"',
    'onclick="toggleAdminGlassInfo(\'signal_isolation\', event)"'
)
text = text.replace(
    'onclick="toggleAdminGlassInfo(\\\'exec_timing\\\', event)"',
    'onclick="toggleAdminGlassInfo(\'exec_timing\', event)"'
)
text = text.replace(
    'onclick="toggleAdminGlassInfo(\\\'log_debug\\\', event)"',
    'onclick="toggleAdminGlassInfo(\'log_debug\', event)"'
)

# Now do Risk Management
text = re.sub(
    r'<span class="text-slate-300 font-sans font-bold flex items-center gap-1">\s*<span>[^<]*</span>\s*Risk Management\s*</span>',
    r'<span class="text-slate-300 font-sans font-bold flex items-center gap-1 cursor-pointer group" onclick="toggleAdminGlassInfo(\'risk_position\', event)">\n                      <span>🛡️</span> Risk Management\n                      <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-blue-500/20 border border-white/10 flex items-center justify-center text-[9px] font-bold text-gray-400 transition-all ml-1">i</span>\n                    </span>',
    text
)

# Now do Confidence Filters
text = re.sub(
    r'<span class="text-slate-300 font-sans font-bold flex items-center gap-1">\s*<span>[^<]*</span>\s*Confidence Filters\s*</span>',
    r'<span class="text-slate-300 font-sans font-bold flex items-center gap-1 cursor-pointer group" onclick="toggleAdminGlassInfo(\'pred_confidence\', event)">\n                        <span>🎯</span> Confidence Filters\n                        <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-blue-500/20 border border-white/10 flex items-center justify-center text-[9px] font-bold text-gray-400 transition-all ml-1">i</span>\n                      </span>',
    text
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(text)
