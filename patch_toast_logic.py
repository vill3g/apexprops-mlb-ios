import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

logic_injection = '''                    // Track Open/Closed Trades for Toast Notifications
                    const currentOpenTrades = new Set((s.recent_trades || []).filter(t => t.status === 'OPEN').map(t => t.id));
                    
                    if (!initialLoad) {
                        (s.recent_trades || []).forEach(t => {
                            // Check if an open trade closed
                            if(knownOpenTrades.has(t.id) && t.status !== 'OPEN') {
                                const pnl = t.pnl_dollars || 0;
                                const tType = pnl > 0 ? 'success' : (pnl < 0 ? 'error' : 'info');
                                const prefix = pnl >= 0 ? '+' : '';
                                showToast(`💰 Trade Closed:<br>${t.side.toUpperCase()} ${t.strike} &rarr; ${prefix}$${pnl.toFixed(2)}`, tType);
                            }
                            // Check if a new trade opened
                            if(t.status === 'OPEN' && !knownOpenTrades.has(t.id)) {
                                showToast(`🚀 Trade Opened:<br>${t.side.toUpperCase()} ${t.strike}`, 'info');
                            }
                        });
                    }
                    
                    knownOpenTrades = currentOpenTrades;
                    initialLoad = false;
                    
                    const recent = (s.recent_trades || []).slice(0, 5);'''

content = content.replace('const recent = (s.recent_trades || []).slice(0, 5);', logic_injection)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
