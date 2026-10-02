import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Update Table Headers
old_thead = '''                    <thead class="bg-black/60 text-gray-500 text-[8px] uppercase tracking-widest border-b border-kalshi-border">
                        <tr>
                            <th class="py-2.5 px-3 font-bold">Time</th>
                            <th class="py-2.5 px-3 font-bold text-center">Side</th>
                            <th class="py-2.5 px-3 font-bold text-center">Strike</th>
                            <th class="py-2.5 px-3 font-bold text-right">PnL</th>
                        </tr>
                    </thead>'''

new_thead = '''                    <thead class="bg-black/60 text-gray-500 text-[8px] uppercase tracking-widest border-b border-kalshi-border">
                        <tr>
                            <th class="py-2.5 px-3 font-bold">Time</th>
                            <th class="py-2.5 px-3 font-bold text-center">Type</th>
                            <th class="py-2.5 px-3 font-bold text-center">Side</th>
                            <th class="py-2.5 px-3 font-bold text-center">Status</th>
                            <th class="py-2.5 px-3 font-bold text-right">PnL</th>
                        </tr>
                    </thead>'''

content = content.replace(old_thead, new_thead)

# Update Table Body Injection
old_tbody = '''                          recent.forEach(t => {
                            const sideColor = t.side === 'yes' ? 'text-kalshi-green' : 'text-kalshi-red';
                            const pnlColor = t.pnl_dollars >= 0 ? 'text-kalshi-green' : 'text-kalshi-red';
                            const pnlStr = t.pnl_dollars >= 0 ? `+$${t.pnl_dollars.toFixed(2)}` : `-$${Math.abs(t.pnl_dollars).toFixed(2)}`;
                            tbody.innerHTML += `
                                <tr class="hover:bg-white/5 transition-colors">
                                    <td class="py-2.5 px-3 text-gray-400 tabular-nums">${t.time}</td>
                                    <td class="py-2.5 px-3 text-center font-bold ${sideColor} uppercase">${t.side}</td>
                                    <td class="py-2.5 px-3 text-center text-gray-300 tabular-nums">${t.strike}</td>
                                    <td class="py-2.5 px-3 font-black text-right ${pnlColor} tabular-nums">${pnlStr}</td>
                                </tr>
                            `;
                        });'''

new_tbody = '''                          recent.forEach(t => {
                            const sideColor = t.side === 'yes' ? 'text-kalshi-green' : 'text-kalshi-red';
                            const pnlColor = t.pnl_dollars >= 0 ? 'text-kalshi-green' : 'text-kalshi-red';
                            const pnlStr = t.pnl_dollars >= 0 ? `+$${t.pnl_dollars.toFixed(2)}` : `-$${Math.abs(t.pnl_dollars).toFixed(2)}`;
                            const isAuto = (!t.reason || t.reason.includes('AI') || t.reason.includes('AUTO'));
                            const typeBadge = isAuto 
                                ? '<span class="px-1.5 py-0.5 bg-kalshi-blue/20 text-kalshi-blue rounded text-[8px] font-bold">AUTO</span>' 
                                : '<span class="px-1.5 py-0.5 bg-purple-500/20 text-purple-400 rounded text-[8px] font-bold">MANUAL</span>';
                                
                            const statusBadge = t.status === 'OPEN' 
                                ? '<span class="text-yellow-400 font-bold animate-pulse text-[9px]">OPEN</span>'
                                : '<span class="text-gray-500 font-bold text-[9px]">CLOSED</span>';

                            tbody.innerHTML += `
                                <tr class="hover:bg-white/5 transition-colors">
                                    <td class="py-2.5 px-3 text-gray-400 tabular-nums">${t.time}</td>
                                    <td class="py-2.5 px-3 text-center">${typeBadge}</td>
                                    <td class="py-2.5 px-3 text-center font-bold ${sideColor} uppercase">${t.side}</td>
                                    <td class="py-2.5 px-3 text-center">${statusBadge}</td>
                                    <td class="py-2.5 px-3 font-black text-right ${pnlColor} tabular-nums">${pnlStr}</td>
                                </tr>
                            `;
                        });'''

content = content.replace(old_tbody, new_tbody)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
