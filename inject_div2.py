with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re

div = '''
                    <div class="flex items-center justify-between px-1.5 py-1 rounded-lg bg-slate-900 border border-slate-800">
                      <span class="text-slate-300 cursor-help" title="Select trading style and speed">Trading Style</span>
                      <select id="settingTradingStyle" title="Select trading speed/style" class="bg-slate-950 border border-slate-700 rounded px-1 text-cyan-300 focus:outline-none cursor-pointer">
                            <option value="AUTO" selected>\uD83E\uDD16 AUTO (Adaptive)</option>
                            <option value="SNIPER">\uD83C\uDFAF Sniper (15m)</option>
                            <option value="MACHINE_GUN">\uD83D\uDD2B Machine Gun (1m)</option>
                            <option value="CHOP">\u2696\uFE0F Chop Engine (Low Vol)</option>
                      </select>
                    </div>
'''

text = re.sub(r'(<div class="flex items-center justify-between px-1\.5 py-1 rounded-lg bg-slate-900 border border-slate-800">\s*<span class="text-slate-300 cursor-help" title="Select which ML model)', div + r'\1', text)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(text)
