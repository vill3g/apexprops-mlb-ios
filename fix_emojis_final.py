file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\dashboard.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

replaces = {
    '?? Loading Community': '? Loading Community',
    '?? <span class=\'text-blue-400': '?? <span class=\'text-blue-400',
    "?? ' + rawStyle": "?? ' + rawStyle",
    "?? ' + rawSource": "?? ' + rawSource",
    "from-amber-400 to-yellow-600 text-black flex items-center justify-center font-black text-xs shadow-[0_0_12px_rgba(251,191,36,0.5)]\">??</div>": "from-amber-400 to-yellow-600 text-black flex items-center justify-center font-black text-xs shadow-[0_0_12px_rgba(251,191,36,0.5)]\">??</div>",
    "from-slate-300 to-slate-500 text-black flex items-center justify-center font-black text-xs shadow-[0_0_10px_rgba(203,213,225,0.4)]\">??</div>": "from-slate-300 to-slate-500 text-black flex items-center justify-center font-black text-xs shadow-[0_0_10px_rgba(203,213,225,0.4)]\">??</div>",
    "from-amber-700 to-orange-800 text-white flex items-center justify-center font-black text-xs shadow-[0_0_10px_rgba(180,83,9,0.3)]\">??</div>": "from-amber-700 to-orange-800 text-white flex items-center justify-center font-black text-xs shadow-[0_0_10px_rgba(180,83,9,0.3)]\">??</div>"
}

for k, v in replaces.items():
    content = content.replace(k, v)

# One more for the spinner
content = content.replace('<span class="animate-spin text-cyan-400">??</span>', '<span class="animate-spin text-cyan-400">?</span>')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("dashboard.js final stragglers complete")
