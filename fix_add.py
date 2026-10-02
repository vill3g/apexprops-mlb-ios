import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Add the ADD button to BOTH places (with profit and without profit)

# Place 1: (pnlVal > 0) has take profit and close
old1 = """<span class="text-[9px] font-bold text-yellow-400 animate-pulse">OPEN</span>
                                            <button onclick="event.stopPropagation(); takeProfitTrade('${t.id}')\""""
new1 = """<span class="text-[9px] font-bold text-yellow-400 animate-pulse">OPEN</span>
                                            <button onclick="event.stopPropagation(); executeManualTrade('${t.side}', '${t.asset || ''}')" class="px-1.5 py-0.5 bg-blue-600/25 text-blue-400 hover:bg-blue-600/40 rounded text-[8px] font-bold border border-blue-500/40 transition-all flex items-center gap-0.5 cursor-pointer"><span>&#10133;</span> ADD</button>
                                            <button onclick="event.stopPropagation(); takeProfitTrade('${t.id}')\""""

# Place 2: (pnlVal <= 0) has only close
old2 = """<span class="text-[9px] font-bold text-yellow-400 animate-pulse">OPEN</span>
                                            <button onclick="event.stopPropagation(); closeTrade('${t.id}')\""""
new2 = """<span class="text-[9px] font-bold text-yellow-400 animate-pulse">OPEN</span>
                                            <button onclick="event.stopPropagation(); executeManualTrade('${t.side}', '${t.asset || ''}')" class="px-1.5 py-0.5 bg-blue-600/25 text-blue-400 hover:bg-blue-600/40 rounded text-[8px] font-bold border border-blue-500/40 transition-all flex items-center gap-0.5 cursor-pointer"><span>&#10133;</span> ADD</button>
                                            <button onclick="event.stopPropagation(); closeTrade('${t.id}')\""""

if old1 in content:
    content = content.replace(old1, new1)
if old2 in content:
    content = content.replace(old2, new2)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("ADD button added.")
