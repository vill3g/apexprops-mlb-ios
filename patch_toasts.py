import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add the Toast Container to the body (right before script tag)
if 'id="toast-container"' not in content:
    content = content.replace('</body>', '    <!-- Toast Container -->\n    <div id="toast-container" class="fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none"></div>\n</body>')

# 2. Add the JS functions and logic
js_injection = '''
        let knownOpenTrades = new Set();
        let initialLoad = true;

        function showToast(message, type = 'info') {
            const container = document.getElementById('toast-container');
            if(!container) return;
            const toast = document.createElement('div');
            const color = type === 'success' ? 'bg-kalshi-green text-black' : (type === 'error' ? 'bg-kalshi-red text-white' : 'bg-kalshi-blue text-white');
            toast.className = `px-4 py-3 rounded-lg shadow-[0_0_15px_rgba(0,0,0,0.5)] border border-white/20 font-bold text-xs ${color} transition-opacity duration-500 opacity-0 transform translate-y-2`;
            toast.innerHTML = message;
            container.appendChild(toast);
            
            // Animate in
            requestAnimationFrame(() => {
                toast.classList.remove('opacity-0', 'translate-y-2');
            });
            
            // Animate out and remove
            setTimeout(() => {
                toast.classList.add('opacity-0', '-translate-y-2');
                setTimeout(() => toast.remove(), 500);
            }, 5000);
        }
        
        async function loadDashboard() {'''

content = content.replace('async function loadDashboard() {', js_injection)


# 3. Add the logic to the fetch success inside loadDashboard
logic_injection = '''                    // Track Open/Closed Trades for Toast Notifications
                    const currentOpenTrades = new Set(s.recent_trades.filter(t => t.status === 'OPEN').map(t => t.id));
                    
                    if (!initialLoad) {
                        s.recent_trades.forEach(t => {
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
                    
                    if (s.recent_trades) {'''

content = content.replace('if (s.recent_trades) {', logic_injection)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
