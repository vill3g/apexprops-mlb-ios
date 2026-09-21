with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re

row = '''<tr class="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                      <td class="py-1.5 px-2 text-[10px] text-slate-300">Trading Style</td>
                      <td class="py-1.5 px-2 text-right">
                        <select id="settingTradingStyle" title="Select trading speed/style" class="bg-slate-950 border border-slate-700 rounded px-1 text-cyan-300 focus:outline-none cursor-pointer">
                            <option value="AUTO" selected>\uD83E\uDD16 AUTO (Adaptive)</option>
                            <option value="SNIPER">\uD83C\uDFAF Sniper (15m)</option>
                            <option value="MACHINE_GUN">\uD83D\uDD2B Machine Gun (1m)</option>
                            <option value="CHOP">\u2696\uFE0F Chop Engine (Low Vol)</option>
                        </select>
                      </td>
                    </tr>
                    '''

# Inject right before settingModelChoice
text = text.replace('<tr class="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">\n                      <td class="py-1.5 px-2 text-[10px] text-slate-300">ML Model</td>', row + '<tr class="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">\n                      <td class="py-1.5 px-2 text-[10px] text-slate-300">ML Model</td>')

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(text)
