import re

fpath = 'static/index.html'
with open(fpath, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace Section A
text = re.sub(
    r'<span class="text-slate-300 font-sans font-bold flex items-center gap-1">\s*<span>[^<]*</span>\s*Model & Training Controls\s*</span>',
    r'<span class="text-slate-300 font-sans font-bold flex items-center gap-1 cursor-pointer group" onclick="toggleAdminGlassInfo(\'model_training\', event)">\n                      <span>🧠</span> Model & Training Controls\n                      <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-blue-500/20 border border-white/10 flex items-center justify-center text-[9px] font-bold text-gray-400 transition-all ml-1">i</span>\n                    </span>',
    text
)

# Replace Section A2
text = re.sub(
    r'<span class="text-slate-300 font-sans font-bold flex items-center gap-1">\s*<span>[^<]*</span>\s*Trade Signal Isolation\s*</span>',
    r'<span class="text-slate-300 font-sans font-bold flex items-center gap-1 cursor-pointer group" onclick="toggleAdminGlassInfo(\'signal_isolation\', event)">\n                      <span>🎛️</span> Trade Signal Isolation\n                      <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-blue-500/20 border border-white/10 flex items-center justify-center text-[9px] font-bold text-gray-400 transition-all ml-1">i</span>\n                    </span>',
    text
)

# Replace Section B
text = re.sub(
    r'<span class="text-slate-300 font-sans font-bold flex items-center gap-1">\s*<span>[^<]*</span>\s*Risk & Position Management\s*</span>',
    r'<span class="text-slate-300 font-sans font-bold flex items-center gap-1 cursor-pointer group" onclick="toggleAdminGlassInfo(\'risk_position\', event)">\n                      <span>🛡️</span> Risk & Position Management\n                      <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-blue-500/20 border border-white/10 flex items-center justify-center text-[9px] font-bold text-gray-400 transition-all ml-1">i</span>\n                    </span>',
    text
)

# Replace Section C
text = re.sub(
    r'<span class="text-slate-300 font-sans font-bold flex items-center gap-1">\s*<span>[^<]*</span>\s*Prediction Confidence Filters\s*</span>',
    r'<span class="text-slate-300 font-sans font-bold flex items-center gap-1 cursor-pointer group" onclick="toggleAdminGlassInfo(\'pred_confidence\', event)">\n                      <span>🎯</span> Prediction Confidence Filters\n                      <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-blue-500/20 border border-white/10 flex items-center justify-center text-[9px] font-bold text-gray-400 transition-all ml-1">i</span>\n                    </span>',
    text
)

# Replace Section C2
text = re.sub(
    r'<span class="text-slate-300 font-sans font-bold flex items-center gap-1">\s*<span>[^<]*</span>\s*Execution & Timing\s*</span>',
    r'<span class="text-slate-300 font-sans font-bold flex items-center gap-1 cursor-pointer group" onclick="toggleAdminGlassInfo(\'exec_timing\', event)">\n                      <span>⏱️</span> Execution & Timing\n                      <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-blue-500/20 border border-white/10 flex items-center justify-center text-[9px] font-bold text-gray-400 transition-all ml-1">i</span>\n                    </span>',
    text
)

# Replace Section C3
text = re.sub(
    r'<span class="text-slate-300 font-sans font-bold flex items-center gap-1">\s*<span>[^<]*</span>\s*Logging & Debugging\s*</span>',
    r'<span class="text-slate-300 font-sans font-bold flex items-center gap-1 cursor-pointer group" onclick="toggleAdminGlassInfo(\'log_debug\', event)">\n                      <span>🐛</span> Logging & Debugging\n                      <span class="w-4 h-4 rounded-full bg-white/5 group-hover:bg-blue-500/20 border border-white/10 flex items-center justify-center text-[9px] font-bold text-gray-400 transition-all ml-1">i</span>\n                    </span>',
    text
)


with open(fpath, 'w', encoding='utf-8') as f:
    f.write(text)
