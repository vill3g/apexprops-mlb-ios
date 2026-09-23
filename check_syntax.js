
    const token = localStorage.getItem('saas_token');
    if (!token) window.location.href = '/login.html';
    
    let currentMode = "PAPER";

    function toggleSettings() {
        const modal = document.getElementById('settings-modal');
        const panel = document.getElementById('settings-panel');
        if (modal.classList.contains('hidden')) {
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            // small delay for animation
            setTimeout(() => { panel.classList.remove('translate-y-full'); }, 10);
        } else {
            panel.classList.add('translate-y-full');
            setTimeout(() => { modal.classList.add('hidden'); modal.classList.remove('flex'); }, 300);
        }
    }

    
    let aiEnabled = true;

    async function toggleAI(enabled) {
        try {
            const res = await fetch('/api/auth/ai_toggle', {
                method: "POST",
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ enabled: enabled })
            });
            if(res.ok) {
                aiEnabled = enabled;
                loadDashboard();
            }
        } catch(e) {}
    }

    async function setTradingMode(mode) {
        try {
            const res = await fetch('/api/auth/trade/config', {
                method: "POST",
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ mode: mode })
            });
            if(res.ok) {
                currentMode = mode;
                updateModeUI();
                loadDashboard(); // Refresh stats with new mode
                alert(`Trading mode switched to ${mode}`);
            } else {
                const data = await res.json();
                alert(data.detail || "Failed to switch mode");
            }
        } catch(e) {
            alert("Network error updating mode");
        }
    }

    function updateModeUI() {
        const slider = document.getElementById('mode-slider');
        const btnPaper = document.getElementById('btn-mode-paper');
        const btnLive = document.getElementById('btn-mode-live');
        const badge = document.getElementById('bal-mode-badge');
        
        if(currentMode === "LIVE") {
            slider.style.transform = "translateX(100%)";
            slider.className = "absolute top-1 bottom-1 w-1/2 bg-kalshi-red rounded-md transition-all shadow-sm";
            btnLive.className = "flex-1 relative z-10 py-2 text-xs font-bold uppercase tracking-wider text-white";
            btnPaper.className = "flex-1 relative z-10 py-2 text-xs font-bold uppercase tracking-wider text-gray-400";
            badge.innerText = "LIVE";
            badge.className = "px-1.5 py-0.5 rounded bg-kalshi-red text-white";
        } else {
            slider.style.transform = "translateX(0%)";
            slider.className = "absolute top-1 bottom-1 w-1/2 bg-kalshi-blue rounded-md transition-all shadow-sm";
            btnPaper.className = "flex-1 relative z-10 py-2 text-xs font-bold uppercase tracking-wider text-white";
            btnLive.className = "flex-1 relative z-10 py-2 text-xs font-bold uppercase tracking-wider text-gray-400";
            badge.innerText = "PAPER";
            badge.className = "px-1.5 py-0.5 rounded bg-kalshi-blue text-white";
        }
    }

    
    async function closeAllTrades() {
        if(!confirm(`Are you sure you want to CLOSE ALL open ${currentMode} trades at current market prices?`)) return;
        try {
            const res = await fetch('/api/auth/trade/close_all', {
                method: "POST",
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            if(res.ok) {
                alert(`Successfully closed ${data.closed_count} positions.`);
                loadDashboard();
            } else {
                alert(`Failed: ${data.detail}`);
            }
        } catch(e) {
            alert("Network error closing trades.");
        }
    }

    async function executeManualTrade(direction) {
        const amt = parseFloat(document.getElementById('trade-amount').value || 50);
        const oneClick = document.getElementById('one-click-toggle').checked;
        if(!oneClick && !confirm(`Execute $${amt} manual trade for ${direction} in ${currentMode} mode?`)) return;
        
        try {
            const res = await fetch('/api/auth/trade/manual', {
                method: "POST",
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ direction: direction, amount_dollars: amt })
            });
            const data = await res.json();
            if(res.ok) {
                alert(`Success! Manual trade executed.`);
                loadDashboard();
            } else {
                alert(`Trade Failed: ${data.detail}`);
            }
        } catch(e) {
            alert("Network error during manual trade.");
        }
    }

    async function loadDashboard() {
        try {
            const statRes = await fetch('/api/auth/dashboard_stats', { headers: { 'Authorization': `Bearer ${token}` } });
            if (statRes.ok) {
                const s = await statRes.json();
                
                currentMode = s.trading_mode || "PAPER";
                updateModeUI();
                
                if (s.balance_dollars !== null && s.balance_dollars !== undefined) {
                    document.getElementById('val-balance').innerText = `$${s.balance_dollars.toFixed(2)}`;
                } else {
                    document.getElementById('val-balance').innerText = "Auth Error";
                    document.getElementById('val-balance').classList.add('text-kalshi-red');
                }

                const pnl = s.total_pnl || 0;
                const pnlEl = document.getElementById('val-pnl');
                pnlEl.innerText = `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`;
                pnlEl.className = `text-lg font-black tabular-nums tracking-tighter ${pnl >= 0 ? 'text-kalshi-green' : 'text-kalshi-red'}`;

                document.getElementById('val-winrate').innerText = `${s.win_rate}%`;
                // document.getElementById('val-trades').innerText = (s.wins + s.losses) || 0;


                aiEnabled = s.ai_enabled;
                document.getElementById('ai-toggle-btn').checked = aiEnabled;

                const statusEl = document.getElementById('connection-status');
                
                const quickBtn = document.getElementById('quick-ai-btn');
                if (quickBtn) {
                    if (aiEnabled) {
                        quickBtn.innerText = "Copy AI: ON";
                        quickBtn.className = "flex-1 py-2 bg-kalshi-green/20 text-kalshi-green font-bold text-[10px] uppercase tracking-widest rounded transition-colors active:scale-95 border border-kalshi-green/50 hover:bg-kalshi-green/40";
                    } else {
                        quickBtn.innerText = "Copy AI: OFF";
                        quickBtn.className = "flex-1 py-2 bg-gray-800 text-gray-500 font-bold text-[10px] uppercase tracking-widest rounded transition-colors active:scale-95 border border-gray-700 hover:bg-gray-700";
                    }
                }

                if (!aiEnabled) {
                    statusEl.innerText = "Paused (AI Ignored)";
                    statusEl.className = "text-[10px] uppercase font-bold text-gray-500 tracking-wider";
                } else if (currentMode === "LIVE" && s.balance_dollars === null) {
                    statusEl.innerText = "Keys Required";
                    statusEl.className = "text-[10px] uppercase font-bold text-kalshi-red tracking-wider";
                } else {
                    statusEl.innerText = "Listening for Signals...";
                    statusEl.className = "text-[10px] uppercase font-bold text-kalshi-green tracking-wider";
                }


                const tbody = document.getElementById('trades-body');
                if (s.recent_trades && s.recent_trades.length > 0) {
                    let html = '';
                    s.recent_trades.forEach(t => {
                        const time = t.timestamp ? t.timestamp.split(' ')[1] + ' ' + t.timestamp.split(' ')[2] : '--';
                        const isYes = t.side === 'YES';
                        const dirClass = isYes ? 'text-kalshi-green bg-green-900/30' : 'text-kalshi-red bg-red-900/30';
                        const modeBadge = t.mode === 'PAPER' ? '<span class="text-[8px] text-kalshi-blue bg-blue-900/30 px-1 rounded mr-1">PAPER</span>' : '<span class="text-[8px] text-kalshi-red bg-red-900/30 px-1 rounded mr-1">LIVE</span>';
                        
                        let statusHtml = '';
                        let pnlText = '--';
                        let pnlColor = 'text-gray-400';
                        
                        if (t.status === 'CLOSED' || t.status === 'SETTLED') {
                            const isWin = parseFloat(t.pnl) > 0;
                            statusHtml = isWin ? `<span class="text-[9px] font-bold text-kalshi-green uppercase">WIN</span>` : `<span class="text-[9px] font-bold text-kalshi-red uppercase">LOSS</span>`;
                            pnlText = `${parseFloat(t.pnl) >= 0 ? '+' : ''}$${parseFloat(t.pnl).toFixed(2)}`;
                            pnlColor = isWin ? 'text-kalshi-green' : 'text-kalshi-red';
                        } else {
                            statusHtml = `<span class="text-[9px] font-bold text-gray-400 uppercase">OPEN</span>`;
                            if (t.live_pnl !== undefined) {
                                pnlText = `${parseFloat(t.live_pnl) >= 0 ? '+' : ''}$${parseFloat(t.live_pnl).toFixed(2)}`;
                                pnlColor = parseFloat(t.live_pnl) >= 0 ? 'text-kalshi-green' : 'text-kalshi-red';
                            }
                        }

                        html += `
                        <div class="p-3 flex justify-between items-center hover:bg-black/20 transition-colors border-b border-kalshi-border/50">
                            <div>
                                <div class="flex items-center gap-1 mb-1">
                                    ${modeBadge}
                                    <span class="px-1.5 py-0.5 rounded text-[9px] font-bold ${dirClass}">${t.side}</span>
                                    <span class="text-xs font-bold text-gray-300 truncate max-w-[120px]">${t.ticker || 'Unknown'}</span>
                                </div>
                                <div class="text-[10px] text-gray-500 font-mono">${time} ${t.reason === 'MANUAL' ? '(Manual)' : ''}</div>
                            </div>
                            <div class="text-right">
                                <div class="font-bold text-sm tabular-nums tracking-tight ${pnlColor}">${pnlText}</div>
                                ${statusHtml}
                            </div>
                        </div>
                        `;
                    });
                    tbody.innerHTML = html;
                }
            }
        } catch (e) {
            console.error("Dashboard error", e);
        }
    }

    async function saveKeys() {
        const keyId = document.getElementById('kalshi-key').value;
        const privKey = document.getElementById('kalshi-priv').value;
        if (!keyId || !privKey) { alert('Please provide both keys.'); return; }

        try {
            const btn = event.currentTarget;
            const originalText = btn.innerText;
            btn.innerText = "Securing...";
            btn.disabled = true;

            const res = await fetch('/api/auth/keys', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ key_id: keyId, private_key: privKey })
            });
            const data = await res.json();
            
            btn.innerText = originalText;
            btn.disabled = false;

            if (data.success) {
                document.getElementById('kalshi-key').value = '';
                document.getElementById('kalshi-priv').value = '';
                alert('Success! Keys encrypted and connected.');
                toggleSettings();
                loadDashboard();
            } else {
                alert(data.detail || 'Failed to save keys.');
            }
        } catch (e) {
            alert('Network error.');
        }
    }

    function logout() {
        localStorage.removeItem('saas_token');
        localStorage.removeItem('saas_username');
        window.location.href = '/login.html';
    }

    // Load TradingView Chart
    setTimeout(() => {
        if(window.TradingView) {
            new TradingView.widget({
                autosize: true,
                symbol: "BINANCE:BTCUSDT",
                interval: "15",
                timezone: "America/New_York",
                theme: "dark",
                style: "1",
                locale: "en",
                toolbar_bg: "#0b0f19",
                enable_publishing: false,
                allow_symbol_change: false,
                hide_side_toolbar: true,
                withdateranges: false,
                hide_top_toolbar: true,
                save_image: false,
                container_id: "tv_chart_container",
                studies: []
            });
        }
    }, 500);


    let globalCloseDate = null;
    let currentYesProb = '--';
    let currentNoProb = '--';

    // Standalone timer that updates the UI exactly every second
    setInterval(() => {
        if (globalCloseDate) {
            const diff = Math.max(0, globalCloseDate - new Date()) / 1000;
            const mins = Math.floor(diff / 60);
            const secs = Math.floor(diff % 60);
            document.getElementById('kalshi-time').innerText = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')} LEFT`;
        }
    }, 1000);


    async function pollML() {
        try {
            const res = await fetch('/api/engine/btc/analyze');
            if(res.ok) {
                const data = await res.json();
                lastMLData = data;
                fillMLPopup();
                
                const bubble = document.getElementById('ml-status-bubble');
                if(data.direction === 'ABOVE') {
                    bubble.innerText = 'AI: BUY YES';
                    bubble.className = 'cursor-pointer px-1.5 py-[2px] rounded text-[8px] font-bold uppercase tracking-widest bg-green-900/40 text-emerald-400 border border-green-500/50 shadow-sm transition-colors duration-300 animate-pulse hover:scale-105 active:scale-95';
                } else if(data.direction === 'BELOW') {
                    bubble.innerText = 'AI: BUY NO';
                    bubble.className = 'cursor-pointer px-1.5 py-[2px] rounded text-[8px] font-bold uppercase tracking-widest bg-red-900/40 text-red-400 border border-red-500/50 shadow-sm transition-colors duration-300 animate-pulse hover:scale-105 active:scale-95';
                } else {
                    bubble.innerText = 'AI: HOLD (CHOP)';
                    bubble.className = 'cursor-pointer px-1.5 py-[2px] rounded text-[8px] font-bold uppercase tracking-widest bg-gray-800 text-gray-400 border border-gray-600 shadow-sm transition-colors duration-300 hover:scale-105 active:scale-95';
                }
            }
        } catch(e) {}
    }
    
    pollML();
    setInterval(pollML, 8000);

    async function pollKalshi() {
        try {
            const [kRes, tRes] = await Promise.all([
                fetch('/api/engine/btc/kalshi'),
                fetch('/api/engine/btc/ticker')
            ]);
            
            if(tRes.ok) {
                const tData = await tRes.json();
                if(tData && tData.price) {
                    document.getElementById('live-btc-price').innerText = '$' + parseFloat(tData.price).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    document.getElementById('live-btc-price').classList.remove('animate-pulse');
                }
            }

            if(kRes.ok) {
                const data = await kRes.json();
                if(data.target_price) {
                    document.getElementById('kalshi-target').innerText = '$' + data.target_price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    
                    currentYesProb = Math.round(data.yes_prob || 0);
                    currentNoProb = Math.round(data.no_prob || 0);
                    
                    document.getElementById('kalshi-yes').innerText = currentYesProb;
                    document.getElementById('kalshi-no').innerText = currentNoProb;
                    
                    // Update the Manual Trade buttons dynamically
                    document.getElementById('btn-buy-yes').innerText = `BUY YES (${currentYesProb}%)`;
                    document.getElementById('btn-buy-no').innerText = `BUY NO (${currentNoProb}%)`;
                    
                    if(data.close_time) {
                        globalCloseDate = new Date(data.close_time);
                    }
                } else {
                    document.getElementById('kalshi-target').innerText = "NO ACTIVE MARKET";
                    document.getElementById('kalshi-time').innerText = "WAITING";
                    document.getElementById('kalshi-yes').innerText = "--";
                    document.getElementById('kalshi-no').innerText = "--";
                    document.getElementById('btn-buy-yes').innerText = `BUY YES`;
                    document.getElementById('btn-buy-no').innerText = `BUY NO`;
                    globalCloseDate = null;
                }
            }
        } catch(e){}
    }


    pollKalshi();
    loadDashboard();
    setInterval(pollKalshi, 1000);
    setInterval(loadDashboard, 1000);
` },
                body: JSON.stringify({ trade_size_pct: size, stop_loss_pct: sl, one_click_trade: oneClick })
            });
            if(res.ok) {
                alert("AI & Trade Preferences Saved!");
            }
        } catch(e) {}
    }
mode?`)) return;
        
        try {
            const res = await fetch('/api/auth/trade/force_ml', {
                method: "POST",
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            if(res.ok) {
                alert(`⚡ Success! ML forced a ${data.side} trade for ${data.count} contracts at $${data.price}`);
                loadDashboard();
                toggleSettings(); // Close modal
            } else {
                alert(`Action Failed: ${data.detail}`);
            }
        } catch(e) {
            alert('Network error executing force trade.');
        }
    }


    async function saveUserConfig() {
        const size = parseFloat(document.getElementById('trade-size-pct').value) || 20.0;
        const sl = parseFloat(document.getElementById('stop-loss-pct').value) || 10.0;
        const toggleEl = document.getElementById('one-click-toggle');
        const oneClick = toggleEl ? toggleEl.checked : false;
        
        try {
            const res = await fetch('/api/auth/user/config', {
                method: "POST",
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ trade_size_pct: size, stop_loss_pct: sl, one_click_trade: oneClick })
            });
            if(res.ok) {
                alert("AI & Trade Preferences Saved!");
            }
        } catch(e) {}
    }

    let lastMLData = null;
    
    function toggleMLPopup(e) {
        if(e) e.stopPropagation();
        const popup = document.getElementById('ml-details-popup');
        popup.classList.toggle('hidden');
        fillMLPopup();
    }
    
    function fillMLPopup() {
        if(!lastMLData) return;
        document.getElementById('popup-bias').innerText = lastMLData.primary_bias || '--';
        document.getElementById('popup-conf').innerText = `${lastMLData.confidence_percent || 0}%`;
        document.getElementById('popup-prob').innerText = `${((lastMLData.predicted_probability || 0)*100).toFixed(1)}%`;
        
        let confColor = 'text-gray-400';
        if(lastMLData.confidence_percent >= 60) confColor = 'text-kalshi-green';
        else if(lastMLData.confidence_percent <= 40) confColor = 'text-kalshi-red';
        document.getElementById('popup-conf').className = `font-bold ${confColor}`;
        
        let summaryText = '';
        if(lastMLData.summary) {
            summaryText = lastMLData.summary;
        } else {
            summaryText = `Model predicts ${lastMLData.primary_bias} with ${((lastMLData.predicted_probability || 0)*100).toFixed(1)}% probability based on timeframe analysis.`;
        }
        document.getElementById('popup-summary').innerText = summaryText;
    }
    
    document.addEventListener('click', (e) => {
        const popup = document.getElementById('ml-details-popup');
        const bubble = document.getElementById('ml-status-bubble');
        if(popup && !popup.classList.contains('hidden') && !popup.contains(e.target) && !bubble.contains(e.target)) {
            popup.classList.add('hidden');
        }
    });

    async function forceMLTrade() {
        const toggleEl = document.getElementById('one-click-toggle');
        const oneClick = toggleEl ? toggleEl.checked : false;
        if(!oneClick && !confirm(`Are you sure you want to FORCE the AI's current signal using your configured trade size in ${currentMode} mode?`)) return;
        
        try {
            const res = await fetch('/api/auth/trade/force_ml', {
                method: "POST",
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            if(res.ok) {
                alert(`⚡ Success! ML forced a ${data.side} trade for ${data.count} contracts at $${data.price}`);
                loadDashboard();
                if(typeof toggleSettings === 'function') toggleSettings(); // Close modal
            } else {
                alert(`Action Failed: ${data.detail}`);
            }
        } catch(e) {
            alert('Network error executing force trade.');
        }
    }

