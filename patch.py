import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

notify_code = '''
        let knownCompletedTrades = new Set();
        window.enableIosNotifications = true;

        window.iosNotify = function(title, subtitle, type="success") {
            if (!window.enableIosNotifications) return;
            let container = document.getElementById('ios-notify-container');
            if(!container){
                container = document.createElement('div');
                container.id = 'ios-notify-container';
                container.className = 'fixed top-4 left-0 right-0 z-[9999] flex flex-col items-center gap-2 pointer-events-none px-4';
                document.body.appendChild(container);
            }
            const toast = document.createElement('div');
            const icon = type === "success" ? "??" : (type === "error" ? "??" : "??");
            const bg = type === "success" ? "bg-gradient-to-r from-emerald-950/90 to-[#1c1c1e]/90 border-emerald-500/30" : (type === "error" ? "bg-gradient-to-r from-rose-950/90 to-[#1c1c1e]/90 border-rose-500/30" : "bg-[#1c1c1e]/90 border-white/10");
            toast.className = \lex items-center gap-3 w-full max-w-sm p-3.5 rounded-[24px] shadow-[0_10px_40px_rgba(0,0,0,0.6)] backdrop-blur-xl border \ transition-all duration-500 ease-out translate-y-[-150%] opacity-0\;
            toast.innerHTML = \
                <div class="w-10 h-10 shrink-0 flex items-center justify-center text-xl bg-black/40 rounded-full border border-white/10 shadow-inner">
                    \
                </div>
                <div class="flex flex-col">
                    <span class="text-[13px] font-black tracking-wide text-white">\</span>
                    <span class="text-[11px] font-medium text-gray-300 mt-0.5">\</span>
                </div>
            \;
            container.appendChild(toast);
            requestAnimationFrame(() => requestAnimationFrame(() => toast.classList.remove('translate-y-[-150%]', 'opacity-0')));
            setTimeout(() => {
                toast.classList.add('translate-y-[-150%]', 'opacity-0');
                setTimeout(() => toast.remove(), 500);
            }, 5000);
            try { if(type === "success" && window.soundEngine) window.soundEngine.play('order_fill'); } catch(e){}
        }
'''
content = content.replace("let knownOpenTrades = new Set();", "let knownOpenTrades = new Set();\n" + notify_code)

check_code = '''
                window.lastDashboardStats = s;

                // iOS Notifications for newly closed trades
                if (s.recent_trades && Array.isArray(s.recent_trades)) {
                    s.recent_trades.forEach(t => {
                        const status = String(t.status || '').toUpperCase();
                        const tradeId = String(t.id);
                        if (status === 'CLOSED' || status.includes('WIN') || status.includes('LOSS')) {
                            if (!knownCompletedTrades.has(tradeId)) {
                                if (!initialLoad) {
                                    const pnl = parseFloat(t.pnl_dollars || t.pnl || 0);
                                    const isWin = status.includes('WIN') || pnl > 0;
                                    const assetStr = t.asset || 'Asset';
                                    if (isWin) {
                                        window.iosNotify('Trade Won! ??', \\ profit secured: +$\\, 'success');
                                    } else {
                                        window.iosNotify('Trade Closed', \\ loss incurred: -$\\, 'error');
                                    }
                                }
                                knownCompletedTrades.add(tradeId);
                            }
                        }
                    });
                }
'''
content = content.replace("window.lastDashboardStats = s;", check_code)

toggle_html = '''
                                <!-- Audio Engine -->
                                <div class="space-y-3 pt-3 border-t border-white/5">
                                    <div class="flex items-center justify-between">
                                        <div class="flex items-center gap-2">
                                            <span class="text-base">??</span>
                                            <div class="flex flex-col">
                                                <span class="text-xs font-bold text-gray-200">iOS Push Notifications</span>
                                                <span class="text-[10px] text-gray-500">Show dynamic overlay for trade events</span>
                                            </div>
                                        </div>
                                        <label class="relative inline-flex items-center cursor-pointer">
                                            <input type="checkbox" id="ios-notify-toggle" class="sr-only peer" checked onchange="window.enableIosNotifications = this.checked;">
                                            <div class="w-9 h-5 bg-black/60 border border-white/10 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-gray-400 peer-checked:after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-500/80 peer-checked:border-emerald-400"></div>
                                        </label>
                                    </div>
                                    <div class="flex items-center justify-between">
                                        <div class="flex items-center gap-2">
                                            <span class="text-base">??</span>
'''

content = content.replace('''
                                <!-- Audio Engine -->
                                <div class="space-y-3 pt-3 border-t border-white/5">
                                    <div class="flex items-center justify-between">
                                        <div class="flex items-center gap-2">
                                            <span class="text-base">??</span>''', toggle_html)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
