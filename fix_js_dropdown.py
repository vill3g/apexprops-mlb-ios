import re

js_path = "static/js/dashboard.js"
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

js_addition = """

// Glassy Profile Menu Logic
function toggleProfileMenu() {
    const menu = document.getElementById('profileDropdown');
    if (!menu) return;
    
    if (menu.classList.contains('hidden')) {
        // Populate stats
        if (window.latestDashboardStats) {
            const s = window.latestDashboardStats;
            document.getElementById('dropdown-username').innerText = s.username || 'Trader';
            if (s.profile_pic) document.getElementById('dropdown-avatar').src = s.profile_pic;
            
            const mBadge = document.getElementById('dropdown-mode-badge');
            mBadge.innerText = s.trading_mode || 'PAPER';
            if (s.trading_mode === 'LIVE') {
                mBadge.className = 'px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-[9px] font-bold uppercase tracking-widest';
            } else {
                mBadge.className = 'px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 text-[9px] font-bold uppercase tracking-widest';
            }
            
            document.getElementById('dropdown-winrate').innerText = (s.win_rate || 0).toFixed(1) + '%';
            document.getElementById('dropdown-wins').innerText = (s.wins || 0) + 'W';
            document.getElementById('dropdown-losses').innerText = (s.losses || 0) + 'L';
            
            const pnl = s.total_pnl || 0;
            const pnlEl = document.getElementById('dropdown-pnl');
            pnlEl.innerText = `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`;
            pnlEl.className = `text-sm font-black tabular-nums truncate ${pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`;
            
            const pnlPct = s.total_pnl_pct || 0;
            const pnlPctEl = document.getElementById('dropdown-pnl-pct');
            pnlPctEl.innerText = `${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(1)}%`;
            pnlPctEl.className = `text-[9px] font-bold font-mono mt-0.5 ${pnlPct >= 0 ? 'text-emerald-500' : 'text-rose-500'}`;
        }

        menu.classList.remove('hidden');
        void menu.offsetWidth; // trigger reflow
        menu.classList.remove('scale-90', 'opacity-0', 'translate-x-[-10px]', 'translate-y-[-10px]');
        menu.classList.add('scale-100', 'opacity-100', 'translate-x-0', 'translate-y-0');
    } else {
        menu.classList.remove('scale-100', 'opacity-100', 'translate-x-0', 'translate-y-0');
        menu.classList.add('scale-90', 'opacity-0', 'translate-x-[-10px]', 'translate-y-[-10px]');
        setTimeout(() => menu.classList.add('hidden'), 300);
    }
}

document.addEventListener('click', (e) => {
    const menu = document.getElementById('profileDropdown');
    const profileTrigger = document.getElementById('profile-trigger-area');
    if (menu && !menu.classList.contains('hidden')) {
        if (!menu.contains(e.target) && (!profileTrigger || !profileTrigger.contains(e.target))) {
            toggleProfileMenu();
        }
    }
});
"""

# Append to file
with open(js_path, "a", encoding="utf-8") as f:
    f.write(js_addition)
print("Added JS profile menu logic!")
