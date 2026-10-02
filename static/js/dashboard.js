async function loadDashboard() {
    try {
        const token = localStorage.getItem('saas_token');
        const res = await fetch('/api/auth/dashboard_stats', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if(!res.ok) {
            if(res.status === 401 && typeof logout === 'function') logout();
            return;
        }
        const s = await res.json();
        const container = document.getElementById('tradesContainer');
        if (container && s.recent_trades) {
            let htmlString = '';
            s.recent_trades.forEach(t => {
                const statusBadge = t.status === 'OPEN' ? '<span class="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[8px] font-bold">OPEN</span>' : '<span class="px-1.5 py-0.5 rounded bg-gray-500/20 text-gray-400 text-[8px] font-bold">CLOSED</span>';
                const pnl = t.pnl_dollars || 0;
                const pnlStr = (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2);
                const pnlColor = pnl >= 0 ? 'text-emerald-400' : 'text-red-400';
                const badges = (t.badges || []).map(b => `<span class="px-1 py-0.5 rounded bg-white/5 text-[7px] text-gray-400">${b}</span>`);
                htmlString += `
                    <div class="p-2 rounded-xl bg-black/40 border border-white/5">
                        <div class="flex justify-between items-center mb-1">
                            <span class="text-[10px] font-bold text-white">${t.ticker || 'BTC'}</span>
                            <div class="flex items-center gap-2">
                                ${statusBadge}
                                <span class="text-[11px] font-mono font-bold ${pnlColor}">${pnlStr}</span>
                            </div>
                        </div>
                        <div class="flex justify-between items-center text-[9px] text-gray-500">
                            <span>${t.time || "Unknown Time"}</span>
                            <span>${t.count || 0} Cont. @ $${(t.entry_price || 0).toFixed(2)}</span>
                        </div>
                        <div class="flex flex-wrap gap-1 mt-0.5">
                            ${badges.join('')}
                        </div>
                    </div>
                `;
            });
            container.innerHTML = htmlString;
        }
    } catch(e) {
        console.error("Dashboard render error:", e);
    }
}

        window.closeTrade = async function(tradeId, action = 'MANUAL_CLOSE') {
            try {
                const token = localStorage.getItem('saas_token');
                const res = await fetch(`/api/auth/trade/close/${tradeId}?action=${encodeURIComponent(action)}`, {
                    method: 'POST',
                    headers: { 
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ action: action })
                });
                const data = await res.json();
                if(data.success) {
                    showToast('Trade closed successfully', 'success');
                    loadDashboard();
                } else {
                    showToast(data.detail || 'Failed to close trade', 'error');
                }
            } catch(e) {
                showToast('Network error closing trade', 'error');
            }
        };

        window.takeProfitTrade = async function(tradeId) {
            try {
                const token = localStorage.getItem('saas_token');
                const res = await fetch(`/api/auth/trade/close/${tradeId}?action=TAKE_PROFIT`, {
                    method: 'POST',
                    headers: { 
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ action: 'TAKE_PROFIT' })
                });
                const data = await res.json();
                if(data.success) {
                    if (data.reentry_triggered) {
                        const rIdx = data.reentry_trade?.reentry_index || 2;
                        showToast(`⚡ Profit secured! Tactical Re-Entry #${rIdx} placed.`, 'success');
                    } else {
                        showToast('⚡ Profit secured! Bot re-entry enabled.', 'success');
                    }
                    loadDashboard();
                } else {
                    showToast(data.detail || 'Failed to take profit', 'error');
                }
            } catch(e) {
                showToast('Network error taking profit', 'error');
            }
        };

        async function pollKalshi() {
            try {
                const asset = (window.currentDashboardAsset || 'btc').toLowerCase();
                // Fetch Ticker
                fetch(`/api/engine/${asset}/ticker`).then(r => r.json()).then(tData => {
                    if(tData && tData.price) {
                        document.getElementById('live-btc-price').innerText = '$' + parseFloat(tData.price).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                        document.getElementById('live-btc-price').classList.remove('animate-pulse');
                    }
                }).catch(e=>{});

                // Fetch Countdown
                fetch(`/api/engine/${asset}/countdown`).then(r => { if(!r.ok) throw new Error('HTTP error'); return r.json(); }).then(cData => {
                    if(cData.formatted) {
                        document.getElementById('kalshi-time').innerText = cData.formatted;
                    } else if(cData.minutes_remaining !== undefined) {
                        const mins = Math.floor(cData.minutes_remaining);
                        const secs = Math.floor((cData.minutes_remaining - mins) * 60);
                        document.getElementById('kalshi-time').innerText = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
                    } else {
                        document.getElementById('kalshi-time').innerText = "--:--";
                    }
                }).catch(e=>{});

                // Fetch Target/Kalshi odds
                const res = await fetch(`/api/engine/${asset}/kalshi`);
                if(!res.ok) return;
                const data = await res.json();

                if (data.target_price) {
                    document.getElementById('kalshi-target').innerText = '$' + data.target_price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    const currentYesProb = data.yes_prob || "--";
                    const currentNoProb = data.no_prob || "--";
                    document.getElementById('kalshi-yes').innerText = currentYesProb + (currentYesProb !== "--" ? "%" : "");
                    document.getElementById('kalshi-no').innerText = currentNoProb + (currentNoProb !== "--" ? "%" : "");
                } else {
                    document.getElementById('kalshi-target').innerText = "--";
                    document.getElementById('kalshi-yes').innerText = "--";
                    document.getElementById('kalshi-no').innerText = "--";
                }

                if(data.ml_reasoning) {
                    document.getElementById('ml-status-bubble').innerText = data.ml_reasoning.primary_bias || "AI";
                    document.getElementById('ml-status-bubble').className = "text-[8px] font-bold px-2 py-0.5 bg-black rounded-full border border-purple-500 text-purple-300 uppercase tracking-widest shadow-[0_0_10px_rgba(168,85,247,0.3)]";
                    fillMLCard(data.ml_reasoning, data);
                } else {
                    document.getElementById('ml-status-bubble').innerText = "STANDBY";
                    document.getElementById('ml-status-bubble').className = "text-[8px] font-bold px-2 py-0.5 bg-black rounded-full border border-gray-600 text-gray-500 uppercase tracking-widest";
                }
            } catch(e) {}
        }

        pollKalshi();
        loadDashboard();
        loadConfig();
        if(window.pollKalshiInterval) clearInterval(window.pollKalshiInterval); window.pollKalshiInterval = setInterval(pollKalshi, 1000);
        if(window.loadDashInterval) clearInterval(window.loadDashInterval); window.loadDashInterval = setInterval(loadDashboard, 1000);

        function initChart() {
            if (typeof TradingView !== "undefined") {
                new TradingView.widget({
                    "autosize": true,
                    "symbol": "COINBASE:BTCUSD",
                    "interval": "15",
                    "timezone": "Etc/UTC",
                    "theme": "dark",
                    "style": "1",
                    "locale": "en",
                    "enable_publishing": false,
                    "backgroundColor": "#131b2c",
                    "gridColor": "rgba(255, 255, 255, 0.06)",
                    "hide_top_toolbar": true,
                    "hide_legend": true,
                    "save_image": false,
                    "container_id": "tradingview_btc_chart"
                });
            } else {
                setTimeout(initChart, 500);
            }
        }
        initChart();


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

function toggleTakeProfitPctVisibility() {
    const isEnabled = document.getElementById('take-profit-enabled')?.checked;
    const row = document.getElementById('take-profit-pct-row');
    if(row) {
        if(isEnabled) {
            row.style.height = row.scrollHeight + "px";
            row.style.opacity = "1";
            row.style.marginTop = "0.75rem";
            row.style.pointerEvents = "auto";
        } else {
            row.style.height = "0px";
            row.style.opacity = "0";
            row.style.marginTop = "0px";
            row.style.pointerEvents = "none";
        }
    }
}
window.toggleTakeProfitPctVisibility = toggleTakeProfitPctVisibility;


// --- Web Push Registration (iOS Support) ---
window.urlB64ToUint8Array = function(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
};

async function enableWebPushNotifications() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        showToast('Web Push not supported on this browser. Try saving as PWA on iOS 16.4+', 'warning');
        return;
    }
    try {
        const registration = await navigator.serviceWorker.register('/static/sw.js');
        console.log('SW registered:', registration);
        
        let permission = await Notification.requestPermission();
        if (permission !== 'granted') {
            showToast('Permission for notifications denied', 'error');
            return;
        }

        const vapidRes = await fetch('/api/auth/push/public_key', { headers: {'Authorization': 'Bearer '+token} });
        const vapidData = await vapidRes.json();
        const applicationServerKey = urlB64ToUint8Array(vapidData.public_key);

        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: applicationServerKey
        });

        const subRes = await fetch('/api/auth/push/subscribe', {
            method: 'POST',
            headers: {'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'},
            body: JSON.stringify(subscription)
        });
        
        if (subRes.ok) {
            showToast('iOS Push Notifications Enabled!', 'success');
        } else {
            showToast('Failed to save push subscription', 'error');
        }
    } catch(e) {
        showToast('Error enabling push: ' + e.message, 'error');
        console.error(e);
    }
}
// ---------------------------------------------


// ==========================================
// Matrix Telemetry & CVD Gauge (SaaS)
// ==========================================
if(window.cvdGaugeInterval) clearInterval(window.cvdGaugeInterval); window.cvdGaugeInterval = setInterval(() => {
    // Attempt to grab forecast from global vars typically updated in dashboard.js
    let forecast = null;
    if (window.lastBtcData && window.lastBtcData.target_benchmark && window.lastBtcData.target_benchmark.next_contract_forecast) {
        forecast = window.lastBtcData.target_benchmark.next_contract_forecast;
    }
    
    if (forecast) {
        // Telemetry
        if (forecast.catalysts) {
            const consoleEl = document.getElementById("matrixTelemetryConsoleSaaS");
            const hash = JSON.stringify(forecast.catalysts);
            if (consoleEl && window._lastMatrixCatalystsSaaS !== hash) {
                consoleEl.innerHTML = "";
                forecast.catalysts.forEach((c, idx) => {
                    const p = document.createElement("div");
                    p.className = "truncate opacity-0 transition-opacity duration-500 ease-in-out";
                    p.innerHTML = `> <span class="text-emerald-400">SYS:</span> ${c}`;
                    consoleEl.appendChild(p);
                    setTimeout(() => { p.classList.remove("opacity-0"); p.classList.add("opacity-100"); }, 100 * idx);
                });
                window._lastMatrixCatalystsSaaS = hash;
            }
        }
        
        // CVD Gauge
        const cvdFill = document.getElementById("cvdGaugeFillSaaS");
        if (cvdFill) {
            let pct = 50; 
            if (forecast.probability_percent) {
                const dir = forecast.direction || "";
                const prob = parseFloat(forecast.probability_percent);
                if (dir.includes("ABOVE") || dir.includes("YES")) {
                    pct = 50 + ((prob - 50) * 0.8);
                } else if (dir.includes("BELOW") || dir.includes("NO")) {
                    pct = 50 - ((prob - 50) * 0.8);
                }
            }
            pct = Math.max(10, Math.min(90, pct));
            cvdFill.style.width = `${pct}%`;
            if (pct > 55) {
                cvdFill.className = "h-full bg-emerald-400 transition-all duration-700 shadow-[0_0_8px_rgba(52,211,153,0.5)]";
            } else if (pct < 45) {
                cvdFill.className = "h-full bg-red-500 transition-all duration-700 shadow-[0_0_8px_rgba(239,68,68,0.5)]";
            } else {
                cvdFill.className = "h-full bg-kalshi-blue transition-all duration-700";
            }
        }
    }
}, 2000);
