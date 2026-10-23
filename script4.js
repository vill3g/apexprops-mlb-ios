
        const token = localStorage.getItem('saas_token');
        if (!token) window.location.href = './login.html';
        
        let currentMode = "PAPER";
        let aiEnabled = true; // Assume true since we removed toggle to simplify iPhone UI. We could re-add if requested.

        function logout() {
            localStorage.removeItem('saas_token');
            window.location.href = './login.html';
        }

        // ── Tab Visibility & Polling Optimization (Audit Item 1) ──
        window.isTabActive = true;
        document.addEventListener('visibilitychange', () => {
            window.isTabActive = !document.hidden;
            if (window.isTabActive) {
                if (typeof fetchKalshiData === 'function') fetchKalshiData();
                if (typeof fetchChartData === 'function') fetchChartData();
                if (typeof loadDashboard === 'function') loadDashboard();
            }
        });

        // ── Synthesized Sound FX Engine (Feature 1) ──
        const soundEngine = {
            ctx: null,
            enabled: localStorage.getItem('sound_enabled') !== 'false',
            init() {
                if (!this.ctx) {
                    const AudioCtx = window.AudioContext || window.webkitAudioContext;
                    if (AudioCtx) this.ctx = new AudioCtx();
                }
                if (this.ctx && this.ctx.state === 'suspended') {
                    this.ctx.resume();
                }
            },
            play(type) {
                if (!this.enabled) return;
                try {
                    this.init();
                    if (!this.ctx) return;
                    const t = this.ctx.currentTime;
                    const osc = this.ctx.createOscillator();
                    const gain = this.ctx.createGain();
                    osc.connect(gain);
                    gain.connect(this.ctx.destination);

                    if (type === 'order_fill') {
                        osc.type = 'sine';
                        osc.frequency.setValueAtTime(880, t);
                        osc.frequency.exponentialRampToValueAtTime(1320, t + 0.08);
                        gain.gain.setValueAtTime(0.12, t);
                        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.15);
                        osc.start(t);
                        osc.stop(t + 0.15);
                    } else if (type === 'win') {
                        const notes = [523.25, 659.25, 783.99, 1046.50];
                        notes.forEach((freq, idx) => {
                            const o = this.ctx.createOscillator();
                            const g = this.ctx.createGain();
                            o.connect(g);
                            g.connect(this.ctx.destination);
                            o.type = 'triangle';
                            o.frequency.value = freq;
                            const st = t + (idx * 0.07);
                            g.gain.setValueAtTime(0.14, st);
                            g.gain.exponentialRampToValueAtTime(0.001, st + 0.25);
                            o.start(st);
                            o.stop(st + 0.25);
                        });
                    } else if (type === 'loss') {
                        osc.type = 'sawtooth';
                        osc.frequency.setValueAtTime(160, t);
                        osc.frequency.exponentialRampToValueAtTime(60, t + 0.2);
                        gain.gain.setValueAtTime(0.15, t);
                        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.22);
                        osc.start(t);
                        osc.stop(t + 0.22);
                    } else if (type === 'reverse') {
                        osc.type = 'sawtooth';
                        osc.frequency.setValueAtTime(1400, t);
                        osc.frequency.exponentialRampToValueAtTime(250, t + 0.2);
                        gain.gain.setValueAtTime(0.15, t);
                        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.25);
                        osc.start(t);
                        osc.stop(t + 0.25);
                    } else if (type === 'countdown_warning') {
                        [0, 0.1].forEach(offset => {
                            const o = this.ctx.createOscillator();
                            const g = this.ctx.createGain();
                            o.connect(g);
                            g.connect(this.ctx.destination);
                            o.type = 'sine';
                            o.frequency.value = 950;
                            g.gain.setValueAtTime(0.1, t + offset);
                            g.gain.exponentialRampToValueAtTime(0.001, t + offset + 0.05);
                            o.start(t + offset);
                            o.stop(t + offset + 0.05);
                        });
                    }
                } catch(e) {
                    console.warn('[Audio] playback error:', e);
                }
            }
        };

        window.syncSoundSettingsUI = function() {
            const isEnabled = localStorage.getItem('sound_enabled') !== 'false';
            soundEngine.enabled = isEnabled;
            const toggle = document.getElementById('settings-sound-toggle');
            if (toggle) toggle.checked = isEnabled;
            const icon = document.getElementById('settings-sound-icon');
            if (icon) icon.textContent = isEnabled ? '🔊' : '🔇';
            const statusBadge = document.getElementById('settings-sound-status');
            if (statusBadge) {
                statusBadge.textContent = isEnabled ? 'ACTIVE' : 'MUTED';
                statusBadge.className = isEnabled 
                    ? 'text-[9px] font-bold text-emerald-400 uppercase tracking-widest' 
                    : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';
            }
        };

        window.isTradeExecutionPanelShowing = function() {
            const panel = document.getElementById('trade-execution-panel');
            if (!panel) {
                return localStorage.getItem('showTradeExecutionPanel') !== 'false';
            }
            const computed = window.getComputedStyle(panel).display;
            return panel.style.display !== 'none' && computed !== 'none';
        };

        window.updatePositionScannerCloseButton = function() {
            const isShowing = window.isTradeExecutionPanelShowing();
            const closeBtn = document.getElementById('scanner-close-now-btn');
            const actionsContainer = document.getElementById('position-scanner-actions');
            
            if (closeBtn) {
                if (isShowing) {
                    closeBtn.classList.add('hidden');
                } else {
                    closeBtn.classList.remove('hidden');
                }
            }
            if (actionsContainer) {
                if (isShowing) {
                    actionsContainer.classList.remove('grid-cols-3');
                    actionsContainer.classList.add('grid-cols-2');
                } else {
                    actionsContainer.classList.remove('grid-cols-2');
                    actionsContainer.classList.add('grid-cols-3');
                }
            }
        };

        window.updateTimerBidsVisibility = function() {
            const panel = document.getElementById('trade-execution-panel');
            const bidsContainer = document.getElementById('timer-bids-container');
            if (!bidsContainer) return;
            const isHidden = (panel && (panel.style.display === 'none' || window.getComputedStyle(panel).display === 'none')) || (localStorage.getItem('showTradeExecutionPanel') === 'false');
            if (isHidden) {
                bidsContainer.classList.remove('hidden');
                bidsContainer.classList.add('flex');
                bidsContainer.style.display = 'flex';
            } else {
                bidsContainer.classList.add('hidden');
                bidsContainer.classList.remove('flex');
                bidsContainer.style.display = 'none';
            }
        };

        window.toggleTradeExecutionPanel = function(explicitVal) {
            let showPanel;
            if (typeof explicitVal === 'boolean') {
                showPanel = explicitVal;
            } else {
                const toggle = document.getElementById('show-trade-panel-toggle') || document.getElementById('show-trade-panel-toggle-chart');
                showPanel = toggle ? toggle.checked : true;
            }

            const toggle1 = document.getElementById('show-trade-panel-toggle');
            if (toggle1) toggle1.checked = showPanel;
            const toggle2 = document.getElementById('show-trade-panel-toggle-chart');
            if (toggle2) toggle2.checked = showPanel;
            const toggle3 = document.getElementById('toggle-trade-exec-panel');
            if (toggle3) toggle3.checked = showPanel;

            const panel = document.getElementById('trade-execution-panel');
            if (panel) panel.style.display = showPanel ? 'block' : 'none';
            localStorage.setItem('showTradeExecutionPanel', showPanel ? 'true' : 'false');
            
            updateTimerBidsVisibility();
            if (typeof updatePositionScannerCloseButton === 'function') updatePositionScannerCloseButton();
            if (typeof showToast === 'function') {
                showToast(`Trade Execution Panel ${showPanel ? 'Enabled' : 'Hidden'}`, 'info', 2000);
            }
        };

        window.toggleSound = function(explicitVal) {
            if (typeof explicitVal === 'boolean') {
                soundEngine.enabled = explicitVal;
            } else {
                soundEngine.enabled = !soundEngine.enabled;
            }
            localStorage.setItem('sound_enabled', soundEngine.enabled ? 'true' : 'false');
            syncSoundSettingsUI();
            if (soundEngine.enabled) {
                soundEngine.init();
                soundEngine.play('order_fill');
            }
            showToast(soundEngine.enabled ? 'Sound FX Enabled 🔊' : 'Sound FX Muted 🔇', 'info', 2000);
        };

        // Dynamic Island settings toggle
        window.toggleDynamicIslandSetting = function(enabled) {
            window._dynamicIslandEnabled = enabled;
            localStorage.setItem('di_enabled', enabled ? 'true' : 'false');
            const badge = document.getElementById('di-status-badge');
            if (badge) {
                badge.textContent = enabled ? 'ON' : 'OFF';
                badge.className = enabled ? 'text-[9px] font-bold text-emerald-400 uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';
            }
            if (enabled) {
                const headerToggle = document.getElementById('header-auto-toggle');
                const isAutoOn = headerToggle ? headerToggle.checked : false;
                if (typeof updateDynamicIsland === 'function') updateDynamicIsland(isAutoOn);
            } else {
                const pill = document.getElementById('dynamic-island-pill');
                if (pill) pill.style.opacity = '0';
            }
            showToast(enabled ? 'Dynamic Island Glow ON 🏝️' : 'Dynamic Island Glow OFF', 'info', 2000);
        };

        // ── Toast Notifications & Non-blocking Confirm Modal (Audit Item 2) ──
        window.showToast = function(msg, type = 'info', duration = 3500) {
            let container = document.getElementById('toast-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'toast-container';
                container.className = 'fixed top-16 right-4 z-[9999] flex flex-col gap-2 pointer-events-none max-w-sm w-full';
                document.body.appendChild(container);
            }

            const toast = document.createElement('div');
            toast.className = 'pointer-events-auto flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl border backdrop-blur-xl shadow-xl transition-all duration-300 transform translate-x-12 opacity-0 text-xs font-mono font-bold';
            
            let border = 'border-blue-500/40 bg-[#0c0c10]/95 text-blue-300';
            let icon = '⚡';
            if (type === 'success') {
                border = 'border-emerald-500/50 bg-[#061810]/95 text-emerald-300 shadow-[0_0_20px_rgba(16,185,129,0.2)]';
                icon = '✅';
            } else if (type === 'error') {
                border = 'border-rose-500/50 bg-[#1e0a0d]/95 text-rose-300 shadow-[0_0_20px_rgba(244,63,94,0.2)]';
                icon = '❌';
            } else if (type === 'warn') {
                border = 'border-amber-500/50 bg-[#1c1404]/95 text-amber-300';
                icon = '⚠️';
            }
            toast.className += ' ' + border;
            toast.innerHTML = `<span class="text-sm shrink-0">${icon}</span><span class="flex-1 leading-snug break-words">${msg}</span>`;
            container.appendChild(toast);

            requestAnimationFrame(() => {
                toast.classList.remove('translate-x-12', 'opacity-0');
                toast.classList.add('translate-x-0', 'opacity-100');
            });

            setTimeout(() => {
                toast.classList.add('translate-x-12', 'opacity-0');
                setTimeout(() => toast.remove(), 300);
            }, duration);
        };

        window.alert = function(msg) {
            window.showToast(msg, 'info');
        };

        window.showConfirmDialog = function({ title, message, confirmText = 'Confirm', cancelText = 'Cancel', onConfirm }) {
            let modal = document.getElementById('custom-confirm-modal');
            if (!modal) {
                modal = document.createElement('div');
                modal.id = 'custom-confirm-modal';
                modal.className = 'fixed inset-0 z-[10000] bg-black/80  flex items-center justify-center p-4 transition-opacity';
                document.body.appendChild(modal);
            }
            modal.innerHTML = `
                <div class="bg-[#0c0c10] border border-kalshi-border rounded-2xl max-w-sm w-full p-5 shadow-2xl space-y-4 animate-scale-up">
                    <div class="flex items-center gap-2 text-white font-bold text-sm uppercase tracking-wider">
                        <span>⚠️</span> <span>${title || 'Confirm Action'}</span>
                    </div>
                    <p class="text-xs text-gray-300 leading-relaxed font-sans">${message}</p>
                    <div class="grid grid-cols-2 gap-2.5 pt-1">
                        <button id="confirm-modal-cancel" class="py-2.5 px-4 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-xl text-xs font-bold uppercase tracking-wider transition-all active:scale-95 cursor-pointer">${cancelText}</button>
                        <button id="confirm-modal-ok" class="py-2.5 px-4 bg-kalshi-blue hover:bg-blue-600 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-all active:scale-95 shadow-md cursor-pointer">${confirmText}</button>
                    </div>
                </div>
            `;
            modal.classList.remove('hidden');

            document.getElementById('confirm-modal-cancel').onclick = () => {
                modal.classList.add('hidden');
            };
            document.getElementById('confirm-modal-ok').onclick = () => {
                modal.classList.add('hidden');
                if (typeof onConfirm === 'function') onConfirm();
            };
        };

        // ── Floating Emoji Particle Emitter (Feature 4) ──
        window.triggerFloatingEmoji = function(emoji) {
            for (let i = 0; i < 6; i++) {
                const particle = document.createElement('div');
                particle.textContent = emoji;
                particle.className = 'fixed pointer-events-none z-[9999] select-none text-2xl transition-all';
                const startX = Math.random() * (window.innerWidth - 60) + 30;
                const startY = window.innerHeight - 80;
                particle.style.left = startX + 'px';
                particle.style.top = startY + 'px';
                particle.style.opacity = '1';
                particle.style.transform = `scale(0.5) rotate(${Math.random() * 40 - 20}deg)`;
                document.body.appendChild(particle);

                const dur = 1200 + Math.random() * 800;
                const drift = (Math.random() - 0.5) * 120;
                const endY = startY - 260 - Math.random() * 150;

                particle.animate([
                    { transform: `scale(0.6) translate(0, 0)`, opacity: 1 },
                    { transform: `scale(1.3) translate(${drift}px, ${endY - startY}px)`, opacity: 0 }
                ], {
                    duration: dur,
                    easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)'
                }).onfinish = () => particle.remove();
            }
        };

        async function setTradingMode(mode) {
            const userTok = localStorage.getItem('saas_token') || (typeof token !== 'undefined' ? token : '');
            try {
                const res = await fetch((window.API_BASE_URL||'')+'/api/auth/trade/config', {
                    method: "POST",
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${userTok}` },
                    body: JSON.stringify({ mode: mode })
                });
                if(res.ok) {
                    currentMode = mode;
                    updateModeUI();
                    if (typeof showToast === 'function') {
                        showToast(`Switched to ${mode} mode 🔥`, mode === 'LIVE' ? 'warning' : 'success', 2000);
                    }
                    loadDashboard();
                } else {
                    const data = await res.json();
                    alert(data.detail || "Failed to switch mode");
                }
            } catch(e) {
                alert("Network error updating mode");
            }
        }

        window.toggleTradingMode = function() {
            setTradingMode(currentMode === 'LIVE' ? 'PAPER' : 'LIVE');
        };

        function updateModeUI() {
            const dpMode = document.getElementById('dropdown-mode-badge');
            if (dpMode) {
                dpMode.textContent = currentMode;
                dpMode.className = currentMode === 'LIVE' 
                    ? 'px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/40 text-[9px] font-bold uppercase tracking-widest cursor-pointer hover:scale-105 transition-all' 
                    : 'px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 text-[9px] font-bold uppercase tracking-widest cursor-pointer hover:scale-105 transition-all';
            }
            
            const execMode = document.getElementById('exec-mode-badge');
            if (execMode) {
                execMode.textContent = currentMode;
                execMode.className = currentMode === 'LIVE' 
                    ? 'px-1.5 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest bg-red-500/20 text-red-300 border border-red-500/40 leading-none shadow-sm cursor-pointer hover:scale-105 transition-all' 
                    : 'px-1.5 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 leading-none shadow-sm cursor-pointer hover:scale-105 transition-all';
            }

            const stText = document.getElementById('settings-mode-text');
            const btnPaper = document.getElementById('btn-mode-paper-settings');
            const btnLive = document.getElementById('btn-mode-live-settings');

            if (stText) {
                stText.textContent = currentMode;
                stText.className = currentMode === 'LIVE' 
                    ? 'text-[9px] font-bold text-red-400 uppercase tracking-widest' 
                    : 'text-[9px] font-bold text-cyan-400 uppercase tracking-widest';
            }
            if (btnPaper && btnLive) {
                if (currentMode === 'LIVE') {
                    btnLive.className = 'flex-1 py-2 text-[11px] font-bold tracking-wider rounded-lg transition-all z-10 text-white bg-red-500/25 border border-red-500/40 shadow-sm flex items-center justify-center gap-1.5 cursor-pointer';
                    btnPaper.className = 'flex-1 py-2 text-[11px] font-bold tracking-wider rounded-lg transition-all z-10 text-gray-400 hover:text-white border border-transparent flex items-center justify-center gap-1.5 cursor-pointer';
                } else {
                    btnPaper.className = 'flex-1 py-2 text-[11px] font-bold tracking-wider rounded-lg transition-all z-10 text-white bg-cyan-500/25 border border-cyan-500/40 shadow-sm flex items-center justify-center gap-1.5 cursor-pointer';
                    btnLive.className = 'flex-1 py-2 text-[11px] font-bold tracking-wider rounded-lg transition-all z-10 text-gray-400 hover:text-white border border-transparent flex items-center justify-center gap-1.5 cursor-pointer';
                }
            }
        }

        
        async function closeAllTrades() {
            const toggleEl = document.getElementById('one-click-toggle');
            const oneClick = toggleEl ? toggleEl.checked : false;
            
            const doAction = async () => {
                try {
                    const res = await fetch((window.API_BASE_URL||'')+'/api/auth/trade/close_all', {
                        method: 'POST',
                        headers: { 'Authorization': 'Bearer ' + token }
                    });
                    const data = await res.json();
                    if (res.ok && data.success) {
                        soundEngine.play('order_fill');
                        showToast('All open positions closed successfully.', 'success');
                        loadDashboard();
                    } else {
                        showToast('Failed to close trades: ' + (data.error || data.detail || 'Unknown error'), 'error');
                    }
                } catch(e) {
                    showToast('Network error closing trades: ' + e.message, 'error');
                }
            };

            if (!oneClick) {
                showConfirmDialog({
                    title: 'Close All Trades',
                    message: 'Are you sure you want to close all open positions immediately at current market bids?',
                    confirmText: 'Close All',
                    onConfirm: doAction
                });
            } else {
                await doAction();
            }
        }

        async function executeManualTrade(direction, overrideAsset = null) {
            const sizeEl = document.getElementById('trade-size-dollars');
            const amt = parseFloat(sizeEl && sizeEl.value ? sizeEl.value : 5.0) || 5.0;
            const toggleEl = document.getElementById('one-click-toggle');
            const oneClick = toggleEl ? toggleEl.checked : false;
            
            const doAction = async () => {
                try {
                    const payload = { direction: direction, amount_dollars: parseFloat(amt) ,
                min_sports_confidence: document.getElementById('sports-conf-slider') ? parseInt(document.getElementById('sports-conf-slider').value) : 70,
                min_sports_edge: document.getElementById('sports-edge-slider') ? parseInt(document.getElementById('sports-edge-slider').value) : 3,
                sports_max_wager: document.getElementById('sports-wager-dollars') ? parseInt(document.getElementById('sports-wager-dollars').value) : 10,
                sports_include_live: document.getElementById('sports-include-live-toggle') ? document.getElementById('sports-include-live-toggle').checked : false
        };
                    if (overrideAsset) payload.asset = overrideAsset;
                    const res = await fetch((window.API_BASE_URL||'')+'/api/auth/trade/manual', {
                        method: "POST",
                        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                        body: JSON.stringify(payload)
                    });
                    const data = await res.json();
                    if(res.ok && data.success) {
                        soundEngine.play('order_fill');
                        let bCount = data.count !== undefined ? data.count : (data.trade ? data.trade.count : 'contracts');
                        showToast(`Bought ${bCount} ${direction.toUpperCase()} contracts ($${amt})!`, 'success');
                        
                        // Optimistically deduct trade size from navbar balance immediately
                        const navBal = document.getElementById('nav-balance');
                        if (navBal && navBal.textContent.startsWith('$')) {
                            const cur = parseFloat(navBal.textContent.replace('$', ''));
                            if (!isNaN(cur) && cur >= amt) {
                                navBal.textContent = '$' + (cur - amt).toFixed(2);
                            }
                        }
                        
                        loadDashboard();
                    } else {
                        let _err = data.detail || data.error || 'Execution failed';
                        if (typeof _err === "object") _err = JSON.stringify(_err);
                        showToast(`Failed: ${_err}`, 'error');
                    }
                } catch(e) {
                    showToast(`Error: ${e.message || e}`, 'error');
                }
            };

            if (!oneClick) {
                showConfirmDialog({
                    title: `Execute Manual Trade (${direction.toUpperCase()})`,
                    message: `Execute $${amt} order for ${direction.toUpperCase()} in ${currentMode} mode?`,
                    confirmText: `Buy ${direction.toUpperCase()}`,
                    onConfirm: doAction
                });
            } else {
                await doAction();
            }
        }

        async function forceMLTrade() {
            const toggleEl = document.getElementById('one-click-toggle');
            const oneClick = toggleEl ? toggleEl.checked : false;
            
            const doAction = async () => {
                try {
                    const res = await fetch((window.API_BASE_URL||'')+'/api/auth/trade/force_ml', {
                        method: "POST",
                        headers: { 'Authorization': `Bearer ${token}` }
                    });
                    const data = await res.json();
                    if(res.ok && data.success) {
                        soundEngine.play('order_fill');
                        showToast(`Success! AI executed ${data.side} trade for ${data.count} contracts.`, 'success');
                        loadDashboard();
                    } else {
                        let _err = data.detail || data.error || 'Force AI failed';
                        if (typeof _err === "object") _err = JSON.stringify(_err);
                        showToast(`Failed: ${_err}`, 'error');
                    }
                } catch(e) {
                    showToast(`Error: ${e.message || e}`, 'error');
                }
            };

            if (!oneClick) {
                showConfirmDialog({
                    title: 'Force AI Signal',
                    message: `Force immediate entry following the AI's current signal in ${currentMode} mode?`,
                    confirmText: 'Force Entry',
                    onConfirm: doAction
                });
            } else {
                await doAction();
            }
        }

        async function reverseTrade() {
            const toggleEl = document.getElementById('one-click-toggle');
            const oneClick = toggleEl ? toggleEl.checked : false;

            const doAction = async () => {
                try {
                    const res = await fetch((window.API_BASE_URL||'')+'/api/auth/trade/reverse', {
                        method: "POST",
                        headers: { 'Authorization': `Bearer ${token}` }
                    });
                    const data = await res.json();
                    if(res.ok && data.success) {
                        soundEngine.play('reverse');
                        showToast(`Position reversed! Opened ${data.count} ${data.side} contracts.`, 'success');
                        loadDashboard();
                    } else {
                        let _err = data.detail || data.error || 'Reverse failed';
                        if (typeof _err === "object") _err = JSON.stringify(_err);
                        showToast(`Failed: ${_err}`, 'error');
                    }
                } catch(e) {
                    showToast(`Error: ${e.message || e}`, 'error');
                }
            };

            if (!oneClick) {
                showConfirmDialog({
                    title: 'Reverse Position',
                    message: `Close your current position and instantly flip to the opposite side in ${currentMode} mode?`,
                    confirmText: 'Reverse Now',
                    onConfirm: doAction
                });
            } else {
                await doAction();
            }
        }

        async function toggleAutoTrader(enabled) {
            try {
                const headerToggle = document.getElementById('header-auto-toggle');
                if (headerToggle) headerToggle.checked = enabled;

                const navAutoBadge = document.getElementById('nav-auto-badge');
                if (navAutoBadge) {
                    navAutoBadge.innerHTML = enabled ? '<span class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>AUTO ON</span>' : 'AUTO OFF';
                    navAutoBadge.className = enabled
                        ? 'px-1.5 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 leading-none shadow-sm'
                        : 'px-1.5 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest bg-gray-800 text-gray-400 border border-gray-700 leading-none shadow-sm';
                }

                // Update Dynamic Island
                if (typeof updateDynamicIsland === 'function') updateDynamicIsland(enabled);

                const inSports = (window.currentUniverse === 'SPORTS');
                let targetAsset = inSports ? 'SPORTS' : ((window.currentAsset || 'BTC').toLowerCase());
                targetAsset = encodeURIComponent(String(targetAsset).replace(/\//g, '_'));
                const userTok = localStorage.getItem('saas_token') || (typeof token !== 'undefined' ? token : null);
                const reqHeaders = {};
                if (userTok) reqHeaders['Authorization'] = `Bearer ${userTok}`;
                const uidVal = (window.lastDashboardStats && window.lastDashboardStats.user_id) || (window.currentUser && window.currentUser.id);
                if (uidVal) reqHeaders['X-User-Id'] = String(uidVal);

                const res = await fetch(`${window.API_BASE_URL||''}/api/engine/${targetAsset}/trade/toggle?enabled=${enabled}`, {
                    method: "POST",
                    headers: reqHeaders
                });
                if(!res.ok) {
                    const errData = await res.json().catch(() => ({}));
                    console.error("Failed toggle response:", res.status, errData);
                    throw new Error(errData.detail || errData.error || `HTTP ${res.status}`);
                }
                const confHeaders = { 'Content-Type': 'application/json' };
                if (userTok) confHeaders['Authorization'] = `Bearer ${userTok}`;
                if (uidVal) confHeaders['X-User-Id'] = String(uidVal);
                fetch(`${window.API_BASE_URL||''}/api/auth/user/config`, {
                    method: "POST",
                    headers: confHeaders,
                    body: JSON.stringify({ ai_enabled: enabled })
                }).catch(e => console.warn('Could not persist auto toggle config:', e));

                if (typeof showToast === 'function') {
                    showToast(enabled ? (inSports ? '🏈 Auto-Trading Active (Sports Universe)' : '⚡ Auto-Trading Active') : '⏸ Auto-Trading Paused', enabled ? 'success' : 'info');
                }
            } catch(e) {
                console.error("Toggle error:", e);
                if (typeof showToast === 'function') {
                    showToast(`⚠️ Failed to toggle auto-trading${e.message ? ': ' + e.message : ''}`, 'error');
                }
                // Revert on failure
                loadConfig();
            }
        }

        async function placeManualTrade(direction) {
            const toggleEl = document.getElementById('one-click-toggle');
            const oneClick = toggleEl ? toggleEl.checked : false;
            const size = document.getElementById('trade-size-dollars').value || 50;
            if(!oneClick && !confirm(`Place a manual ${direction} order for $${size}?`)) return;
            
            try {
                const curA = (window.currentAsset || 'BTC').toLowerCase();
                const res = await fetch(`${window.API_BASE_URL||''}/api/engine/${curA}/trade/manual?direction=${direction}&lots=${size}`, {
                    method: "POST",
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                let data = {}; try { data = await res.json(); } catch(e){} if(res.ok || data.success) {
                    if(!oneClick) alert(`Success! Placed ${direction} trade.`);
                    loadDashboard();
                } else {
                    let _err = data.detail || data.error; if (typeof _err === "object") _err = JSON.stringify(_err); alert(`Failed: ${_err}`);
                }
            } catch(e) {
                alert(`Error: ${e}`);
            }
        }

        async function showSettingsToast(msg, type) {
            let t = document.getElementById('settings-toast');
            if (!t) {
                t = document.createElement('div');
                t.id = 'settings-toast';
                t.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);z-index:9999;padding:8px 18px;border-radius:12px;font-size:11px;font-weight:700;transition:opacity 0.4s ease;pointer-events:none;white-space:nowrap;';
                document.body.appendChild(t);
            }
            t.textContent = msg;
            t.style.background = type === 'error' ? 'rgba(220,38,38,0.95)' : 'rgba(16,185,129,0.95)';
            t.style.color = '#fff';
            t.style.opacity = '1';
            clearTimeout(window._toastTimer);
            window._toastTimer = setTimeout(() => { t.style.opacity = '0'; }, type === 'error' ? 4000 : 2000);

            const badge = document.getElementById('settings-status-badge');
            if (badge) {
                if (type === 'error') {
                    badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span>Error Saving';
                    badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-rose-500/15 text-rose-400 border border-rose-500/30 flex items-center gap-1';
                } else {
                    badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>Saved ✓';
                    badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center gap-1';
                    setTimeout(() => {
                        if (badge) {
                            badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>Auto-Saved';
                            badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1';
                        }
                    }, 2000);
                }
            }
        }

        async function saveUserConfig() {
            // Read raw values with fallback defaults
            const sizeRaw  = document.getElementById('trade-size-dollars')?.value || '';
            const slRaw    = document.getElementById('stop-loss-pct')?.value || '';
            const tpRaw    = document.getElementById('take-profit-pct')?.value || '';
            const mdtRaw   = document.getElementById('max-daily-trades')?.value || '';
            const mdrRaw   = document.getElementById('max-daily-risk')?.value || '';
            const tsActRaw = document.getElementById('trailing-stop-activation-pct')?.value || '';
            const tsDistRaw= document.getElementById('trailing-stop-distance-pct')?.value || '';

            const size  = !isNaN(parseFloat(sizeRaw)) ? parseFloat(sizeRaw) : 25.0;
            const sl    = !isNaN(parseFloat(slRaw)) ? parseFloat(slRaw) : 15.0;
            const tp    = !isNaN(parseFloat(tpRaw)) ? parseFloat(tpRaw) : 10.0;
            const mdt   = !isNaN(parseInt(mdtRaw)) ? parseInt(mdtRaw) : 50;
            const mdr   = !isNaN(parseFloat(mdrRaw)) ? parseFloat(mdrRaw) : 100.0;
            const tsAct = !isNaN(parseFloat(tsActRaw)) ? parseFloat(tsActRaw) : 35.0;
            const tsDist= !isNaN(parseFloat(tsDistRaw)) ? parseFloat(tsDistRaw) : 6.0;

            const forceEl   = document.getElementById('force-trade-toggle');
            const autoForce = forceEl ? forceEl.checked : false;

            const techEl    = document.getElementById('technical-force-toggle');
            const techForce = techEl ? techEl.checked : false;

            const oneshotEl = document.getElementById('one-shot-toggle');
            const oneshot   = oneshotEl ? oneshotEl.checked : false;

            const tsToggle  = document.getElementById('trailing-stop-toggle');
            const tsEnabled = tsToggle ? tsToggle.checked : false;
            const tsText = document.getElementById('trailing-stop-text');
            if (tsText) {
                tsText.innerText = tsEnabled ? 'ON' : 'OFF';
                tsText.className = tsEnabled ? 'text-[9px] font-bold text-emerald-400 uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';
            }

            const tStyle      = document.getElementById('trading-style')?.value      || 'AUTO';
            const sSource     = document.getElementById('signal-source')?.value      || 'BLEND';
            const modelChoice = document.getElementById('model-choice')?.value       || 'Swarm';

            const trainWindowRaw = document.getElementById('train-window')?.value || '';
            const regCRaw        = document.getElementById('reg-c')?.value || '';
            const xgbEstRaw      = document.getElementById('xgb-estimators')?.value || '';
            const xgbDepthRaw    = document.getElementById('xgb-max-depth')?.value || '';
            const xgbLRRaw       = document.getElementById('xgb-learning-rate')?.value || '';

            const trainWindow = parseInt(trainWindowRaw)   || 4000;
            const regC        = parseFloat(regCRaw)        || 0.5;
            const cWeight     = document.getElementById('class-weight')?.value || 'balanced';
            const xgbEst      = parseInt(xgbEstRaw)        || 300;
            const xgbDepth    = parseInt(xgbDepthRaw)      || 5;

            const xgbLR       = parseFloat(xgbLRRaw)       || 0.1;

            const activeAssets = [];
            document.querySelectorAll('input.asset-toggle').forEach(t => {
                const v = String(t.value).toUpperCase();
                if (t.checked && !activeAssets.includes(v)) activeAssets.push(v);
            });
            const targetAssetStr = activeAssets.length > 0 ? activeAssets.join(',') : 'BTC';

            // Collect active sports leagues
            const activeSportsLeagues = [];
            document.querySelectorAll('input.sports-league-toggle').forEach(t => {
                const v = String(t.value).trim().toUpperCase();
                if (t.checked && !activeSportsLeagues.includes(v)) activeSportsLeagues.push(v);
            });
            const sportsActiveLeaguesStr = activeSportsLeagues.length > 0 ? activeSportsLeagues.join(',') : 'NFL,MLB,NPB/KBO,SOC,UFC,TEN,NHL';

            // Collect allowed sports market types
            const activeSportsMarketTypes = [];
            document.querySelectorAll('input.sports-market-toggle').forEach(t => {
                const v = String(t.value).trim().toUpperCase();
                if (t.checked && !activeSportsMarketTypes.includes(v)) activeSportsMarketTypes.push(v);
            });
            const sportsMarketTypesStr = activeSportsMarketTypes.length > 0 ? activeSportsMarketTypes.join(',') : 'GAME,SPREAD,TOTAL,PROP,INNING';

            // Parse price corridor (min/max ¢ as dollars 0.01 - 0.99)
            let sMinPrice = parseFloat(document.getElementById('sports-min-price')?.value || 20);
            if (sMinPrice > 1.0) sMinPrice = sMinPrice / 100.0;
            let sMaxPrice = parseFloat(document.getElementById('sports-max-price')?.value || 80);
            if (sMaxPrice > 1.0) sMaxPrice = sMaxPrice / 100.0;

            try {
                const configPayload = {
                    trade_size_dollars: size,
                    paper_trade_size_dollars: parseFloat(document.getElementById('paper-trade-size-dollars')?.value || size),
                    stop_loss_pct: sl,
                    stop_loss_enabled: document.getElementById('stop-loss-toggle') ? document.getElementById('stop-loss-toggle').checked : true,
                    take_profit_pct: tp,
                    take_profit_enabled: document.getElementById('take-profit-toggle') ? document.getElementById('take-profit-toggle').checked : true,
                    max_daily_trades: mdt,
                    max_daily_risk: mdr,
                    one_click_trade: document.getElementById('one-click-toggle') ? document.getElementById('one-click-toggle').checked : false,
                    auto_force_trade: autoForce,
                    ignore_pass_technical: techForce,
                    one_shot_ai: oneshot,
                    second_entry_enabled: document.getElementById('second-entry-toggle') ? document.getElementById('second-entry-toggle').checked : false,
                    second_entry_max_ask: (parseFloat(document.getElementById('second-entry-max-ask')?.value || 75) > 1) ? (parseFloat(document.getElementById('second-entry-max-ask')?.value || 75) / 100) : parseFloat(document.getElementById('second-entry-max-ask')?.value || 0.75),
                    reentry_after_stop_loss: document.getElementById('reentry-after-stoploss-toggle') ? document.getElementById('reentry-after-stoploss-toggle').checked : false,
                    edge_gate_enabled: document.getElementById('edge-gate-toggle') ? document.getElementById('edge-gate-toggle').checked : false,
                    min_edge_cents: parseFloat(document.getElementById('min-edge-cents')?.value || 5.0),
                    target_asset: targetAssetStr,
                    trading_style: tStyle,
                    signal_source: sSource,
                    trailing_stop_enabled: tsEnabled,
                    trailing_stop_activation_pct: tsAct,
                    trailing_stop_distance_pct: tsDist,
                    model_choice: modelChoice,
                    train_window: trainWindow,
                    regularization_c: regC,
                    class_weight: cWeight,
                    xgb_estimators: xgbEst,
                    xgb_max_depth: xgbDepth,
                    xgb_learning_rate: xgbLR,
                    use_kelly_criterion: document.getElementById('kelly-criterion-toggle') ? document.getElementById('kelly-criterion-toggle').checked : false,
                    atr_risk_enabled: document.getElementById('atr-risk-toggle') ? document.getElementById('atr-risk-toggle').checked : false,
                    trading_universe: (window.configuredTradingUniverse === 'CRYPTO' ? 'FINANCIAL' : (window.configuredTradingUniverse || (window.lastDashboardStats && window.lastDashboardStats.trading_universe) || 'FINANCIAL')),
                    min_sports_confidence: document.getElementById('sports-conf-slider') ? parseFloat(document.getElementById('sports-conf-slider').value) : 70.0,
                    min_sports_edge: document.getElementById('sports-edge-slider') ? parseFloat(document.getElementById('sports-edge-slider').value) : 3.0,
                    sports_max_wager: parseFloat(document.getElementById('sports-trade-size-dollars')?.value || document.getElementById('sports-wager-dollars')?.value || 10.0),
                    sports_trade_size_dollars: parseFloat(document.getElementById('sports-trade-size-dollars')?.value || document.getElementById('sports-wager-dollars')?.value || 10.0),
                    sports_include_live: document.getElementById('sports-include-live-toggle') ? document.getElementById('sports-include-live-toggle').checked : false,
                    sports_active_leagues: sportsActiveLeaguesStr,
                    sports_min_price: sMinPrice,
                    sports_max_price: sMaxPrice,
                    sports_max_daily_trades: parseInt(document.getElementById('sports-max-daily-trades')?.value || 10),
                    sports_max_open_trades: parseInt(document.getElementById('sports-max-open-trades')?.value || 5),
                    sports_max_daily_risk: parseFloat(document.getElementById('sports-max-daily-risk')?.value || 100.0),
                    sports_tp_enabled: document.getElementById('sports-tp-toggle') ? document.getElementById('sports-tp-toggle').checked : false,
                    sports_tp_pct: parseFloat(document.getElementById('sports-tp-pct')?.value || 35.0),
                    sports_use_kelly: document.getElementById('sports-kelly-toggle') ? document.getElementById('sports-kelly-toggle').checked : false,
                    sports_market_types: sportsMarketTypesStr
                };

                // Immediately update local cache so background polling doesn't fight this
                if (window.lastDashboardStats) {
                    Object.assign(window.lastDashboardStats, configPayload);
                }
                if (typeof renderTradeSlip === 'function' && window.sportsTradeSlip && window.sportsTradeSlip.length > 0) {
                    renderTradeSlip();
                }

                const res = await fetch((window.API_BASE_URL||'')+'/api/auth/user/config', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify(configPayload)
                });
                
                

                if (res.ok) {
                    showSettingsToast('✓ Settings saved', 'success');
                } else {
                    let errData = {};
                    try { errData = await res.json(); } catch(_) {}
                    const detail = typeof errData.detail === 'object' ? JSON.stringify(errData.detail) : (errData.detail || errData.error || `HTTP ${res.status}`);
                    showSettingsToast(`⚠️ ${detail}`, 'error');
                }
            } catch(e) {
                showSettingsToast(`⚠️ Network error — check connection`, 'error');
            }
        }
        window.saveConfig = saveUserConfig;

        async function saveKeys() {
            const keyId = document.getElementById('kalshi-key').value;
            const privKey = document.getElementById('kalshi-priv').value;
            if(!keyId || !privKey) return alert("Please fill both key fields.");
            try {
                const res = await fetch((window.API_BASE_URL||'')+'/api/auth/keys', {
                    method: "POST",
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                    body: JSON.stringify({ key_id: keyId, private_key: privKey })
                });
                if(res.ok) {
                    alert("Keys saved securely.");
                    document.getElementById('kalshi-key').value = '';
                    document.getElementById('kalshi-priv').value = '';
                } else {
                    let errorData = {}; try { errorData = await res.json(); } catch(e){} 
                    let _err = errorData.detail || 'Unknown error'; if (typeof _err === "object") _err = JSON.stringify(_err); alert(`Failed to save keys: ${_err}`);
                }
            } catch(e) {
                alert(`Error saving keys: ${e}`);
            }
        }

        function fillMLCard(lastMLData, fullData) {
            if(!lastMLData) return;
            const pb = document.getElementById('popup-bias');
            if (pb) pb.innerText = lastMLData.primary_bias || '--';
            const pc = document.getElementById('popup-conf');
            if (pc) pc.innerText = `${lastMLData.confidence_percent || 0}%`;
            
            // Use the actual AI ML predicted probability, fallback to Kalshi yes_prob if ML is unavailable
            const prob = (lastMLData && lastMLData.predicted_probability != null) 
                ? lastMLData.predicted_probability * 100 
                : ((fullData && fullData.yes_prob != null) ? fullData.yes_prob : 0);
            const pp = document.getElementById('popup-prob');
            if (pp) pp.innerText = `${parseFloat(prob).toFixed(1)}%`;
            
            let confColor = 'text-gray-400';
            if(lastMLData.confidence_percent >= 60) confColor = 'text-kalshi-green';
            else if(lastMLData.confidence_percent <= 40) confColor = 'text-kalshi-red';
            if (pc) pc.className = `text-xs font-black ${confColor}`;
            
            let summaryText = lastMLData.summary ? lastMLData.summary : `Model predicts ${lastMLData.primary_bias} with ${parseFloat(prob).toFixed(1)}% YES probability.`;
            const ps = document.getElementById('popup-summary');
            if (ps) ps.innerText = summaryText;
        }

        async function loadConfig() {
            try {
                const inSports = (window.currentUniverse === 'SPORTS');
                const curA = inSports ? 'sports' : (window.currentAsset || 'BTC').toLowerCase();
                const res = await fetch(`${window.API_BASE_URL||''}/api/engine/${curA}/trade/config`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if(res.ok) {
                    const c = await res.json();
                    
                    if(c.enabled !== undefined) {
                        const headerToggle = document.getElementById('header-auto-toggle');
                        if(headerToggle) headerToggle.checked = c.enabled;
                        
                        const navAutoBadge = document.getElementById('nav-auto-badge');
                        if(navAutoBadge) {
                            navAutoBadge.innerHTML = c.enabled ? '<span class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>AUTO ON</span>' : 'AUTO OFF';
                            navAutoBadge.className = c.enabled ? 'px-1.5 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 leading-none shadow-sm' : 'px-1.5 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest bg-gray-800 text-gray-400 border border-gray-700 leading-none shadow-sm';
                        }
                        // Sync Dynamic Island glow with server state
                        if (typeof updateDynamicIsland === 'function') updateDynamicIsland(c.enabled);
                    }
                }
            } catch(e) {}
        }

        
        let knownOpenTrades = new Set();

        var knownCompletedTrades = new Set();
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
            requestAnimationFrame(() => requestAnimationFrame(() => toast.classList.remove('translate-y-[-150%]', 'opacity-0')));
            setTimeout(() => {
                toast.classList.add('translate-y-[-150%]', 'opacity-0');
                setTimeout(() => toast.remove(), 500);
            }, 5000);
            try { if(type === "success" && window.soundEngine) window.soundEngine.play('order_fill'); } catch(e){}
        }


        var knownCompletedTrades = new Set();
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
            requestAnimationFrame(() => requestAnimationFrame(() => toast.classList.remove('translate-y-[-150%]', 'opacity-0')));
            setTimeout(() => {
                toast.classList.add('translate-y-[-150%]', 'opacity-0');
                setTimeout(() => toast.remove(), 500);
            }, 5000);
            try { if(type === "success" && window.soundEngine) window.soundEngine.play('order_fill'); } catch(e){}
        }


        var knownCompletedTrades = new Set();
        window.enableIosNotifications = localStorage.getItem("enableIosNotifications") !== "false";

        window.toggleIosNotifications = function(checked) {
            window.enableIosNotifications = checked;
            localStorage.setItem("enableIosNotifications", checked);
            if (checked && "Notification" in window && Notification.permission !== "granted" && Notification.permission !== "denied") {
                Notification.requestPermission().then(permission => {
                    if (permission === "granted") {
                        new Notification("ShadowTrade AI", { body: "System notifications are now active. You will receive alerts on your lockscreen." });
                        if (typeof showToast === "function") showToast("System notifications enabled!", "success");
                    }
                });
            }
        };

        window.iosNotify = function(title, subtitle, type="success") {
            if (!window.enableIosNotifications) return;

            if ("Notification" in window && Notification.permission === "granted") {
                try {
                    new Notification(title, { body: subtitle });
                } catch(e) {}
            }

            let container = document.getElementById('ios-notify-container');
            if(!container){
                container = document.createElement('div');
                container.id = 'ios-notify-container';
                container.className = 'fixed top-4 left-0 right-0 z-[9999] flex flex-col items-center gap-2 pointer-events-none px-4';
                document.body.appendChild(container);
            }
            requestAnimationFrame(() => requestAnimationFrame(() => toast.classList.remove('translate-y-[-150%]', 'opacity-0')));
            setTimeout(() => {
                toast.classList.add('translate-y-[-150%]', 'opacity-0');
                setTimeout(() => toast.remove(), 500);
            }, 5000);
            try { if(type === "success" && window.soundEngine) window.soundEngine.play('order_fill'); } catch(e){}
        }

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
        
        window.userSettingsPopulated = false;
        window.lastDashboardStats = null;

        function populateUserSettings(s, force = false) {
            if (!s) return;
            
            const adminGroup = document.getElementById('admin-console-group');
            if (adminGroup) {
                if (s.role === 'admin') {
                    adminGroup.classList.remove('hidden');
                    // Dynamically load admin_users.js if not already loaded
                    if (!window._adminUsersLoaded) {
                        window._adminUsersLoaded = true;
                        const script = document.createElement('script');
                        script.src = './js/admin_users.js?v=1791013020';
                        document.body.appendChild(script);
                    }
                } else {
                    adminGroup.classList.add('hidden');
                }
            }
            
            const drawer = document.getElementById('settingsDrawer');
            const isSettingsOpen = drawer && !drawer.classList.contains('hidden');
            const isFocusInSettings = drawer && drawer.contains(document.activeElement);

            // If the user has already loaded settings and the settings drawer is currently open or focused,
            // DO NOT overwrite inputs/toggles under the user's cursor unless explicitly forced!
            if (!force && window.userSettingsPopulated && (isSettingsOpen || isFocusInSettings)) {
                return;
            }

            if (s.trading_mode) {
                currentMode = s.trading_mode;
                if (typeof updateModeUI === 'function') updateModeUI();
            }

            if (s.trade_size_dollars !== undefined && document.getElementById('trade-size-dollars')) {
                if (document.activeElement.id !== 'trade-size-dollars') {
                    document.getElementById('trade-size-dollars').value = s.trade_size_dollars;
                }
            }
            // Dynamic ATR Risk Management toggle (server-backed, default OFF)
            const atrToggle = document.getElementById('atr-risk-toggle');
            if (atrToggle && s.atr_risk_enabled !== undefined) {
                atrToggle.checked = !!s.atr_risk_enabled;
                if (typeof refreshAtrReadout === 'function') refreshAtrReadout();
            }
            // Populate Kelly Criterion toggle from user settings, defaulting strictly to false (OFF)
            const kellyToggle = document.getElementById('kelly-criterion-toggle');
            if (kellyToggle) {
                if (s.use_kelly_criterion !== undefined) {
                    kellyToggle.checked = !!s.use_kelly_criterion;
                } else {
                    try {
                        const aiSetStr = localStorage.getItem("kalshiAiSettings");
                        if (aiSetStr) {
                            const aiSet = JSON.parse(aiSetStr);
                            kellyToggle.checked = !!aiSet.useKellyCriterion;
                        } else {
                            kellyToggle.checked = false;
                        }
                    } catch(e) {
                        kellyToggle.checked = false;
                    }
                }
            }
            if (s.trading_universe !== undefined) {
                const tu = String(s.trading_universe).toUpperCase();
                if (typeof setAutoTradingUniverse === 'function') {
                    setAutoTradingUniverse(tu, true);
                }
                if (!window.currentUniverse || force) {
                    const viewTab = (tu === 'SPORTS') ? 'SPORTS' : 'FINANCIAL';
                    if (typeof selectUniverse === 'function') selectUniverse(viewTab);
                }
            }
            if (s.min_sports_confidence !== undefined && document.getElementById('sports-conf-slider')) {
                document.getElementById('sports-conf-slider').value = s.min_sports_confidence;
                if (document.getElementById('sports-conf-val')) {
                    document.getElementById('sports-conf-val').innerText = s.min_sports_confidence + '.0%';
                }
            }
            if (s.min_sports_edge !== undefined && document.getElementById('sports-edge-slider')) {
                document.getElementById('sports-edge-slider').value = s.min_sports_edge;
                if (document.getElementById('sports-edge-val')) {
                    document.getElementById('sports-edge-val').innerText = '+' + s.min_sports_edge + '.0%';
                }
            }
            const sportsSize = s.sports_trade_size_dollars !== undefined ? s.sports_trade_size_dollars : s.sports_max_wager;
            if (sportsSize !== undefined) {
                if (document.getElementById('sports-trade-size-dollars')) {
                    if (document.activeElement?.id !== 'sports-trade-size-dollars') {
                        document.getElementById('sports-trade-size-dollars').value = sportsSize;
                    }
                }
                if (document.getElementById('sports-wager-dollars')) {
                    document.getElementById('sports-wager-dollars').value = sportsSize;
                }
            }
            if (s.sports_include_live !== undefined && document.getElementById('sports-include-live-toggle')) {
                document.getElementById('sports-include-live-toggle').checked = !!s.sports_include_live;
            }
            // Sports leagues multi-select
            if (s.sports_active_leagues !== undefined) {
                const leagues = (s.sports_active_leagues || '').split(',').map(l => l.trim().toUpperCase());
                document.querySelectorAll('input.sports-league-toggle').forEach(t => {
                    t.checked = leagues.includes(String(t.value).trim().toUpperCase());
                });
            }
            // Sports market types
            if (s.sports_market_types !== undefined) {
                const mtypes = (s.sports_market_types || '').split(',').map(m => m.trim().toUpperCase());
                document.querySelectorAll('input.sports-market-toggle').forEach(t => {
                    const v = String(t.value).trim().toUpperCase();
                    t.checked = mtypes.includes(v) || (v === 'PROP' && (mtypes.includes('PLAYER_PROP') || mtypes.includes('PROPS')));
                });
            }
            // Price corridor
            if (s.sports_min_price !== undefined && document.getElementById('sports-min-price')) {
                if (document.activeElement?.id !== 'sports-min-price') {
                    const minCents = Math.round(s.sports_min_price * (s.sports_min_price <= 1.0 ? 100 : 1));
                    document.getElementById('sports-min-price').value = minCents;
                }
            }
            if (s.sports_max_price !== undefined && document.getElementById('sports-max-price')) {
                if (document.activeElement?.id !== 'sports-max-price') {
                    const maxCents = Math.round(s.sports_max_price * (s.sports_max_price <= 1.0 ? 100 : 1));
                    document.getElementById('sports-max-price').value = maxCents;
                }
            }
            // Max daily wagers & risk
            if (s.sports_max_daily_trades !== undefined && document.getElementById('sports-max-daily-trades')) {
                if (document.activeElement?.id !== 'sports-max-daily-trades') {
                    document.getElementById('sports-max-daily-trades').value = s.sports_max_daily_trades;
                }
            }
            if (s.sports_max_open_trades !== undefined && document.getElementById('sports-max-open-trades')) {
                if (document.activeElement?.id !== 'sports-max-open-trades') {
                    document.getElementById('sports-max-open-trades').value = s.sports_max_open_trades;
                }
            }
            if (s.sports_max_daily_risk !== undefined && document.getElementById('sports-max-daily-risk')) {
                if (document.activeElement?.id !== 'sports-max-daily-risk') {
                    document.getElementById('sports-max-daily-risk').value = s.sports_max_daily_risk;
                }
            }
            // Mid-game Take-Profit
            if (s.sports_tp_enabled !== undefined && document.getElementById('sports-tp-toggle')) {
                document.getElementById('sports-tp-toggle').checked = !!s.sports_tp_enabled;
            }
            if (s.sports_tp_pct !== undefined && document.getElementById('sports-tp-pct')) {
                if (document.activeElement?.id !== 'sports-tp-pct') {
                    document.getElementById('sports-tp-pct').value = s.sports_tp_pct;
                }
            }
            // Kelly Criterion
            if (s.sports_use_kelly !== undefined && document.getElementById('sports-kelly-toggle')) {
                document.getElementById('sports-kelly-toggle').checked = !!s.sports_use_kelly;
            }
            if (s.paper_trade_size_dollars !== undefined && document.getElementById('paper-trade-size-dollars')) {
                if (document.activeElement.id !== 'paper-trade-size-dollars') {
                    document.getElementById('paper-trade-size-dollars').value = s.paper_trade_size_dollars;
                }
            }
            if (s.trading_style !== undefined && document.getElementById('trading-style')) {
                const tsEl = document.getElementById('trading-style');
                if (tsEl.value !== s.trading_style) {
                    tsEl.value = s.trading_style;
                    const tsOpt = tsEl.querySelector(`option[value="${s.trading_style}"]`);
                    const tsCont = document.querySelector(`.custom-dropdown[data-target="trading-style"]`);
                    if (tsOpt && tsCont) tsCont.querySelector('.selected-text').innerHTML = tsOpt.innerHTML;
                }
            }
            if (s.signal_source !== undefined && document.getElementById('signal-source')) {
                const ssEl = document.getElementById('signal-source');
                if (ssEl.value !== s.signal_source) {
                    ssEl.value = s.signal_source;
                    const ssOpt = ssEl.querySelector(`option[value="${s.signal_source}"]`);
                    const ssCont = document.querySelector(`.custom-dropdown[data-target="signal-source"]`);
                    if (ssOpt && ssCont) ssCont.querySelector('.selected-text').innerHTML = ssOpt.innerHTML;
                }
            }
            if (s.stop_loss_pct !== undefined && document.getElementById('stop-loss-pct')) {
                if (document.activeElement.id !== 'stop-loss-pct') {
                    document.getElementById('stop-loss-pct').value = s.stop_loss_pct;
                }
            }
            if (s.stop_loss_enabled !== undefined && document.getElementById('stop-loss-toggle')) {
                document.getElementById('stop-loss-toggle').checked = !!s.stop_loss_enabled;
            }
            if (s.take_profit_pct !== undefined && document.getElementById('take-profit-pct')) {
                if (document.activeElement.id !== 'take-profit-pct') {
                    document.getElementById('take-profit-pct').value = s.take_profit_pct;
                }
            }
            if (s.take_profit_enabled !== undefined && document.getElementById('take-profit-toggle')) {
                document.getElementById('take-profit-toggle').checked = !!s.take_profit_enabled;
            }
            if (s.max_daily_trades !== undefined && document.getElementById('max-daily-trades')) {
                if (document.activeElement.id !== 'max-daily-trades') {
                    document.getElementById('max-daily-trades').value = s.max_daily_trades;
                }
            }
            if (s.max_daily_risk !== undefined && document.getElementById('max-daily-risk')) {
                if (document.activeElement.id !== 'max-daily-risk') {
                    document.getElementById('max-daily-risk').value = s.max_daily_risk;
                }
            }

            // Trailing Stop Switch & Parameters
            const tsEl = document.getElementById('trailing-stop-toggle');
            if (tsEl && s.trailing_stop_enabled !== undefined) {
                tsEl.checked = !!s.trailing_stop_enabled;
                const tsText = document.getElementById('trailing-stop-text');
                if (tsText) {
                    tsText.innerText = tsEl.checked ? 'ON' : 'OFF';
                    tsText.className = tsEl.checked ? 'text-[9px] font-bold text-emerald-400 uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';
                }
            }
            if (s.trailing_stop_activation_pct !== undefined && document.getElementById('trailing-stop-activation-pct')) {
                if (document.activeElement.id !== 'trailing-stop-activation-pct') {
                    document.getElementById('trailing-stop-activation-pct').value = s.trailing_stop_activation_pct;
                }
            }
            if (s.trailing_stop_distance_pct !== undefined && document.getElementById('trailing-stop-distance-pct')) {
                if (document.activeElement.id !== 'trailing-stop-distance-pct') {
                    document.getElementById('trailing-stop-distance-pct').value = s.trailing_stop_distance_pct;
                }
            }

            // Toggles

            if (s.target_asset !== undefined) {
                const assets = s.target_asset.split(',').map(a => a.trim().toUpperCase());
                document.querySelectorAll('input.asset-toggle').forEach(t => {
                    t.checked = assets.includes(String(t.value).toUpperCase());
                });
            }

            const oneClickEl = document.getElementById('one-click-toggle');
            if (oneClickEl && s.one_click_trade !== undefined) {
                oneClickEl.checked = !!s.one_click_trade;
                const ocText = document.getElementById('one-click-text');
                if (ocText) {
                    ocText.innerText = oneClickEl.checked ? 'ON' : 'OFF';
                    ocText.className = oneClickEl.checked ? 'text-[9px] font-bold text-kalshi-blue uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';
                }
            }
            const forceEl = document.getElementById('force-trade-toggle');
            if (forceEl && s.auto_force_trade !== undefined) {
                forceEl.checked = !!s.auto_force_trade;
                const ftText = document.getElementById('force-trade-text');
                if (ftText) {
                    ftText.innerText = forceEl.checked ? 'ON' : 'OFF';
                    ftText.className = forceEl.checked ? 'text-[9px] font-bold text-purple-400 uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';
                }
            }
            if (s.ignore_pass_technical !== undefined && document.getElementById('technical-force-toggle')) {
                document.getElementById('technical-force-toggle').checked = !!s.ignore_pass_technical;
            }
            if (s.one_shot_ai !== undefined && document.getElementById('one-shot-toggle')) {
                const oneShotEl = document.getElementById('one-shot-toggle');
                const wasChecked = oneShotEl.checked;
                oneShotEl.checked = !!s.one_shot_ai;
                if (wasChecked && !s.one_shot_ai) {
                    const headerAutoToggle = document.getElementById('header-auto-toggle');
                    const isAutoOn = headerAutoToggle ? headerAutoToggle.checked : false;
                    if (typeof updateDynamicIsland === 'function') {
                        updateDynamicIsland(isAutoOn);
                    }
                }
            }
            if (s.second_entry_enabled !== undefined && document.getElementById('second-entry-toggle')) {
                document.getElementById('second-entry-toggle').checked = !!s.second_entry_enabled;
            }
            if (s.reentry_after_stop_loss !== undefined && document.getElementById('reentry-after-stoploss-toggle')) {
                document.getElementById('reentry-after-stoploss-toggle').checked = !!s.reentry_after_stop_loss;
            }
            if (s.second_entry_max_ask !== undefined && document.getElementById('second-entry-max-ask')) {
                if (document.activeElement.id !== 'second-entry-max-ask') {
                    // Convert 0.75 to 75 for the UI
                    let val = parseFloat(s.second_entry_max_ask);
                    if (val < 1) val = Math.round(val * 100);
                    document.getElementById('second-entry-max-ask').value = val;
                }
            }

            // Model choice & ML params
            if (s.model_choice !== undefined && document.getElementById('model-choice')) {
                const mcEl = document.getElementById('model-choice');
                if (mcEl.value !== s.model_choice) {
                    mcEl.value = s.model_choice;
                    const mcOpt = mcEl.querySelector(`option[value="${s.model_choice}"]`);
                    const mcCont = document.querySelector(`.custom-dropdown[data-target="model-choice"]`);
                    if (mcOpt && mcCont) mcCont.querySelector('.selected-text').innerHTML = mcOpt.innerHTML;
                }
            }
            if (s.train_window !== undefined && document.getElementById('train-window')) {
                if (document.activeElement.id !== 'train-window') {
                    document.getElementById('train-window').value = s.train_window;
                    if (document.getElementById('train-win-val')) document.getElementById('train-win-val').innerText = s.train_window;
                }
            }
            if (s.regularization_c !== undefined && document.getElementById('reg-c')) {
                if (document.activeElement.id !== 'reg-c') {
                    document.getElementById('reg-c').value = s.regularization_c;
                }
            }
            if (s.class_weight !== undefined && document.getElementById('class-weight')) {
                const cwEl = document.getElementById('class-weight');
                if (cwEl.value !== s.class_weight) {
                    cwEl.value = s.class_weight;
                    const cwOpt = cwEl.querySelector(`option[value="${s.class_weight}"]`);
                    const cwCont = document.querySelector(`.custom-dropdown[data-target="class-weight"]`);
                    if (cwOpt && cwCont) cwCont.querySelector('.selected-text').innerHTML = cwOpt.innerHTML;
                }
            }
            if (s.xgb_estimators !== undefined && document.getElementById('xgb-estimators')) {
                if (document.activeElement.id !== 'xgb-estimators') {
                    document.getElementById('xgb-estimators').value = s.xgb_estimators;
                }
            }
            if (s.xgb_max_depth !== undefined && document.getElementById('xgb-max-depth')) {
                if (document.activeElement.id !== 'xgb-max-depth') {
                    document.getElementById('xgb-max-depth').value = s.xgb_max_depth;
                }
            }
            if (s.xgb_learning_rate !== undefined && document.getElementById('xgb-learning-rate')) {
                if (document.activeElement.id !== 'xgb-learning-rate') {
                    document.getElementById('xgb-learning-rate').value = s.xgb_learning_rate;
                }
            }
            if (s.edge_gate_enabled !== undefined && document.getElementById('edge-gate-toggle')) {
                document.getElementById('edge-gate-toggle').checked = !!s.edge_gate_enabled;
            }
            if (s.min_edge_cents !== undefined && document.getElementById('min-edge-cents')) {
                if (document.activeElement.id !== 'min-edge-cents') {
                    document.getElementById('min-edge-cents').value = s.min_edge_cents;
                }
            }

            if (typeof syncCustomDropdowns === 'function') {
                syncCustomDropdowns();
            }
            window.userSettingsPopulated = true;
        }

        async function loadDashboard() {
            if (document.hidden || !window.isTabActive) return;
            try {
                const res = await fetch((window.API_BASE_URL||'')+'/api/auth/dashboard_stats', {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if(!res.ok) {
                    if(res.status === 401) logout();
                    return;
                }
                const s = await res.json();
                
                
                
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
                                        window.iosNotify('Trade Won!', 'profit secured', 'success');
                                    } else {
                                        window.iosNotify('Trade Closed', 'loss incurred', 'error');
                                    }
                                }
                                knownCompletedTrades.add(tradeId);
                            }
                        }
                    });
                }


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
                                        window.iosNotify('Trade Won!', 'profit secured', 'success');
                                    } else {
                                        window.iosNotify('Trade Closed', 'loss incurred', 'error');
                                    }
                                }
                                knownCompletedTrades.add(tradeId);
                            }
                        }
                    });
                }


                // iOS Notifications for newly closed trades
                if (s.recent_trades && Array.isArray(s.recent_trades)) {
                    s.recent_trades.forEach(t => {
                        const status = String(t.status || '').toUpperCase();
                        const tradeId = String(t.id);
                        if (status === 'CLOSED' || status.includes('WIN') || status.includes('LOSS')) {
                            if (!knownCompletedTrades.has(tradeId)) {
                                if (!initialLoad) {
                                    const pnl = parseFloat(t.live_pnl !== undefined ? t.live_pnl : (t.pnl_dollars || t.pnl || 0));
                                    const isWin = status.includes('WIN') || pnl > 0;
                                    const assetStr = String(t.asset || t.ticker || 'Asset').toUpperCase().replace('KX', '').replace('15M', '');
                                    if (isWin) {
                                        window.iosNotify('Trade Won! 🎉', `${assetStr} profit secured: +$${pnl.toFixed(2)}`, 'success');
                                    } else {
                                        window.iosNotify('Trade Closed', `${assetStr} loss incurred: -$${Math.abs(pnl).toFixed(2)}`, 'error');
                                    }
                                }
                                knownCompletedTrades.add(tradeId);
                            }
                        }
                    });
                }

                


                if (currentMode !== s.trading_mode) {
                    currentMode = s.trading_mode || "PAPER";
                    updateModeUI();
                }

                if (s.api_configured) {
                    document.getElementById('connection-status').innerText = "SECURE";
                    document.getElementById('connection-status').className = "text-[9px] uppercase font-bold text-kalshi-green tracking-wider";
                } else {
                    document.getElementById('connection-status').innerText = "NO API KEY";
                    document.getElementById('connection-status').className = "text-[9px] uppercase font-bold text-kalshi-red tracking-wider";
                }

                if(currentMode === "PAPER") {
                    if (s.balance_dollars !== undefined && s.balance_dollars !== null) {
                        document.getElementById('val-balance').innerText = `$${s.balance_dollars.toFixed(2)}`;
                        document.getElementById('val-balance').classList.remove('text-kalshi-red');
                    } else {
                        document.getElementById('val-balance').innerText = "--";
                        document.getElementById('val-balance').classList.remove('text-kalshi-red');
                    }
                } else {
                    if (s.balance_dollars !== undefined && s.balance_dollars !== null) {
                        document.getElementById('val-balance').innerText = `$${s.balance_dollars.toFixed(2)}`;
                        document.getElementById('val-balance').classList.remove('text-kalshi-red');
                    } else {
                        document.getElementById('val-balance').innerText = "Auth Error";
                        document.getElementById('val-balance').classList.add('text-kalshi-red');
                    }
                }

                const pnl = s.total_pnl || 0;
                const pnlEl = document.getElementById('val-pnl');
                pnlEl.innerText = `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`;
                pnlEl.className = `text-sm font-black tabular-nums ${pnl >= 0 ? 'text-kalshi-green' : 'text-kalshi-red'}`;
                
                document.getElementById('val-winrate').innerText = `${s.win_rate}%`;

                // Update nav bar center Open Trade PnL (isolated strictly to active universe)
                if (typeof window.updateNavLivePnl === 'function') {
                    window.updateNavLivePnl(s);
                }

                // Update nav bar
                const navBal = document.getElementById('nav-balance');
                if (navBal && s.balance_dollars !== undefined) navBal.textContent = '$' + s.balance_dollars.toFixed(2);
                const navPnl = document.getElementById('nav-pnl');
                if (navPnl) {
                    navPnl.textContent = (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2);
                    navPnl.className = 'text-[11px] font-bold tabular-nums ' + (pnl >= 0 ? 'text-emerald-400' : 'text-red-400');
                }

                // Update profile dropdown
                const dpWr = document.getElementById('dropdown-winrate');
                if (dpWr) dpWr.textContent = (s.win_rate || 0) + '%';
                const dpWins = document.getElementById('dropdown-wins');
                if (dpWins) dpWins.textContent = (s.wins || 0) + 'W';
                const dpLosses = document.getElementById('dropdown-losses');
                if (dpLosses) dpLosses.textContent = (s.losses || 0) + 'L';
                const dpPnl = document.getElementById('dropdown-pnl');
                if (dpPnl) {
                    dpPnl.textContent = (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2);
                    dpPnl.className = 'text-sm font-black tabular-nums truncate ' + (pnl >= 0 ? 'text-emerald-400' : 'text-red-400');
                }
                
                // Update avatar and username
                if (s.profile_pic) {
                    if (s.profile_pic.startsWith('/static/')) s.profile_pic = 'https://moneyprinter.ngrok.app' + s.profile_pic;
                    const navAv = document.getElementById('nav-avatar');
                    const dropAv = document.getElementById('dropdown-avatar');
                    if (navAv) navAv.src = s.profile_pic;
                    if (dropAv) dropAv.src = s.profile_pic;
                }
                if (s.username) {
                    const dropUser = document.getElementById('dropdown-username');
                    if (dropUser) dropUser.textContent = s.username;
                }
                const dpUser = document.getElementById('dropdown-username');
                if (dpUser && s.username) dpUser.textContent = s.username;
                const dpMode = document.getElementById('dropdown-mode-badge');
                if (dpMode) dpMode.textContent = currentMode;
                const execMode = document.getElementById('exec-mode-badge');
                if (execMode) {
                    execMode.textContent = currentMode;
                    execMode.className = currentMode === 'LIVE' ? 'px-1.5 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest bg-red-500/20 text-red-300 border border-red-500/40 leading-none shadow-sm' : 'px-1.5 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 leading-none shadow-sm';
                }

                
        // Profile Picture Upload
        window.uploadAvatar = async function(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                // Show loading state
                const img = document.getElementById('dropdown-avatar');
                const oldSrc = img.src;
                img.style.opacity = '0.5';
                
                const res = await fetch((window.API_BASE_URL||'')+'/api/auth/profile/picture', {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + token },
                    body: formData
                });
                
                let data = {}; try { data = await res.json(); } catch(e){} if(res.ok && data.url) {
                    img.src = data.url;
                    document.getElementById('nav-avatar').src = data.url;
                } else {
                    alert('Upload failed: ' + (data.detail || 'Unknown error'));
                    img.src = oldSrc;
                }
            } catch (e) {
                alert('Upload error: ' + e.message);
            } finally {
                document.getElementById('dropdown-avatar').style.opacity = '1';
                event.target.value = ''; // Reset input
            }
        }

        function getStrategyMeta(style) {
            const s = String(style || '').toUpperCase();
            if (s.includes('SNIPER')) return { icon: '🎯', label: 'Sniper Confluence', short: 'Sniper', border: 'border-cyan-500/30', bg: 'bg-cyan-500/10', text: 'text-cyan-300' };
            if (s.includes('CHOP')) return { icon: '✂️', label: 'Chop Scalper', short: 'Chop', border: 'border-amber-500/30', bg: 'bg-amber-500/10', text: 'text-amber-300' };
            if (s.includes('AMBUSH')) return { icon: '🪤', label: 'Ambush Level', short: 'Ambush', border: 'border-indigo-500/30', bg: 'bg-indigo-500/10', text: 'text-indigo-300' };
            if (s.includes('MOMENTUM')) return { icon: '🏄', label: 'Momentum Surfer', short: 'Momentum', border: 'border-purple-500/30', bg: 'bg-purple-500/10', text: 'text-purple-300' };
            if (s.includes('PREDICTION')) return { icon: '🔮', label: 'Prediction Edge', short: 'Prediction', border: 'border-rose-500/30', bg: 'bg-rose-500/10', text: 'text-rose-300' };
            if (s.includes('GUARD')) return { icon: '🛡️', label: 'Capital Guard', short: 'Guard', border: 'border-blue-500/30', bg: 'bg-blue-500/10', text: 'text-blue-300' };
            if (s.includes('SECOND')) return { icon: '⚡', label: 'Second Entry', short: '2nd Entry', border: 'border-yellow-500/30', bg: 'bg-yellow-500/10', text: 'text-yellow-300' };
            if (s.includes('MANUAL')) return { icon: '✍️', label: 'Manual Entry', short: 'Manual', border: 'border-slate-500/30', bg: 'bg-slate-500/10', text: 'text-slate-300' };
            return { icon: '🤖', label: 'Auto 2.0', short: 'Auto', border: 'border-emerald-500/30', bg: 'bg-emerald-500/10', text: 'text-emerald-300' };
        }

        window.allCommunityUsers = [];
        window.currentCommunityFilter = 'ALL';

        window.setCommunityFilter = function(filter) {
            window.currentCommunityFilter = filter;
            const filterBtns = document.querySelectorAll('[id^="commFilterBtn-"]');
            filterBtns.forEach(btn => {
                if (btn.id === 'commFilterBtn-' + filter) {
                    btn.className = 'px-2.5 py-1 rounded-lg font-bold text-[10px] uppercase tracking-wider bg-indigo-600 text-white whitespace-nowrap transition-all cursor-pointer shadow-sm';
                } else {
                    btn.className = 'px-2.5 py-1 rounded-lg font-bold text-[10px] uppercase tracking-wider bg-[#0c0c10] text-gray-400 hover:text-white border border-kalshi-border whitespace-nowrap transition-all cursor-pointer';
                }
            });
            renderCommunityLeaderboard();
        };

        window.toggleUserStrategyPerf = function(userId) {
            const el = document.getElementById('user-strategy-perf-' + userId);
            const icon = document.getElementById('strat-icon-' + userId);
            const btnText = document.getElementById('strat-btn-text-' + userId);
            if (!el) return;
            
            if (el.classList.contains('hidden')) {
                el.classList.remove('hidden');
                if (icon) icon.classList.add('rotate-180');
                if (btnText) btnText.textContent = 'Hide';
            } else {
                el.classList.add('hidden');
                if (icon) icon.classList.remove('rotate-180');
                const num = el.querySelectorAll('.strat-row-card').length;
                if (btnText) btnText.textContent = 'Breakdown (' + num + ')';
            }
        };

        function renderCommunityLeaderboard() {
            const list = document.getElementById('leaderboardList');
            if (!list) return;
            const users = window.allCommunityUsers || [];

            let filtered = users;
            if (window.currentCommunityFilter !== 'ALL') {
                const f = window.currentCommunityFilter;
                filtered = users.filter(u => {
                    const hasActive = String(u.trading_style || '').toUpperCase().includes(f);
                    const hasPerf = (u.strategy_performance || []).some(s => String(s.strategy || '').toUpperCase().includes(f));
                    return hasActive || hasPerf;
                });
            }

            if (filtered.length === 0) {
                list.innerHTML = '<div class="text-center py-6 text-[10px] text-gray-500 font-mono bg-[#131b2c] rounded-xl border border-kalshi-border">No traders match selected filter</div>';
                return;
            }

            let html = '';
            filtered.forEach((t, i) => {
                const rank = t.rank || (i + 1);
                const rankColor = rank === 1 ? 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30' : 
                                  rank === 2 ? 'text-gray-300 bg-gray-300/10 border-gray-300/30' : 
                                  rank === 3 ? 'text-amber-600 bg-amber-600/10 border-amber-600/30' : 
                                  'text-gray-500 bg-gray-800 border-gray-700';
                                  
                const pnlColor = t.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400';
                const pnlStr = (t.net_pnl >= 0 ? '+$' : '-$') + Math.abs(t.net_pnl).toFixed(2);
                const styleStr = t.trading_style ? t.trading_style.replace(/_/g, ' ') : 'AUTO';
                const sourceStr = t.signal_source ? t.signal_source.replace(/_/g, ' ') : 'BLEND';

                const livePnlVal = t.live_net_pnl !== undefined ? Number(t.live_net_pnl) : 0;
                const paperPnlVal = t.paper_net_pnl !== undefined ? Number(t.paper_net_pnl) : 0;
                const livePnlColor = livePnlVal >= 0 ? 'text-emerald-400' : 'text-rose-400';
                const paperPnlColor = paperPnlVal >= 0 ? 'text-cyan-400' : 'text-rose-400';
                const livePnlStr = (livePnlVal >= 0 ? '+$' : '-$') + Math.abs(livePnlVal).toFixed(2);
                const paperPnlStr = (paperPnlVal >= 0 ? '+$' : '-$') + Math.abs(paperPnlVal).toFixed(2);

                const strats = t.strategy_performance || [];
                let stratChipsHtml = '';
                let stratDetailRowsHtml = '';

                if (strats.length > 0) {
                    stratChipsHtml = strats.slice(0, 3).map(s => {
                        const meta = getStrategyMeta(s.strategy);
                        const pColor = s.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400';
                        const pStr = (s.net_pnl >= 0 ? '+$' : '-$') + Math.abs(s.net_pnl).toFixed(2);
                        return `
                            <div class="px-2 py-0.5 rounded-md ${meta.bg} ${meta.border} border flex items-center gap-1.5 text-[9px] font-mono shadow-sm">
                                <span>${meta.icon}</span>
                                <span class="font-bold text-gray-300">${meta.short}</span>
                                <span class="text-white">${s.win_rate}%</span>
                                <span class="font-bold ${pColor}">${pStr}</span>
                            </div>
                        `;
                    }).join('');

                    stratDetailRowsHtml = strats.map(s => {
                        const meta = getStrategyMeta(s.strategy);
                        const pColor = s.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400';
                        const pStr = (s.net_pnl >= 0 ? '+$' : '-$') + Math.abs(s.net_pnl).toFixed(2);
                        const avgColor = s.avg_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400';
                        const avgStr = (s.avg_pnl >= 0 ? '+$' : '-$') + Math.abs(s.avg_pnl).toFixed(2);
                        const barWidth = Math.min(100, Math.max(5, s.win_rate));
                        const barColor = s.win_rate >= 50 ? 'bg-emerald-500' : 'bg-rose-500';

                        return `
                            <div class="strat-row-card bg-black/50 rounded-lg p-2.5 border border-white/5 space-y-1.5 shadow-inner">
                                <div class="flex items-center justify-between">
                                    <div class="flex items-center gap-1.5">
                                        <span class="text-xs">${meta.icon}</span>
                                        <span class="text-xs font-bold text-white uppercase tracking-wider">${meta.label}</span>
                                        <span class="text-[9px] font-mono text-gray-500">(${s.total_trades} trades)</span>
                                    </div>
                                    <div class="flex items-center gap-2">
                                        <span class="text-xs font-black font-mono ${pColor}">${pStr}</span>
                                        <span class="text-[9px] font-mono text-gray-500">avg ${avgStr}</span>
                                    </div>
                                </div>
                                <div class="flex items-center gap-2">
                                    <div class="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                                        <div class="h-full ${barColor} rounded-full transition-all duration-500" style="width: ${barWidth}%"></div>
                                    </div>
                                    <div class="text-[9px] font-mono font-bold text-gray-300 w-12 text-right">
                                        ${s.win_rate}% WR
                                    </div>
                                    <div class="text-[9px] font-mono text-gray-500">
                                        (${s.wins}W - ${s.losses}L)
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('');
                }

                html += `
                    <div class="bg-[#131b2c] rounded-xl p-3 border border-kalshi-border flex flex-col gap-2.5 transition-all hover:border-slate-700 shadow-md">
                        <!-- Top Row: User Overview -->
                        <div class="flex items-center gap-3">
                            <div class="w-6 h-6 shrink-0 rounded flex items-center justify-center border font-black text-[10px] ${rankColor}">
                                #${rank}
                            </div>
                            <div class="w-9 h-9 rounded-md overflow-hidden border border-kalshi-border shrink-0">
                                <img src="${(t.profile_pic && t.profile_pic.startsWith('/static/')) ? 'https://moneyprinter.ngrok.app'+t.profile_pic : (t.profile_pic || './assets/icon.png')}" class="w-full h-full object-cover">
                            </div>
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-1.5 mb-0.5">
                                    <div class="text-xs font-black text-white uppercase tracking-wider truncate">${t.username}</div>
                                    ${t.is_self ? '<span class="px-1 py-0.2 rounded text-[7px] font-bold uppercase bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">YOU</span>' : ''}
                                    <span class="px-1 py-0.5 rounded text-[7px] font-bold uppercase bg-blue-500/20 text-blue-300 border border-blue-500/30">${styleStr}</span>
                                    <span class="px-1 py-0.5 rounded text-[7px] font-bold uppercase bg-purple-500/20 text-purple-300 border border-purple-500/30">${sourceStr}</span>
                                </div>
                                <div class="text-[9px] font-mono text-gray-500">
                                    <span class="text-white">${t.win_rate}%</span> WR · ${t.total_trades} Trades <span class="opacity-60">(${t.wins}W - ${t.losses}L)</span>
                                    ${t.open_trades > 0 ? '<span class="ml-1 text-emerald-400 font-bold animate-pulse">' + t.open_trades + ' OPEN</span>' : ''}
                                </div>
                            </div>
                            <div class="flex flex-col items-end gap-1 shrink-0">
                                <div class="text-[8px] font-bold uppercase tracking-widest text-gray-500">NET PNL</div>
                                <div class="text-xs font-black tabular-nums ${pnlColor}">${pnlStr}</div>
                                <button id="btn-copy-settings-${t.id}" onclick="copyTraderSettings(${t.id}, '${t.username}')" class="px-2 py-0.5 mt-0.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded text-[8px] font-bold uppercase tracking-wider transition-colors border border-kalshi-border active:scale-95 cursor-pointer">
                                    Copy Settings
                                </button>
                            </div>
                        </div>

                        <!-- Live vs Paper PnL Breakdown Row -->
                        <div class="grid grid-cols-2 gap-2 text-[10px] font-mono">
                            <div class="bg-black/40 border border-emerald-500/25 rounded-lg px-2.5 py-1.5 flex items-center justify-between shadow-inner">
                                <div class="flex items-center gap-1.5">
                                    <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                                    <span class="text-[9px] font-bold text-gray-400 uppercase tracking-wider">Live PnL</span>
                                </div>
                                <div class="flex items-center gap-1.5">
                                    <span class="font-black ${livePnlColor}">${livePnlStr}</span>
                                    <span class="text-[8px] text-gray-500">(${t.live_trades || 0}T · ${t.live_win_rate || 0}%)</span>
                                </div>
                            </div>
                            <div class="bg-black/40 border border-cyan-500/25 rounded-lg px-2.5 py-1.5 flex items-center justify-between shadow-inner">
                                <div class="flex items-center gap-1.5">
                                    <span class="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
                                    <span class="text-[9px] font-bold text-gray-400 uppercase tracking-wider">Paper PnL</span>
                                </div>
                                <div class="flex items-center gap-1.5">
                                    <span class="font-black ${paperPnlColor}">${paperPnlStr}</span>
                                    <span class="text-[8px] text-gray-500">(${t.paper_trades || 0}T · ${t.paper_win_rate || 0}%)</span>
                                </div>
                            </div>
                        </div>

                        <!-- Strategy Performance Row -->
                        <div class="pt-2 border-t border-kalshi-border/40">
                            <div class="flex items-center justify-between mb-1.5">
                                <span class="text-[8px] font-bold uppercase tracking-widest text-gray-400 flex items-center gap-1">
                                    <span>🎯</span> Strategy Performance
                                </span>
                                ${strats.length > 0 ? `
                                    <button onclick="toggleUserStrategyPerf(${t.id})" class="text-[8px] font-bold uppercase tracking-wider text-cyan-400 hover:text-cyan-300 flex items-center gap-1 cursor-pointer transition-colors">
                                        <span id="strat-btn-text-${t.id}">Breakdown (${strats.length})</span>
                                        <svg id="strat-icon-${t.id}" class="w-3 h-3 transform transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                                    </button>
                                ` : `
                                    <span class="text-[8px] text-gray-600 font-mono">No closed trades</span>
                                `}
                            </div>

                            ${strats.length > 0 ? `
                                <!-- Mini Chips (Top 3) -->
                                <div class="flex flex-wrap gap-1.5">
                                    ${stratChipsHtml}
                                </div>

                                <!-- Expandable Full Breakdown -->
                                <div id="user-strategy-perf-${t.id}" class="hidden mt-2.5 pt-2 border-t border-white/5 space-y-2">
                                    <div class="text-[8px] font-bold text-gray-500 uppercase tracking-wider mb-1">
                                        Historical Win Rate & PnL by Trading Style
                                    </div>
                                    ${stratDetailRowsHtml}
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
            });
            list.innerHTML = html;
        }

        // Community Modal
        window.openCommunityModal = async function() {
            // Close dropdown
            document.getElementById('profileDropdown').classList.add('hidden');
            
            // Open modal
            const modal = document.getElementById('communityModal');
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
            
            // Fetch data
            try {
                const userToken = localStorage.getItem('saas_token') || token;
                const res = await fetch((window.API_BASE_URL||'')+'/api/auth/community', {
                    headers: { 'Authorization': 'Bearer ' + userToken }
                });
                if (!res.ok) throw new Error('Failed to fetch community data');
                const data = await res.json();
                
                const summary = data.summary || {};
                document.getElementById('comm-total-traders').textContent = (summary.total_traders || 0) + ' TRADERS';
                document.getElementById('comm-winrate').textContent = (summary.community_win_rate || 0) + '%';
                document.getElementById('comm-total-trades').textContent = (summary.total_trades || 0).toLocaleString();
                
                const livePnl = Number(summary.total_live_pnl || 0);
                const paperPnl = Number(summary.total_paper_pnl || 0);
                const liveEl = document.getElementById('comm-live-pnl');
                if (liveEl) {
                    liveEl.textContent = (livePnl >= 0 ? '+$' : '-$') + Math.abs(livePnl).toFixed(2);
                    liveEl.className = 'text-lg font-black tabular-nums ' + (livePnl >= 0 ? 'text-emerald-400' : 'text-rose-400');
                }
                const paperEl = document.getElementById('comm-paper-pnl');
                if (paperEl) {
                    paperEl.textContent = (paperPnl >= 0 ? '+$' : '-$') + Math.abs(paperPnl).toFixed(2);
                    paperEl.className = 'text-lg font-black tabular-nums ' + (paperPnl >= 0 ? 'text-cyan-400' : 'text-rose-400');
                }
                
                window.allCommunityUsers = data.users || [];
                renderCommunityLeaderboard();
                
            } catch (e) {
                console.error("Community leaderboard error:", e);
                document.getElementById('leaderboardList').innerHTML = '<div class="text-center py-6 text-[10px] text-red-400 font-mono bg-red-900/10 border border-red-900/30 rounded-xl">Error loading community: ' + e.message + '</div>';
            }
        };
        
        window.copyTraderSettings = async function(targetId, username) {
            if (!confirm(`Are you sure you want to copy the trading settings from ${username}? This will overwrite your current configuration.`)) return;
            
            try {
                const res = await fetch(`${window.API_BASE_URL||''}/api/auth/community/copy_settings/${targetId}`, {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + token }
                });
                let data = {}; try { data = await res.json(); } catch(e){} if(res.ok) {
                    alert(`Successfully copied settings from ${username}!`);
                    loadDashboard(); // Refresh UI with new settings
                } else {
                    alert('Failed to copy settings: ' + (data.detail || 'Unknown error'));
                }
            } catch (e) {
                alert('Error: ' + e.message);
            }
        };

        window.openSupportModal = function() {
            const dropdown = document.getElementById('profileDropdown');
            if (dropdown) dropdown.classList.add('hidden');
            const modal = document.getElementById('supportModal');
            if (modal) {
                modal.classList.remove('hidden');
                document.body.style.overflow = 'hidden';
                const msg = document.getElementById('supportTicketMsg');
                if (msg) msg.classList.add('hidden');
            }
        };

        window.closeSupportModal = function() {
            const modal = document.getElementById('supportModal');
            if (modal) {
                modal.classList.add('hidden');
                document.body.style.overflow = 'auto';
            }
        };

        window.submitSupportTicket = async function() {
            const textEl = document.getElementById('supportTicketText');
            const msgEl = document.getElementById('supportTicketMsg');
            const btn = document.getElementById('btnSubmitSupportTicket');
            const issueText = textEl ? textEl.value.trim() : '';

            if (!issueText) {
                if (msgEl) {
                    msgEl.textContent = 'Please enter a description of your issue.';
                    msgEl.className = 'text-xs py-2 px-3 rounded-lg font-bold bg-rose-900/40 text-rose-300 border border-rose-800';
                    msgEl.classList.remove('hidden');
                }
                return;
            }

            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span>⏳</span> Submitting...';
            }

            try {
                const userToken = localStorage.getItem('saas_token') || token;
                const res = await fetch((window.API_BASE_URL||'')+'/api/auth/tickets', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + userToken
                    },
                    body: JSON.stringify({ issue_text: issueText })
                });
                const data = await res.json();
                if (res.ok && data.success) {
                    if (textEl) textEl.value = '';
                    if (msgEl) {
                        msgEl.textContent = '✓ Ticket submitted successfully! Our team and AI Dev Bot will review it.';
                        msgEl.className = 'text-xs py-2 px-3 rounded-lg font-bold bg-emerald-900/40 text-emerald-300 border border-emerald-800';
                        msgEl.classList.remove('hidden');
                    }
                    setTimeout(() => {
                        window.closeSupportModal();
                    }, 2000);
                } else {
                    throw new Error(data.detail || data.message || 'Failed to submit ticket');
                }
            } catch (err) {
                if (msgEl) {
                    msgEl.textContent = 'Error: ' + err.message;
                    msgEl.className = 'text-xs py-2 px-3 rounded-lg font-bold bg-rose-900/40 text-rose-300 border border-rose-800';
                    msgEl.classList.remove('hidden');
                }
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<span>🚀</span> Submit Ticket';
                }
            }
        };

        // Update execution panel
                // Update execution panel
                if (typeof updateExecPanel === 'function') updateExecPanel(s);

                // Populate user settings without overwriting active edits
                populateUserSettings(s);

                // Recent trades
                    const container = document.getElementById('tradesContainer');
                    window.__isSportTrade = function(t) {
                        if (!t) return false;
                        const a = String(t.asset || '').toUpperCase();
                        const tk = String(t.ticker || '').toUpperCase();
                        let meta = t.metadata;
                        if (typeof meta === 'string') {
                            try { meta = JSON.parse(meta); } catch(e) { meta = {}; }
                        }
                        let ml = t.ml_reasoning;
                        if (typeof ml === 'string') {
                            try { ml = JSON.parse(ml); } catch(e) { ml = {}; }
                        }
                        const hasSportProp = Boolean(t.sport || t.predicted_team || (meta && (meta.sport || meta.league)) || (ml && (ml.sport || ml.predicted_team)));
                        const isSportsTicker = /^KX(NFL|MLB|NBA|NHL|NCAAF|NCAAB|WNBA|SOC|UFC|MMA|TEN|NPB|KBO|GAME|ATP)/.test(tk) ||
                                               /^(NFL|MLB|NBA|NHL|NCAAF|NCAAB|WNBA|SOC|UFC|MMA|TEN)-/.test(tk) ||
                                               tk.startsWith('KALSHI-') ||
                                               ['NFL','MLB','NBA','NCAAF','NCAAB','WNBA','NPB','KBO','NPB/KBO','NPB_KBO','NHL','SOC','UFC','TEN','MMA','SPORTS'].includes(a);
                        const isSportsStyle = String(t.trading_style || '').toUpperCase() === 'SPORTS_AI';
                        return isSportsStyle || hasSportProp || isSportsTicker;
                    };
                    window.__getSportInfo = function(t) {
                        if (!t) return { sport: 'SPORTS', team: 'Team', icon: '🏆' };
                        let sport = t.sport || '';
                        let team = t.predicted_team || t.team || '';
                        let meta = t.metadata;
                        if (typeof meta === 'string') {
                            try { meta = JSON.parse(meta); } catch(e) { meta = {}; }
                        }
                        if (!sport && meta) {
                            sport = meta.sport || meta.league || '';
                        }
                        if (!team && meta) {
                            team = meta.predicted_team || meta.team || meta.name || '';
                        }
                        let ml = t.ml_reasoning;
                        if (typeof ml === 'string') {
                            try { ml = JSON.parse(ml); } catch(e) { ml = {}; }
                        }
                        if (!sport && ml) {
                            sport = ml.sport || '';
                        }
                        if (!team && ml) {
                            team = ml.predicted_team || ml.team || '';
                        }
                        const tk = String(t.ticker || '').toUpperCase();
                        if (!sport) {
                            const m = tk.match(/^KX(NFL|MLB|NBA|NHL|NCAAF|NCAAB|WNBA|NPB|KBO|SOC|UFC|MMA|TEN)/) ||
                                      tk.match(/^KX([A-Z]{3,5}?)(?:GAME|-|$)/) ||
                                      tk.match(/^KX([A-Z]{3,5})/);
                            if (m) sport = m[1];
                            else if (tk.startsWith('KALSHI-')) {
                                const parts = tk.split('-');
                                if (parts.length > 1) sport = parts[1];
                                if (!team && parts.length > 2) team = parts[2];
                            }
                        }
                        if (!sport && t.asset && ['NFL','MLB','NBA','NCAAF','NCAAB','WNBA','NPB','KBO','NPB/KBO','NPB_KBO','NHL','SOC','UFC','TEN','MMA','SPORTS'].includes(String(t.asset).toUpperCase())) {
                            sport = String(t.asset).toUpperCase();
                        }
                        sport = (sport || 'SPORTS').toUpperCase();
                        if (sport === 'SOCCER') sport = 'SOC';
                        if (sport === 'TENNIS') sport = 'TEN';
                        if (sport === 'MMA') sport = 'UFC';
                        if (sport === 'NPB_KBO') sport = 'NPB/KBO';

                        if (!team && t.reason) {
                            const mEdge = t.reason.match(/AI Edge:\s*([^(]+)/i);
                            if (mEdge) team = mEdge[1].trim();
                        }
                        if (!team && tk.startsWith('KALSHI-')) {
                            const parts = tk.split('-');
                            if (parts.length > 2) team = parts[2];
                        }
                        if (!team) {
                            team = t.side || 'YES';
                        }

                        // Extract Prop Type, Line, Spread Amount, O/U Amount, Strike Details
                        let propType = t.prop_type || (meta && meta.prop_type) || (ml && ml.prop_type) || '';
                        let line = t.line || (meta && meta.line) || (ml && ml.line) || '';
                        let spreadAmount = t.spread_amount || (meta && meta.spread_amount) || (ml && ml.spread_amount) || '';
                        let overUnderAmount = t.over_under_amount || (meta && meta.over_under_amount) || (ml && ml.over_under_amount) || '';
                        let strikeDetails = t.strike_details || (meta && meta.strike_details) || (ml && ml.strike_details) || '';

                        // Check for player prop patterns from strikeDetails, reason, or ticker
                        const isPlayerPropSeries = [
                            'KXNHLGOAL', 'KXNHLSHOT', 'KXNHLSOG', 'KXNHLAST', 'KXNHLPTS',
                            'KXMLBHR', 'KXMLBHIT', 'KXMLBKS', 'KXMLBRBI',
                            'KXNFLTD', 'KXNFLPASS', 'KXNFLRUSH', 'KXNFLREC',
                            'KXNBAPTS', 'KXNBAREB', 'KXNBAAST', 'KXNBATHREE', 'KXNBA3PT',
                            'GOAL', 'SHOT', 'SOG', 'STRIKEOUT', 'TOUCHDOWN', 'PROP'
                        ].some(k => tk.includes(k));

                        const mPlayer = (strikeDetails + ' ' + (t.reason || '')).match(/([A-Z][a-zA-Z\.\'\-\s]{2,35}?):\s*(\d+\+?|\d+\.\d+|\d+)\s*([a-zA-Z\s]*)/);
                        if (mPlayer) {
                            const pName = mPlayer[1].trim();
                            if (!/^(total|totals|over|under|spread|run line|puck line|moneyline|game|winner|match)/i.test(pName)) {
                                if (!team || team.includes('/') || team.includes('vs') || team.length <= 4) {
                                    team = pName;
                                }
                                propType = 'Player Prop';
                                const pLineNum = mPlayer[2].trim();
                                let pStat = (mPlayer[3] || '').trim();
                                if (!pStat) {
                                    if (tk.includes('GOAL')) pStat = 'Goals';
                                    else if (tk.includes('SHOT') || tk.includes('SOG')) pStat = 'Shots';
                                    else if (tk.includes('HR') || tk.includes('HOMERUN')) pStat = 'Home Runs';
                                    else if (tk.includes('KS') || tk.includes('STRIKEOUT')) pStat = 'Strikeouts';
                                    else if (tk.includes('TD') || tk.includes('TOUCHDOWN')) pStat = 'Touchdowns';
                                    else if (tk.includes('PASS')) pStat = 'Pass Yds';
                                    else if (tk.includes('RUSH')) pStat = 'Rush Yds';
                                    else if (tk.includes('REC')) pStat = 'Receptions';
                                    else if (tk.includes('PTS')) pStat = 'Points';
                                    else if (tk.includes('REB')) pStat = 'Rebounds';
                                    else if (tk.includes('AST')) pStat = 'Assists';
                                    else pStat = 'Props';
                                } else {
                                    pStat = pStat.charAt(0).toUpperCase() + pStat.slice(1);
                                }
                                line = `${pLineNum} ${pStat}`;
                                strikeDetails = `${pName}: ${line}`;
                            }
                        } else if (isPlayerPropSeries) {
                            propType = 'Player Prop';
                        }

                        if (!propType) {
                            if (tk.includes('SPREAD') || tk.includes('RUNLINE')) propType = 'Spread';
                            else if (tk.includes('TOTAL') || tk.includes('OVER') || tk.includes('UNDER')) propType = 'Total (O/U)';
                            else propType = 'Moneyline';
                        }

                        if (!line && t.reason) {
                            const mLine = t.reason.match(/\[([^\]]+)\]\s*([^|]+)/);
                            if (mLine && mLine[2]) line = mLine[2].trim();
                        }
                        if (!line && propType === 'Moneyline') {
                            line = 'Moneyline';
                        }

                        // Enrich line if it's missing the stat unit (e.g. just "1+" or "2+")
                        if (propType === 'Player Prop' && line && /^\d+\+?$/.test(line.trim())) {
                            let statUnit = 'Goals';
                            if (tk.includes('SHOT') || tk.includes('SOG')) statUnit = 'Shots';
                            else if (tk.includes('HR')) statUnit = 'Home Runs';
                            else if (tk.includes('KS') || tk.includes('STRIKEOUT')) statUnit = 'Strikeouts';
                            else if (tk.includes('TD')) statUnit = 'Touchdowns';
                            else if (tk.includes('PTS')) statUnit = 'Points';
                            line = `${line.trim()} ${statUnit}`;
                        }

                        const iconMap = {
                            'NFL': '🏈',
                            'NCAAF': '🏈',
                            'MLB': '⚾',
                            'NBA': '🏀',
                            'NCAAB': '🏀',
                            'WNBA': '🏀',
                            'NHL': '🏒',
                            'NPB': '⚾',
                            'KBO': '⚾',
                            'NPB/KBO': '⚾',
                            'NPB_KBO': '⚾',
                            'SOC': '⚽',
                            'SOCCER': '⚽',
                            'UFC': '🥊',
                            'MMA': '🥊',
                            'TEN': '🎾',
                            'TENNIS': '🎾'
                        };
                        const icon = iconMap[sport] || '🏆';

                        return {
                            sport: sport,
                            team: team,
                            icon: icon,
                            propType: propType,
                            line: line,
                            spreadAmount: spreadAmount,
                            overUnderAmount: overUnderAmount,
                            strikeDetails: strikeDetails
                        };
                    };
                    const __isSportTrade = window.__isSportTrade;
                    const __getSportInfo = window.__getSportInfo;
                    window.renderTradesContainer = function(statsObj) {
                        const sTrades = statsObj || window.lastDashboardStats || {};
                        const __inSports = window.currentUniverse === 'SPORTS';
                        let universeFiltered = (sTrades.recent_trades || []).filter(t => __inSports ? window.__isSportTrade(t) : !window.__isSportTrade(t));
                    const recent = universeFiltered.slice(0, 15);
                    if (recent.length === 0) {
                        container.innerHTML = '<div class="text-center py-6 text-[10px] text-gray-500 font-mono bg-[#131b2c] rounded-xl border border-kalshi-border">No recent trades found</div>';
                    } else {
                        let htmlString = '';
                        window.tradesById = window.tradesById || {};
                        recent.forEach((t, idx) => {
                            const tradeKey = t.id || ('trade_' + idx);
                            window.tradesById[tradeKey] = t;
                            const isWin = (t.status || "").toUpperCase().includes("WIN") || parseFloat(t.pnl_dollars || 0) > 0;
                            const isLoss = (t.status || "").toUpperCase().includes("LOSS") || parseFloat(t.live_pnl !== undefined ? t.live_pnl : (t.pnl_dollars || 0)) < 0;
                            
                            let borderClass = "border-l-2 border-l-kalshi-blue";
                            let statusBadge = '<span class="text-[9px] font-bold text-kalshi-blue">OPEN</span>';
                            
                            const pnlVal = parseFloat(t.live_pnl !== undefined ? t.live_pnl : (t.pnl_dollars || t.pnl || 0));
                            const pnlColor = pnlVal > 0 ? "text-emerald-400" : (pnlVal < 0 ? "text-red-400" : "text-gray-400");
                            const pnlStr = pnlVal > 0 ? "+$" + pnlVal.toFixed(2) : (pnlVal < 0 ? "-$" + Math.abs(pnlVal).toFixed(2) : "$0.00");

                            if (t.status === 'OPEN') {
                                const isSportTrade = window.__isSportTrade(t);
                                const addBtn = isSportTrade ? '' : `<button onclick="event.stopPropagation(); executeManualTrade('${t.side}', '${t.asset || ''}')" class="px-1.5 py-0.5 bg-blue-600/25 text-blue-400 hover:bg-blue-600/40 rounded text-[8px] font-bold border border-blue-500/40 transition-all flex items-center gap-0.5 cursor-pointer"><span>&#10133;</span> ADD</button>`;
                                if (pnlVal > 0) {
                                    statusBadge = `
                                        <div class="flex items-center gap-1">
                                            <span class="text-[9px] font-bold text-yellow-400 animate-pulse">OPEN</span>
                                            ${addBtn}
                                            <button onclick="event.stopPropagation(); takeProfitTrade('${t.id}')" class="px-1.5 py-0.5 bg-emerald-600/25 text-emerald-400 hover:bg-emerald-600/40 rounded text-[8px] font-bold border border-emerald-500/40 transition-all flex items-center gap-0.5 cursor-pointer"><span>💰</span> TAKE PROFIT</button>
                                            <button onclick="event.stopPropagation(); closeTrade('${t.id}')" class="px-1.5 py-0.5 bg-red-600/20 text-red-500 hover:bg-red-600/30 rounded text-[8px] font-bold border border-red-500/30 transition-colors cursor-pointer">CLOSE</button>
                                        </div>
                                    `;
                                } else {
                                    statusBadge = `
                                        <div class="flex items-center gap-1">
                                            <span class="text-[9px] font-bold text-yellow-400 animate-pulse">OPEN</span>
                                            ${addBtn}
                                            <button onclick="event.stopPropagation(); closeTrade('${t.id}')" class="px-1.5 py-0.5 bg-red-600/20 text-red-500 hover:bg-red-600/30 rounded text-[8px] font-bold border border-red-500/30 transition-colors cursor-pointer">CLOSE</button>
                                        </div>
                                    `;
                                }
                            } else if (isWin) {
                                borderClass = "border-l-2 border-l-emerald-500";
                                statusBadge = '<span class="text-[9px] font-bold text-emerald-400">WIN</span>';
                            } else if (isLoss) {
                                borderClass = "border-l-2 border-l-red-500";
                                statusBadge = '<span class="text-[9px] font-bold text-red-400">LOSS</span>';
                            } else {
                                borderClass = "border-l-2 border-l-gray-500";
                                statusBadge = '<span class="text-[9px] font-bold text-gray-400">CLOSED</span>';
                            }

                            const dir = String(t.side || "").toUpperCase();
                            const dirColor = dir === "YES" ? "text-kalshi-green" : "text-kalshi-red";

                            let badges = [];
                            const mode = String(t.mode || "PAPER").toUpperCase();
                            if (mode === "LIVE") {
                                badges.push('<span class="text-[8px] font-black px-1.5 py-0.5 rounded uppercase bg-red-500/20 text-red-300 border border-red-500/40">LIVE</span>');
                            } else {
                                badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">PAPER</span>');
                            }

                            const exitReason = String(t.exit_reason || "").toUpperCase();
                            const isManual = t.is_manual === true || (exitReason === "MANUAL" && !t.trading_style);

                                                        if (isManual) {
                                badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-amber-500/15 text-amber-300 border border-amber-500/35">MANUAL</span>');
                            } else {
                                let styleStr = (t.trading_style && t.trading_style !== "REVERSAL") ? String(t.trading_style).replace(/_/g, ' ') : "🤖 AUTO";
                                if (styleStr.includes("SECOND ENTRY") || styleStr.includes("THIRD ENTRY") || styleStr.includes("STOP LOSS REENTRY") || styleStr.includes("REENTRY")) {
                                    styleStr = "🤖 AUTO";
                                }
                                badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-blue-500/20 text-blue-300 border border-blue-500/35">' + styleStr + '</span>');
                            }
                            
                            const ts = t.trading_style || "";
                            if (t.is_profit_reentry || t.is_second_entry || t.is_third_entry || t.is_stop_loss_reentry || ts.includes('SECOND_ENTRY') || ts.includes('THIRD_ENTRY') || ts.includes('STOP_LOSS_REENTRY') || (t.reason && (t.reason.includes('SECOND_ENTRY') || t.reason.includes('THIRD_ENTRY') || t.reason.includes('STOP_LOSS_REENTRY')))) {
                                const isThird = (ts === 'THIRD_ENTRY' || t.is_third_entry || (t.reason && t.reason.includes('THIRD_ENTRY')));
                                const isSL = (t.is_stop_loss_reentry || (t.reason && t.reason.includes('STOP_LOSS_REENTRY')));
                                const baseText = isThird ? '3RD ENTRY' : '2ND ENTRY';
                                const reentryText = isSL ? ('DIP RE-ENTRY (' + baseText + ')') : baseText;
                                const badgeColor = isSL ? 'bg-amber-500/20 text-amber-300 border-amber-500/35' : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/35';
                                badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase ' + badgeColor + '">' + reentryText + '</span>');
                            }
                            const isReversal = Boolean(t.is_reversal || t.is_reverse || (t.reason && t.reason.includes('REVERSAL')) || (t.signal_source && t.signal_source.includes('REVERSAL')));
                            if (isReversal) {
                                badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-purple-500/20 text-purple-400 border border-purple-500/35">REVERSAL</span>');
                            }

                            if (exitReason && exitReason !== 'KALSHI_POSITION_RECONCILED' && exitReason !== 'AI_SIGNAL' && exitReason !== 'SETTLEMENT' && !isManual && !exitReason.includes('AI_COPY') && !exitReason.includes('REVERSAL') && !exitReason.includes('SECOND_ENTRY') && !exitReason.includes('THIRD_ENTRY') && !exitReason.includes('STOP_LOSS_REENTRY')) {
                                let exitStr = exitReason.replace(/_/g, ' ');
                                let exitColor = 'bg-slate-500/20 text-slate-400 border-slate-500/35';
                                if (exitStr.includes('PROFIT') || exitStr.includes('TP')) exitColor = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/35';
                                else if (exitStr.includes('STOP LOSS') || exitStr.includes('STOP_LOSS') || exitStr.includes('SL') || exitStr.includes('STOP')) exitColor = 'bg-red-500/20 text-red-400 border-red-500/35';
                                badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase border ' + exitColor + '">' + exitStr + '</span>');
                            }

                            // Format entry/exit times
                            const entryTs = t.timestamp || t.time || '';
                            let entryTime = '--';
                            let exitTime = '--';
                            try {
                                if (entryTs) {
                                    const d = new Date(entryTs);
                                    entryTime = d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
                                }
                                // exit_time may not exist; derive from reason timing or show settled
                                if (t.settled_at) exitTime = new Date(t.settled_at * 1000).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
                                else if (t.status !== 'OPEN') exitTime = 'settled';
                            } catch(e) {}

                            // Size
                            const contractSize = t.count || t.size || 1;
                            const entryPct = t.entry_price !== undefined ? Math.round(t.entry_price * 100) + 'c' : '--';
                            const exitPct  = t.exit_price  !== undefined ? Math.round(t.exit_price  * 100) + 'c' : '--';

                            // Signal source badge color
                            let aiColor = 'bg-blue-500/20 text-blue-300 border-blue-500/35';
                            const src = String(t.signal_source || '').toUpperCase();
                            if (src === 'AI_ONLY')    aiColor = 'bg-purple-500/20 text-purple-300 border-purple-500/35';
                            else if (src === '⚖️ BLEND' || src === 'BLEND') aiColor = 'bg-cyan-500/20 text-cyan-300 border-cyan-500/35';
                            else if (src === 'CHART_ONLY') aiColor = 'bg-orange-500/20 text-orange-300 border-orange-500/35';
                            else if (src === 'MANUAL') aiColor = 'bg-amber-500/15 text-amber-300 border-amber-500/35';

                            // Model badge
                            const modelStr = t.model_choice ? String(t.model_choice) : '';

                            // Confidence
                            const confStr = t.confidence != null ? Math.round(t.confidence) + '% conf' : (t.probability_percent != null ? Math.round(t.probability_percent) + '% prob' : '');

                            if (src && !isManual && !src.includes('REVERSAL')) {
                                badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase border ' + aiColor + '">' + (src === '⚖️ BLEND' || src === 'BLEND' ? '⚖️ BLEND' : src === 'AI_ONLY' ? '🧠 AI ONLY' : src === 'CHART_ONLY' ? 'CHART' : src) + '</span>');
                            }
                            if (modelStr && !isManual) {
                                badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-indigo-500/20 text-indigo-300 border border-indigo-500/35">' + modelStr + '</span>');
                            }
                            if (confStr) {
                                badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-gray-700/40 text-gray-400 border border-gray-600/40">' + confStr + '</span>');
                            }

                            // Strict deduplication of badges by stripped uppercase text
                            const seenBadgeTexts = new Set();
                            const uniqueBadges = [];
                            badges.forEach(b => {
                                const cleanTxt = b.replace(/<[^>]*>/g, '').trim().toUpperCase();
                                if (cleanTxt && !seenBadgeTexts.has(cleanTxt)) {
                                    seenBadgeTexts.add(cleanTxt);
                                    uniqueBadges.push(b);
                                }
                            });

                            // Official result badge
                            let resultBadge = '';
                            if (t.market_finished) {
                                const won = String(t.official_result || '').toUpperCase() === String(t.side || '').toUpperCase();
                                resultBadge = won
                                    ? '<span class="text-[8px] font-black px-1.5 py-0.5 rounded uppercase bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">CORRECT</span>'
                                    : '<span class="text-[8px] font-black px-1.5 py-0.5 rounded uppercase bg-red-500/20 text-red-300 border border-red-500/40">WRONG</span>';
                            }

                            const rawStrikeNum = Number(t.strike);
                            const hasValidStrike = (t.strike !== null && t.strike !== undefined && t.strike !== '' && !isNaN(rawStrikeNum) && isFinite(rawStrikeNum) && rawStrikeNum > 0);
                            const formattedStrike = hasValidStrike ? ('$' + rawStrikeNum.toLocaleString(undefined, {maximumFractionDigits: 0})) : '---';

                            htmlString += `
                                <div onclick="openTradeDetailsModal('${tradeKey}')" class="bg-[#131b2c] hover:bg-[#152033] cursor-pointer rounded-xl shadow-sm border border-kalshi-border ${borderClass} hover:border-kalshi-blue/60 transition-all flex flex-col mb-2 overflow-hidden group active:scale-[0.99]" title="Click to view AI breakdown & full trade details">
                                    <!-- Asset Type Detection -->
                                    ${(() => {
                                        const isSport = window.__isSportTrade(t);
                                        if (isSport) {
                                            const sInfo = window.__getSportInfo(t);
                                            window._currentAssetBadge = `<span class="text-[9px] font-black px-1.5 py-0.5 rounded uppercase tracking-wider border bg-cyan-500/20 text-cyan-300 border-cyan-500/40">${sInfo.icon} ${sInfo.sport}</span>`;
                                            window._currentTradeSportInfo = sInfo;
                                            return '';
                                        }
                                        window._currentTradeSportInfo = null;
                                        let assetType = String(t.asset || '').toUpperCase();
                                        if (!assetType || assetType === 'NONE') {
                                            const tk = String(t.ticker || '').toUpperCase();
                                            if (tk.includes('BTC')) assetType = 'BTC';
                                            else if (tk.includes('ETH')) assetType = 'ETH';
                                            else if (tk.includes('GOLD')) assetType = 'GOLD';
                                            else if (tk.includes('EURUSD')) assetType = 'EURUSD';
                                            else if (tk.includes('GBPUSD')) assetType = 'GBPUSD';
                                            else if (tk.includes('USDJPY')) assetType = 'USDJPY';
                                            else if (tk.includes('AUDUSD')) assetType = 'AUDUSD';
                                            else if (tk.includes('NDQ')) assetType = 'NDQ';
                                            else if (tk.includes('SOL')) assetType = 'SOL';
                                            else if (tk.includes('DOGE')) assetType = 'DOGE';
                                            else assetType = 'BTC';
                                        }
                                        let assetBadgeClass = 'bg-slate-500/20 text-slate-300 border-slate-500/40';
                                        let assetIcon = '';
                                        if (assetType === 'BTC') { assetBadgeClass = 'bg-amber-500/20 text-amber-300 border-amber-500/40'; assetIcon = '₿ '; }
                                        else if (assetType === 'ETH') { assetBadgeClass = 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40'; assetIcon = 'Ξ '; }
                                        else if (assetType === 'GOLD') { assetBadgeClass = 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40'; assetIcon = '🪙 '; }
                                            else if (assetType === 'EURUSD') { assetBadgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'; assetIcon = '💵 '; }
                                            else if (assetType === 'GBPUSD') { assetBadgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'; assetIcon = '💵 '; }
                                            else if (assetType === 'USDJPY') { assetBadgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'; assetIcon = '💵 '; }
                                            else if (assetType === 'AUDUSD') { assetBadgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'; assetIcon = '💵 '; }
                                            else if (assetType === 'NDQ') { assetBadgeClass = 'bg-blue-500/20 text-blue-300 border-blue-500/40'; assetIcon = '📈 '; }
                                            else if (assetType === 'SOL') { assetBadgeClass = 'bg-purple-500/20 text-purple-300 border-purple-500/40'; assetIcon = '🚀 '; }
                                            else if (assetType === 'DOGE') { assetBadgeClass = 'bg-orange-500/20 text-orange-300 border-orange-500/40'; assetIcon = '🐕 '; }
                                        window._currentAssetBadge = `<span class="text-[9px] font-black px-1.5 py-0.5 rounded uppercase tracking-wider border ${assetBadgeClass}">${assetIcon}${assetType}</span>`;
                                        return '';
                                    })()}
                                    <!-- Row 1: Direction + Asset + Prop/Line/Team + PnL -->
                                    <div class="flex justify-between items-center px-3 pt-2.5 pb-1">
                                        <div class="flex items-center gap-1.5 flex-wrap min-w-0">
                                            <span class="text-[13px] font-black tracking-wider ${dirColor}">${dir}</span>
                                            ${window._currentAssetBadge || ''}
                                            ${window._currentTradeSportInfo ? `
                                                <span class="px-1.5 py-0.5 rounded font-black text-[8.5px] uppercase tracking-wider ${
                                                    window._currentTradeSportInfo.propType === 'Player Prop' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' :
                                                    window._currentTradeSportInfo.propType === 'Spread' ? 'bg-purple-500/20 text-purple-300 border-purple-500/40' :
                                                    (window._currentTradeSportInfo.propType.includes('Total') || window._currentTradeSportInfo.propType.includes('O/U')) ? 'bg-amber-500/20 text-amber-300 border-amber-500/40' :
                                                    'bg-blue-500/20 text-blue-300 border-blue-500/40'
                                                } border">${window._currentTradeSportInfo.propType || 'Pick'}</span>
                                                <span class="text-[11px] font-bold text-white tracking-wide truncate max-w-[140px]">${window._currentTradeSportInfo.team}</span>
                                                ${window._currentTradeSportInfo.line && window._currentTradeSportInfo.line !== 'Moneyline' ? `<span class="px-1.5 py-0.5 rounded font-bold text-[8.5px] bg-black/50 text-cyan-300 border border-cyan-500/25 font-mono">${window._currentTradeSportInfo.line}</span>` : ''}
                                            ` : `<span class="text-[11px] font-bold text-gray-400">Strike <span class="text-white">${formattedStrike}</span></span>`}
                                            ${resultBadge}
                                        </div>
                                        <div class="flex items-center gap-2 shrink-0">
                                            <span class="text-[12px] font-black tabular-nums ${pnlColor}">${pnlStr}</span>
                                            ${statusBadge}
                                        </div>
                                    </div>
                                    ${window._currentTradeSportInfo && window._currentTradeSportInfo.strikeDetails && window._currentTradeSportInfo.strikeDetails.toLowerCase() !== window._currentTradeSportInfo.team.toLowerCase() ? `
                                        <div class="px-3 pb-1 text-[9px] text-gray-300 font-mono flex items-center gap-1 truncate">
                                            <span class="text-cyan-400">🎯</span>
                                            <span class="truncate">${window._currentTradeSportInfo.strikeDetails}</span>
                                        </div>
                                    ` : ''}

                                    <!-- Row 2: Entry/Exit prices + Size Spent -->
                                    <div class="flex items-center gap-3 px-3 pb-1.5 text-[10px] text-gray-400 font-mono">
                                        <span>IN <span class="text-white font-bold">${entryPct}</span></span>
                                        <span class="text-gray-600">→</span>
                                        <span>OUT <span class="text-white font-bold">${exitPct}</span></span>
                                        <span class="ml-auto bg-black/40 px-1.5 py-0.5 rounded border border-kalshi-border text-[9px] font-bold uppercase tracking-widest text-gray-300">Size <span class="text-white">$${(t.count * (t.entry_price || 0)).toFixed(2)}</span></span>
                                    </div>

                                    <!-- Row 3: Times -->
                                    <div class="flex items-center gap-3 px-3 pb-1.5 text-[9px] text-gray-500 font-mono">
                                        <span>&#9656; ${entryTime}</span>
                                        <span class="text-gray-600">→</span>
                                        <span>&#9632; ${exitTime}</span>
                                        <span class="ml-auto text-gray-600">${t.ticker ? t.ticker.split('-').slice(-2).join('-') : ''}</span>
                                    </div>

                                    <!-- Row 4: Badges -->
                                    <div class="flex flex-wrap gap-1 px-3 pb-2">
                                        ${uniqueBadges.join(' ')}
                                    </div>

                                    <!-- Row 5: Sleek Click Breakdown Banner -->
                                    <div class="flex items-center justify-between px-3 py-1.5 bg-black/25 border-t border-white/5 text-[9px] text-gray-400 font-mono group-hover:text-gray-300">
                                        <span class="flex items-center gap-1.5">
                                            <span class="text-[10px]">🔍</span> Tap for AI/ML breakdown
                                        </span>
                                        <span class="text-kalshi-blue font-bold flex items-center gap-0.5 group-hover:translate-x-0.5 transition-transform">Details →</span>
                                    </div>
                                </div>
                            `;
                        });
                        container.innerHTML = htmlString;
                    }
                };
                
                
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
                                        window.iosNotify('Trade Won!', 'profit secured', 'success');
                                    } else {
                                        window.iosNotify('Trade Closed', 'loss incurred', 'error');
                                    }
                                }
                                knownCompletedTrades.add(tradeId);
                            }
                        }
                    });
                }


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
                                        window.iosNotify('Trade Won!', 'profit secured', 'success');
                                    } else {
                                        window.iosNotify('Trade Closed', 'loss incurred', 'error');
                                    }
                                }
                                knownCompletedTrades.add(tradeId);
                            }
                        }
                    });
                }

                window.renderTradesContainer(s);
                if (typeof updateActivePositionHud === 'function') updateActivePositionHud(s);
            } catch (err) {
                console.error("loadDashboard error:", err);
            }
        }

        let chartInitialized = false;
        async function init() {
            if (!window.isTabActive) return;
            try {
                // Retry chart init until it succeeds
                if (!chartInitialized && document.getElementById('lw-chart-container') && !document.querySelector('#lw-chart-container canvas')) {
                    await initChart();
                    if (document.querySelector('#lw-chart-container canvas')) {
                        chartInitialized = true;
                    }
                }
                if(typeof loadConfig === 'function') await loadConfig();
                if(typeof loadDashboard === 'function') await loadDashboard();
                if(typeof updateTimerBidsVisibility === 'function') updateTimerBidsVisibility();
                if(typeof checkUpdateAnnouncement === 'function') checkUpdateAnnouncement();
            } catch(e) { console.error("Init error:", e); }
        }
        
        function applyTradePanelPreference() {
            const showPanelStr = localStorage.getItem('showTradeExecutionPanel');
            const showPanel = showPanelStr !== 'false'; // default true
            
            const toggle = document.getElementById('show-trade-panel-toggle');
            if (toggle) toggle.checked = showPanel;
            const toggle3 = document.getElementById('toggle-trade-exec-panel');
            if (toggle3) toggle3.checked = showPanel;
            
            const panel = document.getElementById('trade-execution-panel');
            if (panel) panel.style.display = showPanel ? 'block' : 'none';
            if (typeof updateTimerBidsVisibility === 'function') updateTimerBidsVisibility();
            if (typeof updatePositionScannerCloseButton === 'function') updatePositionScannerCloseButton();
        }

        // Apply immediately and on lifecycle events
        applyTradePanelPreference();
        document.addEventListener('DOMContentLoaded', applyTradePanelPreference);
        window.addEventListener('load', () => {
            init();
            applyTradePanelPreference();
            if(typeof checkUpdateAnnouncement === 'function') checkUpdateAnnouncement();
        });

        // Auto refresh
        setInterval(init, 1000);

        
        // Logout function
        
    
        // ── Real BTC 15m Chart + Live Kalshi Bids ──
        let lwChart, candleSeries, lineSeries, volumeSeries;
        let lastBidTs = 0;

        let isChartInitializing = false;
        async function initChart() {
            if (chartInitialized || isChartInitializing) return;
            isChartInitializing = true;
            // Restore saved chart preferences on init
            const savedType = localStorage.getItem('chart_type') || 'candle';
            const savedTf = localStorage.getItem('chart_timeframe') || '15m';
            window.currentChartType = savedType;
            window.currentChartTimeframe = savedTf;

            const chartTypeSelect = document.getElementById('settings-chart-type');
            if (chartTypeSelect) chartTypeSelect.value = savedType;
            const chartTfSelect = document.getElementById('settings-chart-timeframe');
            if (chartTfSelect) chartTfSelect.value = savedTf;

            // Wait for LightweightCharts to be available (CDN may still be loading)
            let attempts = 0;
            while (typeof LightweightCharts === 'undefined' && attempts < 20) {
                await new Promise(r => setTimeout(r, 250));
                attempts++;
            }

                        const container = document.getElementById('lw-chart-container');
            if (!container) { hideChartLoader(); isChartInitializing = false; return; }
            container.innerHTML = '';

            if (typeof LightweightCharts === 'undefined') {
                console.error('[Chart] LightweightCharts CDN failed to load');
                const loader = document.getElementById('chart-loader');
                if (loader) loader.innerHTML = '<div class="text-[10px] text-red-400 font-mono">Chart CDN unavailable</div>';
                return;
            }

            try {
                lwChart = LightweightCharts.createChart(container, {
                    layout:     { background: { type:'solid', color:'#0a0e17' }, textColor:'#94a3b8', fontSize:10, attributionLogo: false },
                    grid:       { vertLines:{ color:'#1e293b22' }, horzLines:{ color:'#1e293b22' } },
                    timeScale:  { timeVisible:true, secondsVisible:false, borderColor:'#1e293b', rightOffset:4 },
                    rightPriceScale: { borderColor:'#1e293b', scaleMargins:{ top:0.1, bottom:0.22 } },
                    crosshair:  { mode: LightweightCharts.CrosshairMode.Normal },
                    width: container.clientWidth || container.offsetWidth || 390,
                    height: container.clientHeight || container.offsetHeight || 280,
                });

                candleSeries = lwChart.addCandlestickSeries({
                    upColor:'#22c55e', downColor:'#ef4444', borderUpColor:'#22c55e', borderDownColor:'#ef4444',
                    wickUpColor:'#22c55e80', wickDownColor:'#ef444480',
                    visible: window.currentChartType !== 'line',
                });

                lineSeries = lwChart.addLineSeries({
                    color: '#00e5ff',
                    lineWidth: 2,
                    crosshairMarkerVisible: true,
                    crosshairMarkerRadius: 4,
                    priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
                    visible: window.currentChartType === 'line',
                });

                volumeSeries = lwChart.addHistogramSeries({
                    priceFormat:{ type:'volume' }, priceScaleId:'vol',
                    color:'#0052ff40',
                });
                lwChart.priceScale('vol').applyOptions({ scaleMargins:{ top:0.85, bottom:0 } });

                await fetchChartData();
                hideChartLoader();

                // Responsive resize
                const ro = new ResizeObserver(entries => {
                    const r = entries[0]?.contentRect;
                    if (r && r.width > 0 && r.height > 0) {
                        lwChart.applyOptions({ width: r.width, height: r.height });
                    }
                });
                ro.observe(container);

                // Register refresh intervals once (Audit Item 1: throttle and guard)
                if (!window.chartIntervalsRegistered) {
                    window.chartIntervalsRegistered = true;
                    setInterval(fetchChartData, 15000);
                    if (typeof scheduleNextLiveBids === 'function') scheduleNextLiveBids(BASE_LIVE_BIDS_INTERVAL_MS);
                    setInterval(loadDashboard, 1000);
                }
                chartInitialized = true;
            } catch(err) {
                console.error('[Chart] init error:', err);
            } finally {
                isChartInitializing = false;
                hideChartLoader();
            }
            if (typeof initSpotWebSocket === 'function') initSpotWebSocket();
        }

        window.updateChartSettings = async function() {
            const typeEl = document.getElementById('settings-chart-type');
            const tfEl = document.getElementById('settings-chart-timeframe');
            if (!typeEl || !tfEl) return;

            const newType = typeEl.value; // 'line' or 'candle'
            const newTf = tfEl.value; // '1m', '5m', '15m', '1d'

            window.currentChartType = newType;
            window.currentChartTimeframe = newTf;

            localStorage.setItem('chart_type', newType);
            localStorage.setItem('chart_timeframe', newTf);

            if (lwChart) {
                if (newType === 'line') {
                    if (candleSeries) candleSeries.applyOptions({ visible: false });
                    if (lineSeries) lineSeries.applyOptions({ visible: true });
                } else {
                    if (candleSeries) candleSeries.applyOptions({ visible: true });
                    if (lineSeries) lineSeries.applyOptions({ visible: false });
                }
            }

            if (typeof fetchChartData === 'function') {
                await fetchChartData(true);
            }

            if (typeof showToast === 'function') {
                const label = newType === 'line' ? 'Line' : 'Candles';
                showToast(`Chart updated: ${newTf.toUpperCase()} ${label}`, 'success', 2000);
            }
        };

        window.syncChartSettingsUI = function() {
            const savedType = localStorage.getItem('chart_type') || window.currentChartType || 'candle';
            const savedTf = localStorage.getItem('chart_timeframe') || window.currentChartTimeframe || '15m';
            const typeEl = document.getElementById('settings-chart-type');
            const tfEl = document.getElementById('settings-chart-timeframe');
            if (typeEl) typeEl.value = savedType;
            if (tfEl) tfEl.value = savedTf;

            const showPanelStr = localStorage.getItem('showTradeExecutionPanel');
            const showPanel = showPanelStr !== 'false';
            const toggle = document.getElementById('show-trade-panel-toggle');
            if (toggle) toggle.checked = showPanel;
            const toggle2 = document.getElementById('show-trade-panel-toggle-chart');
            if (toggle2) toggle2.checked = showPanel;
        };

        // Multi-asset spot price cache & request sequence tracking
        window.currentAsset = 'BTC';
        window.assetSpotPrices = { 'BTC': null, 'ETH': null, 'GOLD': null, 'EURUSD': null, 'GBPUSD': null, 'USDJPY': null, 'AUDUSD': null, 'NDQ': null, 'SOL': null, 'DOGE': null };
        let currentChartRequestId = 0;
        let currentKalshiRequestId = 0;
        let isRebuildingChart = false;

        
        window.toggleMoreAssets = function(e) {
            if (e) e.stopPropagation();
            const dropdown = document.getElementById('more-assets-dropdown');
            if (!dropdown) return;
            if (dropdown.classList.contains('hidden')) {
                dropdown.classList.remove('hidden');
                setTimeout(() => {
                    dropdown.classList.remove('opacity-0', 'scale-95');
                    dropdown.classList.add('opacity-100', 'scale-100');
                }, 10);
            } else {
                dropdown.classList.remove('opacity-100', 'scale-100');
                dropdown.classList.add('opacity-0', 'scale-95');
                setTimeout(() => dropdown.classList.add('hidden'), 150);
            }
        };
        
        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            const dropdown = document.getElementById('more-assets-dropdown');
            const btn = document.getElementById('btn-asset-more');
            if (dropdown && !dropdown.classList.contains('hidden') && btn && !btn.contains(e.target) && !dropdown.contains(e.target)) {
                window.toggleMoreAssets();
            }
        });

        function showChartLoader() {
            const el = document.getElementById('chart-loader');
            if (el) {
                el.style.opacity = '1';
                el.style.display = 'flex';
                el.classList.remove('pointer-events-none');
            }
        }

        function hideChartLoader() {
            const el = document.getElementById('chart-loader');
            if (el) {
                el.style.opacity = '0';
                el.style.display = 'none';
                el.classList.add('pointer-events-none');
            }
        }

        function sanitizeCandles(rawCandles) {
            if (!Array.isArray(rawCandles) || !rawCandles.length) return [];
            const valid = [];
            const seenTimes = new Set();
            const sorted = [...rawCandles].sort((a, b) => Number(a.time) - Number(b.time));

            for (const c of sorted) {
                if (!c || c.time === undefined || c.time === null) continue;
                const time = Number(c.time);
                if (!isFinite(time) || time <= 0) continue;
                if (seenTimes.has(time)) continue;

                let o = Number(c.open);
                let h = Number(c.high);
                let l = Number(c.low);
                let cl = Number(c.close);

                if (!isFinite(o) || !isFinite(h) || !isFinite(l) || !isFinite(cl)) continue;
                if (o <= 0 || cl <= 0) continue;

                const maxVal = Math.max(o, cl, h, l);
                const minVal = Math.min(o, cl, h, l);
                h = maxVal;
                l = Math.max(0.0001, minVal);

                seenTimes.add(time);
                valid.push({ time, open: o, high: h, low: l, close: cl });
            }
            return valid;
        }

        function sanitizeVolume(rawVol) {
            if (!Array.isArray(rawVol) || !rawVol.length) return [];
            const valid = [];
            const seenTimes = new Set();
            const sorted = [...rawVol].sort((a, b) => Number(a.time) - Number(b.time));
            for (const v of sorted) {
                if (!v || v.time === undefined || v.time === null) continue;
                const time = Number(v.time);
                if (!isFinite(time) || time <= 0) continue;
                if (seenTimes.has(time)) continue;
                const value = Math.max(0, Number(v.value) || 0);
                seenTimes.add(time);
                valid.push({
                    time,
                    value,
                    color: v.color || (value > 0 ? '#0052ff40' : '#1e293b40')
                });
            }
            return valid;
        }

        async function rebuildChart() {
            if (isRebuildingChart) return;
            isRebuildingChart = true;
            try {
                console.log('[Chart] Rebuilding Lightweight Charts instance...');
                if (lwChart) {
                    try { lwChart.remove(); } catch(_) {}
                    lwChart = null;
                    candleSeries = null;
                    lineSeries = null;
                    volumeSeries = null;
                }
                chartInitialized = false;
                isChartInitializing = false;
                await initChart();
            } catch (err) {
                console.error('[Chart] Rebuild failed:', err);
            } finally {
                isRebuildingChart = false;
            }
        }

        window.currentUniverse = localStorage.getItem('preferred_universe') || null;
        
        window.toggleUniverseDropdown = function(e) {
            e.stopPropagation();
            const dd = document.getElementById('universe-dropdown');
            if (dd.classList.contains('hidden')) {
                dd.classList.remove('hidden');
                setTimeout(() => {
                    dd.classList.remove('opacity-0', 'scale-95');
                }, 10);
            } else {
                dd.classList.add('opacity-0', 'scale-95');
                setTimeout(() => {
                    dd.classList.add('hidden');
                }, 200);
            }
        };
        
        document.addEventListener('click', (e) => {
            const dd = document.getElementById('universe-dropdown');
            if (dd && !dd.classList.contains('hidden') && !e.target.closest('#universe-dropdown') && !e.target.closest('[onclick="toggleUniverseDropdown(event)"]')) {
                dd.classList.add('opacity-0', 'scale-95');
                setTimeout(() => {
                    dd.classList.add('hidden');
                }, 200);
            }
        });

        window.updateNavLivePnl = function(statsObj) {
            const s = statsObj || window.lastDashboardStats || {};
            const __inSports = window.currentUniverse === 'SPORTS';
            const isSportTradeFn = window.__isSportTrade || (() => false);
            const openTrades = (s.recent_trades || [])
                .filter(t => String(t.status || '').toUpperCase() === 'OPEN')
                .filter(t => __inSports ? isSportTradeFn(t) : !isSportTradeFn(t));

            const hasOpenTrades = openTrades.length > 0;
            const livePnlContainer = document.getElementById('nav-live-pnl-container');
            const livePnlVal = document.getElementById('nav-live-pnl-val');
            if (livePnlContainer && livePnlVal) {
                if (hasOpenTrades) {
                    livePnlContainer.classList.remove('hidden');
                    livePnlContainer.classList.add('flex');
                    let lPnl = 0;
                    if (!__inSports && s.live_open_pnl !== undefined && s.live_open_pnl !== null) {
                        lPnl = Number(s.live_open_pnl);
                    } else {
                        lPnl = openTrades.reduce((acc, t) => acc + (t.live_pnl !== undefined ? Number(t.live_pnl) : (t.pnl_dollars !== undefined ? Number(t.pnl_dollars) : 0)), 0);
                    }
                    if (isNaN(lPnl)) lPnl = 0;
                    const isPos = lPnl > -0.005;
                    livePnlVal.textContent = (isPos ? '+$' : '-$') + Math.abs(lPnl).toFixed(2);
                    livePnlVal.className = `text-sm sm:text-base font-black tabular-nums leading-none tracking-tight ${isPos ? 'text-emerald-400' : 'text-rose-400'}`;
                } else {
                    livePnlContainer.classList.add('hidden');
                    livePnlContainer.classList.remove('flex');
                }
            }
        };

        window.selectUniverse = function(universe) {
            window.currentUniverse = universe;
            try { localStorage.setItem('preferred_universe', universe); } catch(_) {}
            document.body.classList.toggle('universe-sports', universe === 'SPORTS');
            const label = document.getElementById('market-universe-label');
            if (label) label.innerText = universe === 'SPORTS' ? 'SPORTS' : 'MARKETS';
            
            // Sync settings drawer title, badge, subtitle, and buttons
            const sTitle = document.getElementById('settings-drawer-title');
            const sBadge = document.getElementById('settings-universe-badge');
            const sSub = document.getElementById('settings-drawer-subtitle');
            if (sTitle) sTitle.innerText = universe === 'SPORTS' ? 'Sports Universe Settings' : 'Financials Settings';
            if (sBadge) {
                sBadge.innerText = universe === 'SPORTS' ? '🏈 SPORTS' : '📈 FINANCIALS';
                sBadge.className = universe === 'SPORTS'
                    ? 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-amber-500/15 text-amber-400 border border-amber-500/30 flex items-center gap-1'
                    : 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 flex items-center gap-1';
            }
            if (sSub) {
                sSub.innerHTML = universe === 'SPORTS'
                    ? '<span>Sports AI edge, wager sizing & pick controls</span> <span class="text-amber-400/80">✦ Swipe right to close</span>'
                    : '<span>Algorithmic risk limits & crypto trading parameters</span> <span class="text-cyan-400/80">✦ Swipe right to close</span>';
            }
            const btnFin = document.getElementById('btn-universe-fin-settings');
            const btnSports = document.getElementById('btn-universe-sports-settings');
            if (btnFin && btnSports) {
                if (universe === 'SPORTS') {
                    btnSports.className = 'flex-1 py-2 text-[10px] font-bold tracking-wider rounded-lg transition-all text-white bg-amber-500/25 border border-amber-500/40 shadow-sm flex items-center justify-center gap-1.5 cursor-pointer';
                    btnFin.className = 'flex-1 py-2 text-[10px] font-bold tracking-wider rounded-lg transition-all text-gray-400 hover:text-white border border-transparent flex items-center justify-center gap-1.5 cursor-pointer';
                } else {
                    btnFin.className = 'flex-1 py-2 text-[10px] font-bold tracking-wider rounded-lg transition-all text-white bg-cyan-500/25 border border-cyan-500/40 shadow-sm flex items-center justify-center gap-1.5 cursor-pointer';
                    btnSports.className = 'flex-1 py-2 text-[10px] font-bold tracking-wider rounded-lg transition-all text-gray-400 hover:text-white border border-transparent flex items-center justify-center gap-1.5 cursor-pointer';
                }
            }

            const dd = document.getElementById('universe-dropdown');
            if (dd) {
                dd.classList.add('opacity-0', 'scale-95');
                setTimeout(() => {
                    dd.classList.add('hidden');
                }, 200);
            }
            
            const finAssets = document.querySelectorAll('#btn-asset-btc, #btn-asset-eth, #btn-asset-gold');
            const moreAssetsWrapper = document.getElementById('btn-asset-more') ? document.getElementById('btn-asset-more').parentElement : null;
            const sportsAssets = document.querySelectorAll('.asset-btn-sports');
            
            const fAs = document.getElementById('finance-asset-settings');
            const fRs = document.getElementById('finance-risk-settings');
            const sRs = document.getElementById('sports-risk-settings');

            if (universe === 'SPORTS') {
                document.querySelectorAll('.finance-only-setting').forEach(el => el.classList.add('hidden'));
                document.querySelectorAll('.sports-only-setting').forEach(el => el.classList.remove('hidden'));
                finAssets.forEach(el => { el.style.display = 'none'; });
                if (moreAssetsWrapper) moreAssetsWrapper.style.display = 'none';
                sportsAssets.forEach(el => { el.style.display = 'inline-block'; el.classList.remove('hidden'); });
                
                if (fAs) fAs.classList.add('hidden');
                if (fRs) fRs.classList.add('hidden');
                if (sRs) sRs.classList.remove('hidden');

                const lw = document.getElementById('lw-chart-container');
                if (lw) lw.style.display = 'none';
                const sbt = document.getElementById('stats-bar-target');
                if (sbt) sbt.style.display = 'none';
                const spl = document.getElementById('sports-event-list');
                if (spl) { spl.style.display = 'block'; spl.classList.remove('hidden'); }
                
                if (typeof renderTradeSlip === 'function') renderTradeSlip();

                if (window.activeSportsEventMarket) {
                    const found = Array.from(sportsAssets).find(b => b.innerText.includes(window.activeSportsEventMarket));
                    if (found) found.click();
                    else filterSportsEvents('ALL');
                } else {
                    filterSportsEvents('ALL');
                }
            } else {
                finAssets.forEach(el => { el.style.display = ''; el.classList.remove('hidden'); });
                if (moreAssetsWrapper) moreAssetsWrapper.style.display = '';
                sportsAssets.forEach(el => { el.style.display = 'none'; el.classList.add('hidden'); });
                
                if (fAs) fAs.classList.remove('hidden');
                document.querySelectorAll('.finance-only-setting').forEach(el => el.classList.remove('hidden'));
                document.querySelectorAll('.sports-only-setting').forEach(el => el.classList.add('hidden'));
                if (fRs) fRs.classList.remove('hidden');
                if (sRs) sRs.classList.add('hidden');

                const lw = document.getElementById('lw-chart-container');
                if (lw) lw.style.display = 'block';
                const sbt = document.getElementById('stats-bar-target');
                if (sbt) sbt.style.display = 'flex';
                const spl = document.getElementById('sports-event-list');
                if (spl) { spl.style.display = 'none'; spl.classList.add('hidden'); }

                const slip = document.getElementById('sports-trade-slip-panel');
                if (slip) { slip.classList.add('hidden'); slip.classList.remove('flex'); }

                const found = Array.from(finAssets).find(b => b.innerText.includes(window.activeAsset));
                if (found) found.click();
                else if (typeof selectDashboardAsset === 'function') selectDashboardAsset('BTC');
            }

            if (window.lastDashboardStats) {
                window.lastDashboardStats.trading_universe = universe;
                if (typeof window.renderTradesContainer === 'function') window.renderTradesContainer(window.lastDashboardStats);
                if (typeof updateActivePositionHud === 'function') updateActivePositionHud(window.lastDashboardStats);
                if (typeof window.updateNavLivePnl === 'function') window.updateNavLivePnl(window.lastDashboardStats);
            }
            // Tab switching is decoupled: purely client-side view selection, no implicit backend mutation
        };

        window.configuredTradingUniverse = 'CRYPTO';
        window.setAutoTradingUniverse = function(univ, skipSave = false) {
            const raw = (univ || 'CRYPTO').toUpperCase();
            const normalized = (raw === 'FINANCIAL' || raw === 'CRYPTO') ? 'CRYPTO' : raw;
            window.configuredTradingUniverse = normalized;

            const btnCrypto = document.getElementById('btn-auto-univ-crypto');
            const btnSports = document.getElementById('btn-auto-univ-sports');
            const btnBoth = document.getElementById('btn-auto-univ-both');
            const badge = document.getElementById('auto-universe-label-badge');

            const activeClass = "flex-1 py-1.5 text-[10px] font-bold tracking-wider rounded-lg transition-all text-white bg-cyan-500/25 border border-cyan-500/40 shadow-sm flex items-center justify-center gap-1 cursor-pointer";
            const inactiveClass = "flex-1 py-1.5 text-[10px] font-bold tracking-wider rounded-lg transition-all text-gray-400 hover:text-white border border-transparent flex items-center justify-center gap-1 cursor-pointer";

            if (btnCrypto) btnCrypto.className = (normalized === 'CRYPTO') ? activeClass : inactiveClass;
            if (btnSports) btnSports.className = (normalized === 'SPORTS') ? activeClass : inactiveClass;
            if (btnBoth) btnBoth.className = (normalized === 'BOTH' || normalized === 'ALL') ? activeClass : inactiveClass;

            if (badge) {
                if (normalized === 'CRYPTO') {
                    badge.innerText = 'CRYPTO';
                    badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-cyan-500/15 text-cyan-400 border border-cyan-500/30';
                } else if (normalized === 'SPORTS') {
                    badge.innerText = 'SPORTS';
                    badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-amber-500/15 text-amber-400 border border-amber-500/30';
                } else if (normalized === 'BOTH' || normalized === 'ALL') {
                    badge.innerText = 'BOTH';
                    badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-400 border border-emerald-500/30';
                }
            }

            if (!skipSave && typeof saveConfig === 'function') {
                saveConfig();
            }
        };

        const SPORT_ICONS = {
            'NFL': '🏈',
            'NCAAF': '🏈',
            'MLB': '⚾',
            'NBA': '🏀',
            'NCAAB': '🏀',
            'WNBA': '🏀',
            'NHL': '🏒',
            'NPB': '⚾',
            'KBO': '⚾',
            'NPB/KBO': '⚾',
            'NPB_KBO': '⚾',
            'SOC': '⚽',
            'SOCCER': '⚽',
            'UFC': '🥊',
            'MMA': '🥊',
            'TEN': '🎾',
            'TENNIS': '🎾'
        };

        window.filterSportsEvents = function(sport) {
            window.sportsFilter = (window.sportsFilter === sport) ? 'ALL' : sport;
            const normFilter = String(window.sportsFilter || 'ALL').toUpperCase();
            document.querySelectorAll('.asset-btn-sports').forEach(btn => {
                const id = btn.id.replace('btn-asset-', '').toUpperCase();
                let on = false;
                if (normFilter === 'ALL') {
                    on = false;
                } else if ((normFilter === 'NPB/KBO' || normFilter === 'NPB_KBO' || normFilter === 'NPB' || normFilter === 'KBO') && (id.includes('NPB') || id.includes('KBO'))) {
                    on = true;
                } else if ((normFilter === 'SOC' || normFilter === 'SOCCER') && (id === 'SOC' || id === 'SOCCER')) {
                    on = true;
                } else if ((normFilter === 'TEN' || normFilter === 'TENNIS') && (id === 'TEN' || id === 'TENNIS')) {
                    on = true;
                } else if ((normFilter === 'UFC' || normFilter === 'MMA') && (id === 'UFC' || id === 'MMA')) {
                    on = true;
                } else if (normFilter === id) {
                    on = true;
                }
                btn.classList.toggle('bg-cyan-500/25', on);
                btn.classList.toggle('text-cyan-300', on);
                btn.classList.toggle('border-cyan-500/50', on);
            });
            // Immediately render any cached events for the selected sport and kick off fetch
            renderSportsEvents();
            loadSportsEvents(window.sportsFilter);
        };

        function isSportMatch(evt, f) {
            if (!f || f === 'ALL') return true;
            const filterNorm = f.toUpperCase();
            const eSport = String(evt.sport || '').toUpperCase();
            const eLeague = String(evt.league || evt.metadata?.league || '').toUpperCase();
            const eSeries = String(evt.series_ticker || evt.metadata?.series_ticker || '').toUpperCase();

            if (filterNorm === 'NPB/KBO' || filterNorm === 'NPB_KBO' || filterNorm === 'NPB-KBO' || filterNorm === 'NPB' || filterNorm === 'KBO') {
                return eSport.includes('NPB') || eSport.includes('KBO') ||
                       eLeague.includes('NPB') || eLeague.includes('KBO') ||
                       eSeries.includes('NPB') || eSeries.includes('KBO');
            }
            if (filterNorm === 'SOC' || filterNorm === 'SOCCER') {
                return eSport === 'SOC' || eSport === 'SOCCER' || eLeague === 'SOC' || eSeries.includes('EPL') || eSeries.includes('MLS') || eSeries.includes('UEFA') || eSeries.includes('WC');
            }
            if (filterNorm === 'TEN' || filterNorm === 'TENNIS') {
                return eSport === 'TEN' || eSport === 'TENNIS' || eLeague === 'TEN' || eSeries.includes('ATP') || eSeries.includes('WTA');
            }
            if (filterNorm === 'UFC' || filterNorm === 'MMA') {
                return eSport === 'UFC' || eSport === 'MMA' || eLeague === 'UFC' || eSeries.includes('UFC');
            }
            return eSport === filterNorm || eLeague === filterNorm || eSeries.includes(filterNorm);
        }

        window.__sportsLoading = false;
        window.__sportsReqId = 0;

        function renderSportsEvents() {
            const container = document.getElementById('sports-events-container');
            if (!container) return;
            const all = window.__sportsEventsCache || [];
            const f = window.sportsFilter || 'ALL';
            const list = all.filter(e => isSportMatch(e, f));
            const label = f === 'ALL' ? 'any sport' : f;

            if (list.length === 0) {
                if (window.__sportsLoading) {
                    container.innerHTML = '<div class="col-span-full text-center text-cyan-400 text-xs py-6 animate-pulse">⚡ Loading ' + label + ' AI picks...</div>';
                } else {
                    container.innerHTML = '<div class="col-span-full text-center text-gray-500 text-xs py-6">No active AI picks for ' + label + ' right now.</div>';
                }
                return;
            }
            container.innerHTML = '';
            list.forEach(evt => {
                const md = evt.metadata || {};
                const sport = String(evt.sport || '').toUpperCase();
                const league = String(evt.league || md.league || sport).toUpperCase();
                const icon = SPORT_ICONS[sport] || SPORT_ICONS[league] || '🏟️';

                // 1. Clean Matchup Name (e.g. "Chiba Lotte Marines vs Saitama Seibu Lions" or "Bellucci vs Muller")
                let rawMatchup = evt.matchup || md.matchup || evt.opponent || md.name || 'Sports Matchup';
                let cleanMatchup = rawMatchup.replace(/:\s*(Spread|Total\s*Runs?|Totals?|Game|Moneyline).*$/i, '').trim();
                if (!cleanMatchup) cleanMatchup = rawMatchup;

                // 2. Clean Market Type & Detailed Prop Info
                let marketType = evt.market_type || md.market_type_label || '';
                if (!marketType || marketType.toLowerCase().includes('vs') || marketType.length > 20) {
                    const tk = (evt.event_ticker || '').toUpperCase();
                    if (evt.prop_type === 'Player Prop' || ['KXNHLGOAL', 'KXNHLSHOT', 'KXMLBHRR', 'KXMLBHIT', 'KXMLBHR', 'KXMLBKS', 'KXNFLTD', 'PROP', 'GOAL', 'SHOT', 'HRR'].some(k => tk.includes(k))) marketType = 'Player Prop';
                    else if (tk.includes('SPREAD')) marketType = 'Spread';
                    else if (tk.includes('TOTAL')) marketType = (league === 'NPB' || league === 'KBO' || league === 'MLB') ? 'Total Runs' : 'Totals';
                    else marketType = 'Moneyline';
                }

                const propType = evt.prop_type || md.prop_type || marketType;
                const line = evt.line || md.line || '';
                const spreadAmount = evt.spread_amount || md.spread_amount || '';
                const overUnderAmount = evt.over_under_amount || md.over_under_amount || '';
                const strikeDetails = evt.strike_details || md.strike_details || '';

                let propBadgeClass = 'bg-blue-500/20 text-blue-300 border-blue-500/40';
                if (propType === 'Spread') {
                    propBadgeClass = 'bg-purple-500/20 text-purple-300 border-purple-500/40';
                } else if (propType.includes('Total') || propType.includes('O/U')) {
                    propBadgeClass = 'bg-amber-500/20 text-amber-300 border-amber-500/40';
                } else if (propType === 'Player Prop') {
                    propBadgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
                }

                let linePill = '';
                if (line && line !== 'Moneyline') {
                    linePill = `<span class="px-1.5 py-0.5 rounded font-black text-cyan-200 bg-cyan-950/70 border border-cyan-500/30 text-[9px] font-mono tracking-wide">${line}</span>`;
                }

                let strikeDetailsRow = '';
                if (strikeDetails && strikeDetails.toLowerCase() !== cleanMatchup.toLowerCase()) {
                    strikeDetailsRow = `<div class="text-[10px] text-gray-300 font-mono flex items-center gap-1.5 mt-0.5 truncate" title="${strikeDetails}"><span class="text-cyan-400 shrink-0">🎯</span> <span class="truncate">${strikeDetails}</span></div>`;
                }

                // 3. Date & Start Time
                let when = evt.game_time || md.game_time || md.start_label || evt.start_time || '';
                if (!when && evt.event_ticker) {
                    const m = evt.event_ticker.match(/-(\d{2})([A-Z]{3})(\d{2})(\d{4})/i);
                    if (m) {
                        const mon = m[2].charAt(0).toUpperCase() + m[2].slice(1).toLowerCase();
                        const dd = parseInt(m[3], 10);
                        const hh = parseInt(m[4].slice(0, 2), 10);
                        const mn = m[4].slice(2);
                        const ampm = hh >= 12 ? 'PM' : 'AM';
                        const displayHr = hh % 12 === 0 ? 12 : hh % 12;
                        when = `${mon} ${dd}, ${displayHr}:${mn} ${ampm} ET`;
                    } else {
                        const mDate = evt.event_ticker.match(/-(\d{2})([A-Z]{3})(\d{2})/i);
                        if (mDate) {
                            const mon = mDate[2].charAt(0).toUpperCase() + mDate[2].slice(1).toLowerCase();
                            const dd = parseInt(mDate[3], 10);
                            when = `${mon} ${dd}`;
                        }
                    }
                }
                if (when.includes('@')) {
                    when = when.replace('@', ',').replace(/\s+/g, ' ');
                }

                // 4. Pricing details
                const yesPriceVal = evt.yes_ask != null ? Math.round(evt.yes_ask * 100) : (md.yes_ask != null ? Math.round(md.yes_ask * 100) : null);
                const noPriceVal = evt.no_ask != null ? Math.round(evt.no_ask * 100) : (md.no_ask != null ? Math.round(md.no_ask * 100) : (yesPriceVal != null ? (100 - yesPriceVal) : null));
                const yesPriceLabel = (yesPriceVal != null && yesPriceVal > 0 && yesPriceVal < 100) ? ` ${yesPriceVal}¢` : '';
                const noPriceLabel = (noPriceVal != null && noPriceVal > 0 && noPriceVal < 100) ? ` ${noPriceVal}¢` : '';

                // 5. AI Prediction Details
                const edge = parseFloat(evt.edge_pct) || 0;
                const conf = parseFloat(evt.confidence_pct) || 0;
                const rawPick = evt.ai_pick || evt.predicted_team || md.name || '';
                const hasAiPick = !!(conf > 0 && rawPick && !rawPick.toLowerCase().includes(' vs ') && rawPick.toLowerCase() !== cleanMatchup.toLowerCase());
                const aiPickTeam = hasAiPick ? rawPick : null;

                let isRedundantStrike = false;
                if (hasAiPick && strikeDetails && strikeDetails.toLowerCase().includes(aiPickTeam.toLowerCase()) && (propType === 'Moneyline' || propType === 'Spread')) {
                    isRedundantStrike = true;
                }
                if (strikeDetails && strikeDetails.toLowerCase() !== cleanMatchup.toLowerCase() && !isRedundantStrike) {
                    strikeDetailsRow = <div class="text-[10px] text-gray-300 font-mono flex items-center gap-1.5 mt-0.5 truncate" title=""><span class="text-cyan-400 shrink-0">??</span> <span class="truncate"></span></div>;
                }


                // 6. YES / NO option labels
                const matchupParts = cleanMatchup.split(/\s+(?:vs\.?|@|v)\s+/i).map(s => s.trim()).filter(Boolean);
                let yesSub = '';
                let noSub = '';
                if (hasAiPick) {
                    yesSub = aiPickTeam;
                    if (matchupParts.length === 2) {
                        noSub = aiPickTeam.toLowerCase().includes(matchupParts[0].toLowerCase()) ? matchupParts[1] : matchupParts[0];
                    } else {
                        noSub = 'Opponent';
                    }
                } else if (matchupParts.length === 2) {
                    yesSub = matchupParts[0];
                    noSub = matchupParts[1];
                } else {
                    yesSub = 'YES';
                    noSub = 'NO';
                }

                let yesBtnSub = yesSub;
                let noBtnSub = noSub;
                if (propType === 'Spread' && spreadAmount) {
                    yesBtnSub = spreadAmount;
                } else if ((propType.includes('Total') || propType.includes('O/U')) && overUnderAmount) {
                    yesBtnSub = `Over ${overUnderAmount}`;
                    noBtnSub = `Under ${overUnderAmount}`;
                } else if (propType === 'Player Prop' && line) {
                    yesBtnSub = line;
                    noBtnSub = `Under ${line}`;
                }

                const ticker = evt.ticker || evt.event_ticker || md.name || '';
                const yesPickLabel = (hasAiPick ? aiPickTeam : yesSub) + ' (YES)';
                const noPickLabel = (propType === 'Player Prop') ? (aiPickTeam || yesSub) + ' (NO)' : (noSub + ' (NO)');

                const el = document.createElement('div');
                el.className = 'bg-[#101726]/95 hover:bg-[#151f33] border border-white/10 hover:border-cyan-500/40 rounded-xl p-3 flex flex-col justify-between transition-all duration-200 shadow-md group relative';
                el.innerHTML = `
                    <!-- Top Line: Sport/League Badge + Prop Type Badge + Line Pill + Date/Time -->
                    <div class="flex items-center justify-between gap-2 pb-2 border-b border-white/5 text-[10px]">
                        <div class="flex items-center gap-1.5 min-w-0 flex-wrap">
                            <span class="text-xs shrink-0">${icon}</span>
                            <span class="px-1.5 py-0.5 rounded font-bold uppercase tracking-wider bg-white/10 text-cyan-300 text-[9px]">${league}</span>
                            <span class="px-1.5 py-0.5 rounded font-bold uppercase tracking-wider ${propBadgeClass} text-[9px]">${propType}</span>
                            ${linePill}
                        </div>
                        <div class="flex items-center gap-1.5 shrink-0 text-gray-400 font-mono text-[9.5px]">
                            ${evt.is_today ? `<span class="px-1.5 py-0.5 rounded font-black tracking-wider bg-emerald-500/20 text-emerald-300 text-[8.5px]">TODAY</span>` : ''}
                            <svg class="w-3 h-3 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                            <span>${when || 'Live/Upcoming'}</span>
                        </div>
                    </div>

                    <!-- Matchup Line + Strike Details -->
                    <div class="py-2.5 cursor-pointer" onclick="querySportsAI('${ticker}', window.__sportsEventsCache.find(x => (x.ticker === '${ticker}' || x.event_ticker === '${ticker}')) || {})">
                        <div class="text-[13px] sm:text-[14px] font-black text-white tracking-wide leading-snug group-hover:text-cyan-200 transition-colors">${cleanMatchup}</div>
                        ${strikeDetailsRow}
                    </div>

                    <!-- AI Prediction Row / Badge -->
                    <div class="bg-black/50 rounded-lg px-2.5 py-2 border border-white/5 flex items-center justify-between gap-2 mb-2.5">
                        ${hasAiPick ? `
                            <div class="flex items-center gap-1.5 min-w-0">
                                <span class="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-black text-[9px] uppercase tracking-wider shrink-0">AI PICK</span>
                                <span class="text-xs font-bold text-white truncate">${aiPickTeam}</span>
                            </div>
                            <div class="flex items-center gap-2 shrink-0 font-mono text-[11px]">
                                <span class="font-bold ${conf >= 65 ? 'text-emerald-400' : 'text-amber-300'}">${conf.toFixed(1)}% Win</span>
                                ${edge > 0 ? `<span class="px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-bold text-[9px]">+${edge.toFixed(1)}% Edge</span>` : ''}
                            </div>
                        ` : `
                            <div class="flex items-center gap-1.5">
                                <span class="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
                                <span class="text-[10px] font-bold text-gray-400 uppercase tracking-wider">AI Ready • Ready for Live Prediction</span>
                            </div>
                            <button onclick="event.stopPropagation(); querySportsAI('${ticker}', window.__sportsEventsCache.find(x => (x.ticker === '${ticker}' || x.event_ticker === '${ticker}')) || {})" class="text-[9px] font-bold text-cyan-400 hover:text-cyan-300 uppercase tracking-wider">Analyze ⚡</button>
                        `}
                    </div>

                    <!-- Action Buttons: YES / NO / AI Slip -->
                    <div class="flex items-center gap-1.5 pt-0.5">
                        <button onclick="event.stopPropagation(); addPredictionToSlip('${ticker}', '${yesPickLabel.replace(/'/g, "\\'")}', '${hasAiPick ? conf.toFixed(1) : 'N/A'}', '${hasAiPick ? edge.toFixed(1) : 'N/A'}', 'YES', {prop_type:'${propType}', line:'${line.replace(/'/g, "\\'")}', spread_amount:'${spreadAmount}', over_under_amount:'${overUnderAmount}', strike_details:'${strikeDetails.replace(/'/g, "\\'")}'})" class="flex-1 py-1.5 px-2 bg-emerald-600/20 hover:bg-emerald-600/35 border border-emerald-500/40 text-emerald-300 rounded-lg font-bold text-[10px] uppercase tracking-wider flex items-center justify-center gap-1 transition-all active:scale-95 cursor-pointer shadow-sm">
                            <span class="font-black">YES${yesPriceLabel}</span>
                            <span class="text-[9px] font-normal opacity-75 truncate max-w-[85px]">• ${yesBtnSub}</span>
                        </button>
                        <button onclick="event.stopPropagation(); addPredictionToSlip('${ticker}', '${noPickLabel.replace(/'/g, "\\'")}', 'N/A', 'N/A', 'NO', {prop_type:'${propType}', line:'${line.replace(/'/g, "\\'")}', spread_amount:'${spreadAmount}', over_under_amount:'${overUnderAmount}', strike_details:'${strikeDetails.replace(/'/g, "\\'")}'})" class="flex-1 py-1.5 px-2 bg-rose-600/20 hover:bg-rose-600/35 border border-rose-500/40 text-rose-300 rounded-lg font-bold text-[10px] uppercase tracking-wider flex items-center justify-center gap-1 transition-all active:scale-95 cursor-pointer shadow-sm">
                            <span class="font-black">NO${noPriceLabel}</span>
                            <span class="text-[9px] font-normal opacity-75 truncate max-w-[85px]">• ${noBtnSub}</span>
                        </button>
                        <button onclick="event.stopPropagation(); querySportsAI('${ticker}', window.__sportsEventsCache.find(x => (x.ticker === '${ticker}' || x.event_ticker === '${ticker}')) || {})" title="AI Model Insight" class="p-1.5 px-2.5 bg-white/5 hover:bg-white/10 border border-white/10 text-cyan-300 hover:text-cyan-200 rounded-lg font-bold text-[10px] flex items-center justify-center transition-all cursor-pointer">
                            ⚡
                        </button>
                    </div>
                `;
                container.appendChild(el);
            });
        }

        // Global Trade Slip state
        window.sportsTradeSlip = [];
        document.addEventListener('DOMContentLoaded', renderTradeSlip);

        function renderTradeSlip() {
            let panel = document.getElementById('sports-trade-slip-panel');
            if (!panel) return;
            
            if (window.currentUniverse !== 'SPORTS' || !window.sportsTradeSlip || window.sportsTradeSlip.length === 0) {
                panel.classList.add('hidden');
                panel.classList.remove('flex');
                panel.innerHTML = '';
                return;
            }

            panel.classList.remove('hidden');
            panel.classList.add('flex');
            
                const sportsTradeSize = parseFloat(document.getElementById('sports-trade-size-dollars')?.value || document.getElementById('sports-wager-dollars')?.value || 10.0) || 10.0;
                let html = `
                <div class="p-3 border-b border-white/10 bg-gradient-to-r from-cyan-900/30 to-transparent flex justify-between items-center rounded-t-xl">
                    <div class="text-xs font-black text-cyan-300 uppercase tracking-wider">🧾 Trade Slip (${window.sportsTradeSlip.length})</div>
                    <button onclick="window.sportsTradeSlip=[]; renderTradeSlip();" class="text-gray-400 hover:text-white">✖</button>
                </div>
                <div class="p-3 space-y-2 max-h-60 overflow-y-auto">
            `;
            window.sportsTradeSlip.forEach((item, index) => {
                const propType = item.prop_type || 'Pick';
                let propBadgeClass = 'bg-blue-500/20 text-blue-300 border-blue-500/35';
                if (propType === 'Spread') propBadgeClass = 'bg-purple-500/20 text-purple-300 border-purple-500/35';
                else if (propType.includes('Total') || propType.includes('O/U')) propBadgeClass = 'bg-amber-500/20 text-amber-300 border-amber-500/35';
                else if (propType === 'Player Prop') propBadgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/35';

                const propBadge = `<span class="px-1.5 py-0.5 rounded font-black text-[8.5px] uppercase ${propBadgeClass}">${propType}</span>`;
                const lineBadge = item.line && item.line !== 'Moneyline' ? `<span class="px-1.5 py-0.5 rounded font-bold text-[8.5px] bg-black/60 text-cyan-300 border border-cyan-500/30 font-mono">${item.line}</span>` : '';
                const sideColor = (item.side || 'YES').toUpperCase() === 'YES' ? 'text-emerald-400' : 'text-rose-400';

                html += `
                    <div class="p-2.5 bg-black/40 border border-white/5 rounded-lg relative group">
                        <button onclick="window.sportsTradeSlip.splice(${index}, 1); renderTradeSlip();" class="absolute top-1.5 right-1.5 text-gray-500 hover:text-rose-400 cursor-pointer">✖</button>
                        <div class="flex items-center gap-1.5 mb-1 flex-wrap pr-5">
                            ${propBadge}
                            ${lineBadge}
                            <span class="text-[9px] font-mono text-gray-400 truncate max-w-[130px]">${item.ticker}</span>
                        </div>
                        <div class="text-xs font-bold text-white flex items-center gap-1.5">
                            <span class="${sideColor} font-black">${item.side || 'YES'}</span>
                            <span class="truncate">${item.team}</span>
                        </div>
                        ${item.strike_details ? `<div class="text-[9.5px] text-gray-300 font-mono mt-0.5 truncate">🎯 ${item.strike_details}</div>` : ''}
                        <div class="text-[9px] text-emerald-400 mt-1 font-mono">${item.conf !== 'N/A' ? `Conf: ${item.conf}% | Edge: ${item.edge}%` : 'Manual Pick Selection'}</div>
                    </div>
                `;
            });
            html += `
                </div>
                <div class="p-3 border-t border-white/10 space-y-2">
                    <div class="flex justify-center gap-4 text-xs font-bold text-gray-300">
                        <label class="flex items-center gap-1 cursor-pointer">
                            <input type="radio" name="trade_type" value="single" checked class="accent-cyan-500">
                            Single Trades
                        </label>
                        <label class="flex items-center gap-1 cursor-pointer">
                            <input type="radio" name="trade_type" value="combo" class="accent-cyan-500">
                            Combo (Parlay)
                        </label>
                    </div>
                    <button onclick="executeTradeSlip()" class="w-full py-2 bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs uppercase tracking-wider rounded transition-colors" id="btn-execute-slip">Approve & Execute Trades ($${sportsTradeSize})</button>
                </div>
            `;
            panel.innerHTML = html;
        }

        function showToast(msg, type = 'info') {
            let container = document.getElementById('toastContainer');
            if (!container) {
                container = document.createElement('div');
                container.id = 'toastContainer';
                container.className = 'fixed top-4 left-1/2 -translate-x-1/2 z-[99999] flex flex-col items-center gap-2 pointer-events-none w-11/12 max-w-sm';
                document.body.appendChild(container);
            }
            const el = document.createElement('div');
            el.className = `px-4 py-2.5 rounded-lg text-xs font-semibold shadow-lg text-white pointer-events-auto transition-all duration-300 transform translate-y-0 opacity-100 ${
                type === 'success' ? 'bg-emerald-600' :
                type === 'error' ? 'bg-rose-600' :
                type === 'warning' ? 'bg-amber-600' : 'bg-cyan-600'
            }`;
            el.textContent = msg;
            container.appendChild(el);
            setTimeout(() => {
                el.style.opacity = '0';
                el.style.transform = 'translateY(-10px)';
                setTimeout(() => el.remove(), 300);
            }, 4000);
        }

        async function executeTradeSlip() {
            const btn = document.getElementById('btn-execute-slip');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'EXECUTING...';
            }
            
            const typeEls = document.getElementsByName('trade_type');
            let isCombo = false;
            for (let i = 0; i < typeEls.length; i++) {
                if (typeEls[i].checked && typeEls[i].value === 'combo') {
                    isCombo = true;
                }
            }
            
            const sportsTradeSize = parseFloat(document.getElementById('sports-trade-size-dollars')?.value || document.getElementById('sports-wager-dollars')?.value || 10.0) || 10.0;
            
            let activeUid = null;
            if (window.lastDashboardStats && window.lastDashboardStats.user_id) {
                activeUid = window.lastDashboardStats.user_id;
            } else if (window.currentUser && window.currentUser.id) {
                activeUid = window.currentUser.id;
            } else {
                try {
                    const token = localStorage.getItem('saas_token');
                    if (token) {
                        const base64Url = token.split('.')[1];
                        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
                        const jsonPayload = decodeURIComponent(atob(base64).split('').map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)).join(''));
                        const payload = JSON.parse(jsonPayload);
                        if (payload && payload.user_id) {
                            activeUid = payload.user_id;
                        }
                    }
                } catch(e) {}
            }
            if (!activeUid) {
                activeUid = 7;
            }

            try {
                if (isCombo && window.sportsTradeSlip.length > 1) {
                    try {
                        const tickers = window.sportsTradeSlip.map(i => i.ticker).join(',');
                        const teams = window.sportsTradeSlip.map(i => i.team).join(',');
                        const userTok = localStorage.getItem('saas_token');
                        const authH = userTok ? { 'Authorization': 'Bearer ' + userTok, 'X-User-Id': String(activeUid) } : { 'X-User-Id': String(activeUid) };
                        const comboUrl = (window.API_BASE_URL || '') + '/api/engine/sports/combo?event_tickers=' + encodeURIComponent(tickers) + '&teams=' + encodeURIComponent(teams) + '&trade_size=' + encodeURIComponent(sportsTradeSize) + '&user_id=' + encodeURIComponent(activeUid);
                        const res = await fetch(comboUrl, { method: 'POST', headers: authH });
                        const data = await res.json();
                        if (res.ok && data.combo_executed) {
                            showToast(`Combo trade executed (${data.trades.length} legs)`, 'success');
                        } else {
                            const errText = data.error || (data.errors && data.errors.length ? data.errors.map(e => e.error).join('; ') : 'Combo execution failed');
                            showToast(`Combo failed: ${errText}`, 'error');
                            console.error("Combo Trade failed", data);
                        }
                    } catch(e) {
                        showToast(`Combo network error: ${e.message}`, 'error');
                        console.error("Execution error", e);
                    }
                } else {
                    for (const item of window.sportsTradeSlip) {
                        try {
                            const team = item.team;
                            const explicitSide = item.side || (team && team.includes('(NO)') ? 'NO' : 'YES');
                            const sideParam = `&side=${encodeURIComponent(explicitSide)}`;
                            const url = (window.API_BASE_URL || '') + '/api/engine/sports/execute?event_ticker=' + encodeURIComponent(item.ticker) + '&manual_team=' + encodeURIComponent(team) + '&trade_size=' + encodeURIComponent(sportsTradeSize) + '&user_id=' + encodeURIComponent(activeUid) + sideParam;
                            const userTok = localStorage.getItem('saas_token');
                            const authH = userTok ? { 'Authorization': 'Bearer ' + userTok, 'X-User-Id': String(activeUid) } : { 'X-User-Id': String(activeUid) };
                            const res = await fetch(url, { method: 'POST', headers: authH });
                            const data = await res.json();
                            if (res.ok && data.executed) {
                                showToast(`Trade placed: ${data.trade?.ticker || item.ticker} (${data.trade?.mode || 'LIVE'})`, 'success');
                            } else {
                                showToast(`Trade failed: ${data.error || 'Execution failed'}`, 'error');
                                console.error("Trade failed", data);
                            }
                        } catch(e) {
                            showToast(`Trade network error: ${e.message}`, 'error');
                            console.error("Execution error", e);
                        }
                    }
                }
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = `Approve & Execute Trades ($${sportsTradeSize})`;
                }
            }
            
            window.sportsTradeSlip = [];
            renderTradeSlip();
            
            // Reload the events to clear processing states
            loadSportsEvents(window.sportsFilter);
            
            if (typeof loadDashboard === 'function') {
                loadDashboard();
            }
            // Re-fetch trades
            if (typeof fetchKalshiTrades === 'function') {
                setTimeout(fetchKalshiTrades, 1500);
            }
        }
        window.executeSportsTradeSlip = executeTradeSlip;

        function closeSportsAIPopup() {
            const popup = document.getElementById('sports-ai-popup');
            if (popup) {
                popup.remove();
            }
        }

        function addPredictionToSlip(ticker, team, conf, edge, side='YES', extraDetails={}) {
            if (!Array.isArray(window.sportsTradeSlip)) window.sportsTradeSlip = [];
            window.sportsTradeSlip.push({ ticker, team, conf, edge, side, ...(extraDetails || {}) });
            renderTradeSlip();
            closeSportsAIPopup();
            if (typeof showToast === 'function') {
                showToast(`Added ${team} to Trade Slip`, 'success');
            }
            const panel = document.getElementById('sports-trade-slip-panel');
            if (panel && !panel.classList.contains('hidden')) {
                panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }

        async function querySportsAI(ticker, evt) {
            if (!ticker) return;
            
            closeSportsAIPopup();
            
            const fullEvt = evt || (window.__sportsEventsCache ? window.__sportsEventsCache.find(x => x.event_ticker === ticker) : {}) || {};
            const md = fullEvt.metadata || {};
            const sport = String(fullEvt.sport || md.sport || 'SPORTS').toUpperCase();
            const league = String(fullEvt.league || md.league || sport).toUpperCase();
            const icon = (typeof SPORT_ICONS !== 'undefined' && (SPORT_ICONS[sport] || SPORT_ICONS[league])) ? (SPORT_ICONS[sport] || SPORT_ICONS[league]) : '🏟️';
            const rawMatchup = fullEvt.matchup || md.matchup || ticker;
            const cleanMatchup = rawMatchup.replace(/:\s*(Spread|Total\s*Runs?|Totals?|Game|Moneyline).*$/i, '').trim() || rawMatchup;
            const gameTime = fullEvt.game_time || md.game_time || 'Upcoming / Today';
            
            const popup = document.createElement('div');
            popup.id = 'sports-ai-popup';
            popup.className = 'fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[92%] max-w-md bg-[#0c0c10]/95 backdrop-blur-3xl border border-cyan-500/50 rounded-2xl shadow-[0_20px_70px_rgba(0,200,255,0.15)] z-[9999] overflow-hidden flex flex-col';
            popup.innerHTML = `
                <div class="p-3.5 border-b border-cyan-500/30 bg-gradient-to-r from-cyan-900/40 via-blue-900/20 to-transparent flex justify-between items-center">
                    <div class="text-sm font-black text-white flex items-center gap-2">
                        <span class="text-base">${icon}</span>
                        <span class="px-1.5 py-0.5 rounded font-black text-[9px] uppercase bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">${league}</span>
                        <span class="tracking-wide">Market & Prediction Intel</span>
                    </div>
                    <button onclick="closeSportsAIPopup()" class="text-gray-400 hover:text-white cursor-pointer px-1 text-sm font-bold">✕</button>
                </div>
                <div class="p-5" id="sports-ai-popup-content">
                    <div class="text-center py-6">
                        <div class="text-cyan-400 text-sm animate-pulse font-mono mb-2">Analyzing market data & odds...</div>
                        <div class="text-[10px] text-gray-500">Connecting to Local AI & Kalshi Orderbook</div>
                    </div>
                </div>
            `;
            document.body.appendChild(popup);
            
            try {
                const titleParam = fullEvt && (fullEvt.predicted_team || md.name) ? '&title=' + encodeURIComponent(fullEvt.predicted_team || md.name) : '';
                const sportParam = fullEvt && (fullEvt.sport || fullEvt.league) ? '&sport=' + encodeURIComponent(fullEvt.sport || fullEvt.league) : '';
                
                const token = localStorage.getItem('saas_token') || localStorage.getItem('app_api_token') || '';
                const fetchOpts = {
                    headers: token ? { 'Authorization': `Bearer ${token}` } : {}
                };
                
                const res = await fetch((window.API_BASE_URL || '') + '/api/engine/sports/predict?event_ticker=' + encodeURIComponent(ticker) + '&execute=false' + titleParam + sportParam, fetchOpts);
                if (!res.ok) throw new Error('HTTP ' + res.status);
                const data = await res.json();
                
                const pred = data.prediction || {};
                const details = data.event_details || {};
                const propType = details.prop_type || pred.prop_type || fullEvt.prop_type || md.prop_type || 'Moneyline';
                const line = details.line || pred.line || fullEvt.line || md.line || (propType === 'Moneyline' ? 'Moneyline' : '');
                const spreadAmount = details.spread_amount || pred.spread_amount || fullEvt.spread_amount || md.spread_amount || '';
                const overUnderAmount = details.over_under_amount || pred.over_under_amount || fullEvt.over_under_amount || md.over_under_amount || '';
                const strikeDetails = details.strike_details || pred.strike_details || fullEvt.strike_details || md.strike_details || '';

                const team = pred.predicted_team || fullEvt.predicted_team || ticker;
                const conf = pred.confidence_pct != null ? parseFloat(pred.confidence_pct).toFixed(1) : (fullEvt.confidence_pct ? parseFloat(fullEvt.confidence_pct).toFixed(1) : '55.0');
                const edge = pred.edge_pct != null ? parseFloat(pred.edge_pct).toFixed(1) : (fullEvt.edge_pct ? parseFloat(fullEvt.edge_pct).toFixed(1) : '5.0');
                
                const yesPriceVal = fullEvt.yes_ask != null ? Math.round(fullEvt.yes_ask * 100) : (md.yes_ask != null ? Math.round(md.yes_ask * 100) : null);
                const noPriceVal = fullEvt.no_ask != null ? Math.round(fullEvt.no_ask * 100) : (md.no_ask != null ? Math.round(md.no_ask * 100) : (yesPriceVal != null ? (100 - yesPriceVal) : null));
                
                let propBadgeClass = 'bg-blue-500/20 text-blue-300 border-blue-500/40';
                if (propType === 'Spread') propBadgeClass = 'bg-purple-500/20 text-purple-300 border-purple-500/40';
                else if (propType.includes('Total') || propType.includes('O/U')) propBadgeClass = 'bg-amber-500/20 text-amber-300 border-amber-500/40';
                else if (propType === 'Player Prop') propBadgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';

                const content = document.getElementById('sports-ai-popup-content');
                if (content) {
                    content.innerHTML = `
                        <div class="space-y-3 text-left">
                            <!-- Event Matchup & League Details -->
                            <div class="bg-black/50 p-3 rounded-xl border border-white/10">
                                <div class="flex items-center justify-between gap-2 mb-1.5 flex-wrap">
                                    <div class="flex items-center gap-1.5 flex-wrap">
                                        <span class="px-1.5 py-0.5 rounded font-black text-[9px] uppercase ${propBadgeClass}">${propType}</span>
                                        ${line && line !== 'Moneyline' ? `<span class="px-1.5 py-0.5 rounded font-black text-[9px] bg-cyan-950/80 text-cyan-200 border border-cyan-500/30 font-mono">${line}</span>` : ''}
                                    </div>
                                    <span class="text-[9.5px] font-mono text-gray-400">${gameTime}</span>
                                </div>
                                <div class="text-[14px] sm:text-[15px] font-black text-white leading-snug">${cleanMatchup}</div>
                                ${strikeDetails && strikeDetails.toLowerCase() !== cleanMatchup.toLowerCase() ? `
                                    <div class="text-[10px] text-gray-300 font-mono mt-1.5 pt-1.5 border-t border-white/5 flex items-center gap-1.5">
                                        <span class="text-cyan-400 shrink-0">🎯</span>
                                        <span>${strikeDetails}</span>
                                    </div>
                                ` : ''}
                            </div>

                            <!-- Recommended Pick Hero Box -->
                            <div class="bg-gradient-to-br from-emerald-950/40 via-black/70 to-[#0e1626] p-3 rounded-xl border border-emerald-500/40">
                                <div class="flex items-center justify-between mb-0.5">
                                    <span class="text-[9px] font-bold text-emerald-400 uppercase tracking-widest">✦ AI Recommended Pick</span>
                                    ${spreadAmount ? `<span class="text-[9px] font-mono text-purple-300 font-bold">Spread: ${spreadAmount}</span>` : (overUnderAmount ? `<span class="text-[9px] font-mono text-amber-300 font-bold">Line: ${overUnderAmount}</span>` : '')}
                                </div>
                                <div class="text-[16px] font-black text-white leading-tight">${team}</div>
                            </div>

                            <!-- Market Metrics Grid -->
                            <div class="grid grid-cols-4 gap-1.5">
                                <div class="p-2 bg-black/40 rounded-lg border border-white/5 text-center">
                                    <div class="text-[8px] text-gray-500 font-bold uppercase tracking-wider">Conviction</div>
                                    <div class="text-xs font-black ${parseFloat(conf) >= 60 ? 'text-emerald-400' : 'text-amber-400'}">${conf}%</div>
                                </div>
                                <div class="p-2 bg-black/40 rounded-lg border border-white/5 text-center">
                                    <div class="text-[8px] text-gray-500 font-bold uppercase tracking-wider">Edge</div>
                                    <div class="text-xs font-black text-cyan-400">+${edge}%</div>
                                </div>
                                <div class="p-2 bg-black/40 rounded-lg border border-white/5 text-center">
                                    <div class="text-[8px] text-gray-500 font-bold uppercase tracking-wider">YES Ask</div>
                                    <div class="text-xs font-black text-emerald-300">${yesPriceVal != null ? yesPriceVal + '¢' : '--'}</div>
                                </div>
                                <div class="p-2 bg-black/40 rounded-lg border border-white/5 text-center">
                                    <div class="text-[8px] text-gray-500 font-bold uppercase tracking-wider">NO Ask</div>
                                    <div class="text-xs font-black text-rose-300">${noPriceVal != null ? noPriceVal + '¢' : '--'}</div>
                                </div>
                            </div>
                        </div>

                        <!-- Action Buttons -->
                        <div class="flex flex-col gap-2 mt-4 pt-1 border-t border-white/5">
                            <div class="flex gap-2">
                                <button onclick="addPredictionToSlip('${ticker}', '${team.replace(/'/g, "\\'")}', '${conf}', '${edge}', 'YES', {prop_type:'${propType}', line:'${line.replace(/'/g, "\\'")}', spread_amount:'${spreadAmount}', over_under_amount:'${overUnderAmount}', strike_details:'${strikeDetails.replace(/'/g, "\\'")}'})" class="flex-1 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white font-black text-[10px] uppercase tracking-wider rounded-lg transition-all active:scale-95 shadow-[0_0_15px_rgba(6,182,212,0.4)] cursor-pointer">
                                    + Add AI Pick
                                </button>
                                <button onclick="addPredictionToSlip('${ticker}', '${team.replace(/'/g, "\\'")} (Manual YES)', 'N/A', 'N/A', 'YES', {prop_type:'${propType}', line:'${line.replace(/'/g, "\\'")}', spread_amount:'${spreadAmount}', over_under_amount:'${overUnderAmount}', strike_details:'${strikeDetails.replace(/'/g, "\\'")}'})" class="flex-1 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-black text-[10px] uppercase tracking-wider rounded-lg transition-all active:scale-95 shadow-[0_0_15px_rgba(16,185,129,0.4)] cursor-pointer">
                                    + YES
                                </button>
                                <button onclick="addPredictionToSlip('${ticker}', '${team.replace(/'/g, "\\'")} (Manual NO)', 'N/A', 'N/A', 'NO', {prop_type:'${propType}', line:'${line.replace(/'/g, "\\'")}', spread_amount:'${spreadAmount}', over_under_amount:'${overUnderAmount}', strike_details:'${strikeDetails.replace(/'/g, "\\'")}'})" class="flex-1 py-2.5 bg-rose-600 hover:bg-rose-500 text-white font-black text-[10px] uppercase tracking-wider rounded-lg transition-all active:scale-95 shadow-[0_0_15px_rgba(225,29,72,0.4)] cursor-pointer">
                                    + NO
                                </button>
                            </div>
                        </div>
                    `;
                }
            } catch (e) {
                const content = document.getElementById('sports-ai-popup-content');
                if (content) {
                    content.innerHTML = `
                        <div class="text-rose-400 text-sm mb-4">Error querying AI: ${e.message}</div>
                        <button onclick="closeSportsAIPopup()" class="py-2 px-4 bg-gray-800 text-white rounded">Close</button>
                    `;
                }
            }
        }

        async function loadSportsEvents(sport = null) {
            const container = document.getElementById('sports-events-container');
            if (!container) return;
            const reqId = ++window.__sportsReqId;
            const targetSport = sport || window.sportsFilter || 'ALL';
            window.__sportsLoading = true;

            const currentCache = window.__sportsEventsCache || [];
            const hasExisting = currentCache.some(e => isSportMatch(e, targetSport));
            if (!hasExisting) {
                renderSportsEvents();
            }

            try {
                const sportParam = targetSport && targetSport !== 'ALL' ? '&sport=' + encodeURIComponent(targetSport) : '';
                const token = localStorage.getItem('saas_token') || localStorage.getItem('app_api_token') || '';
                const fetchOpts = {
                    cache: 'no-store',
                    headers: token ? { 'Authorization': `Bearer ${token}` } : {}
                };
                const res = await fetch((window.API_BASE_URL || '') + '/api/engine/sports/events?t=' + Date.now() + sportParam, fetchOpts);
                if (!res.ok) throw new Error('HTTP ' + res.status);
                const data = await res.json();

                // If another tab switch occurred while waiting, ignore stale response
                if (reqId !== window.__sportsReqId) return;

                const newEvents = Array.isArray(data.events) ? data.events : [];
                if (targetSport && targetSport !== 'ALL') {
                    const otherEvents = (window.__sportsEventsCache || []).filter(e => !isSportMatch(e, targetSport));
                    window.__sportsEventsCache = [...otherEvents, ...newEvents];
                } else {
                    window.__sportsEventsCache = newEvents;
                }
                window.__sportsLoading = false;
                renderSportsEvents();
            } catch (e) {
                if (reqId !== window.__sportsReqId) return;
                window.__sportsLoading = false;
                if (!window.__sportsEventsCache || !window.__sportsEventsCache.length) {
                    container.innerHTML = '<div class="col-span-full text-center text-red-400 text-xs py-6">Failed to load picks: ' + e.message + '</div>';
                } else {
                    renderSportsEvents();
                }
            }
        }
        async function selectDashboardAsset(asset) {
            asset = (asset || 'BTC').toUpperCase();
            if (window.currentAsset === asset && window.lastCandle && document.querySelector('#lw-chart-container canvas')) {
                return;
            }
            window.currentAsset = asset;
            
            // Visual styles
            const activeStyles = {
                'BTC': 'bg-orange-500/25 text-orange-300 border-orange-500/50 shadow-[0_0_12px_rgba(249,115,22,0.2)]',
                'ETH': 'bg-indigo-500/25 text-indigo-300 border-indigo-500/50 shadow-[0_0_12px_rgba(99,102,241,0.2)]',
                'GOLD': 'bg-yellow-500/25 text-yellow-300 border-yellow-500/50 shadow-[0_0_12px_rgba(234,179,8,0.2)]',
                'NDQ': 'bg-blue-500/25 text-blue-300 border-blue-500/50 shadow-[0_0_12px_rgba(59,130,246,0.2)]',
                'EURUSD': 'bg-emerald-500/25 text-emerald-300 border-emerald-500/50 shadow-[0_0_12px_rgba(16,185,129,0.2)]',
                'GBPUSD': 'bg-emerald-500/25 text-emerald-300 border-emerald-500/50 shadow-[0_0_12px_rgba(16,185,129,0.2)]',
                'USDJPY': 'bg-emerald-500/25 text-emerald-300 border-emerald-500/50 shadow-[0_0_12px_rgba(16,185,129,0.2)]',
                'AUDUSD': 'bg-emerald-500/25 text-emerald-300 border-emerald-500/50 shadow-[0_0_12px_rgba(16,185,129,0.2)]',
                'SOL': 'bg-purple-500/25 text-purple-300 border-purple-500/50 shadow-[0_0_12px_rgba(168,85,247,0.2)]',
                'DOGE': 'bg-orange-500/25 text-orange-300 border-orange-500/50 shadow-[0_0_12px_rgba(249,115,22,0.2)]'
            };
            const inactiveStyle = 'bg-white/5 text-gray-400 border-white/5 hover:bg-white/10 hover:text-gray-200';
            
            ['BTC', 'ETH', 'GOLD', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'NDQ', 'SOL', 'DOGE'].forEach(a => {
                const btn = document.getElementById('btn-asset-' + a.toLowerCase());
                if (!btn) return;
                
                // For main buttons (BTC, ETH, GOLD)
                if (['BTC', 'ETH', 'GOLD'].includes(a)) {
                    btn.className = 'asset-btn flex-1 py-1.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 border cursor-pointer ' + 
                        (a === asset ? activeStyles[a] : inactiveStyle);
                } else {
                    // For dropdown buttons
                    btn.className = 'asset-btn py-2 px-3 rounded-lg text-[11px] font-bold transition-all flex items-center gap-2 border cursor-pointer text-left w-full ' + 
                        (a === asset ? activeStyles[a] : 'bg-transparent text-gray-400 border-transparent hover:bg-white/10 hover:text-gray-200');
                }
            });
            
            // Reset transient HUD values for the new asset without blanking the chart canvas
            window.lastCandle = null;

            // Update dropdown button
            const moreBtn = document.getElementById('btn-asset-more');
            const moreText = document.getElementById('btn-asset-more-text');
            if (moreBtn && moreText) {
                if (!['BTC', 'ETH', 'GOLD'].includes(asset)) {
                    moreBtn.className = 'py-1 px-2 rounded-md text-[11px] font-bold transition-all flex items-center justify-center gap-1 border cursor-pointer shadow-sm w-auto px-3 ' + activeStyles[asset];
                    const iconMap = {'NDQ':'📈', 'EURUSD':'💵', 'GBPUSD':'💷', 'USDJPY':'💴', 'AUDUSD':'🇦🇺', 'SOL':'🚀', 'DOGE':'🐕'};
                    moreText.innerHTML = (iconMap[asset] || '') + ' ' + asset + ' ▼';
                } else {
                    moreBtn.className = 'py-1 px-2 rounded-md text-[11px] font-bold transition-all flex items-center justify-center gap-1 border cursor-pointer bg-white/5 text-gray-400 border-white/5 hover:bg-white/10 hover:text-gray-200 shadow-sm w-12';
                    moreText.innerHTML = '▼';
                }
            }

            window.currentKalshiTarget = null;
            lastBidTs = 0;
            bidsQueue = [];
            const bidsBox = document.getElementById('live-bids-container');
            if (bidsBox) bidsBox.innerHTML = '';
            
            const strikeEl = document.getElementById('exec-strike');
            if (strikeEl) strikeEl.textContent = '$--,---';
            const spotEl = document.getElementById('exec-spot');
            if (spotEl) {
                const knownPrice = window.assetSpotPrices ? window.assetSpotPrices[asset] : null;
                if (knownPrice && isFinite(knownPrice) && knownPrice > 0) {
                    spotEl.textContent = '$' + Number(knownPrice).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                } else {
                    spotEl.textContent = '$--,---';
                }
            }
            const yesBid = document.getElementById('kalshi-yes');
            if (yesBid) yesBid.textContent = '--%';
            const noBid  = document.getElementById('kalshi-no');
            if (noBid) noBid.textContent = '--%';
            const cdEl = document.getElementById('exec-countdown');
            if (cdEl) cdEl.textContent = '--:--';
            
            // Show loader spinner
            showChartLoader();
            
            // Fetch fresh chart, Kalshi contract, and live bids in parallel
            try {
                await Promise.allSettled([
                    fetchChartData(true),
                    fetchKalshiData(true),
                    fetchLiveBids()
                ]);
            } finally {
                hideChartLoader();
            }
        }

        async function fetchChartData(isSwitch = false) {
            if (document.hidden || !window.isTabActive) return;
            const thisReqId = ++currentChartRequestId;
            const reqAsset = (window.currentAsset || 'BTC').toUpperCase();
            const curA = reqAsset.toLowerCase();
            const tf = window.currentChartTimeframe || '15m';

            try {
                const res = await fetch(`${window.API_BASE_URL || ''}/api/engine/${curA}/chart?timeframe=${tf}&limit=200`);
                if (!res.ok) return;

                // Drop response if user switched asset while request was in-flight
                if (reqAsset !== (window.currentAsset || 'BTC').toUpperCase()) {
                    return;
                }

                const d = await res.json();
                const rawCandles = d.candles || [];
                const cleanCandles = sanitizeCandles(rawCandles);
                if (!cleanCandles.length) {
                    return;
                }

                if (!lwChart || !candleSeries || !lineSeries) {
                    await initChart();
                }

                // Apply asset-specific spot price safely to latest candle if close matches asset scale
                const spot = window.assetSpotPrices ? window.assetSpotPrices[reqAsset] : null;
                if (spot && isFinite(spot) && spot > 0) {
                    const last = cleanCandles[cleanCandles.length - 1];
                    if (last && Math.abs(spot - last.close) / last.close < 0.5) {
                        last.close = spot;
                        if (spot > last.high) last.high = spot;
                        if (spot < last.low) last.low = spot;
                    }
                }

                try {
                    const isLine = window.currentChartType === 'line';
                    if (isLine && lineSeries) {
                        const lineData = cleanCandles.map(c => ({ time: c.time, value: c.close }));
                        lineSeries.setData(lineData);
                        if (candleSeries) candleSeries.applyOptions({ visible: false });
                        lineSeries.applyOptions({ visible: true });
                    } else if (candleSeries) {
                        candleSeries.setData(cleanCandles);
                        if (lineSeries) lineSeries.applyOptions({ visible: false });
                        candleSeries.applyOptions({ visible: true });
                    }
                    if (d.volume?.length && volumeSeries) {
                        const cleanVol = sanitizeVolume(d.volume);
                        if (cleanVol.length) volumeSeries.setData(cleanVol);
                    }
                    window.lastCandle = cleanCandles[cleanCandles.length - 1];

                    // Fit content on asset switch, timeframe change, or initial load
                    if (isSwitch || !window._chartHasFitted) {
                        window._chartHasFitted = true;
                        if (lwChart && lwChart.timeScale) {
                            lwChart.timeScale().fitContent();
                        }
                    }
                } catch (seriesErr) {
                    console.error('[Chart] setData failed, rebuilding chart:', seriesErr);
                    await rebuildChart();
                }
            } catch(e) {
                console.warn('[Chart] fetch err', e);
            } finally {
                hideChartLoader();
            }
        }

        let bidsQueue = [];
        let isProcessingBids = false;

        async function processBidsQueue() {
            if (isProcessingBids || bidsQueue.length === 0) return;
            isProcessingBids = true;

            const box = document.getElementById('live-bids-container');
            if (!box) {
                isProcessingBids = false;
                return;
            }

            const t = bidsQueue.shift();
            const isYes = (t.side||'').toUpperCase() === 'YES';
            let dollars = 0;
            if (t.dollars !== undefined && t.dollars > 0) dollars = Math.round(t.dollars);
            else dollars = Math.round((t.count || 0) * (t.price || 0) * 100);
            
            if (dollars >= 1) {
                const el = document.createElement('div');
                el.style.cssText = 'opacity:0; transform:translateY(12px); transition:opacity 0.4s ease-out, transform 0.4s cubic-bezier(0.2, 0.8, 0.2, 1);';
                el.className = 'text-[11px] font-mono font-bold tracking-wide ' + (isYes ? 'text-emerald-400' : 'text-red-400');
                el.innerHTML = '$' + dollars;
                
                box.insertBefore(el, box.firstChild);
                
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => {
                        el.style.opacity = '1';
                        el.style.transform = 'translateY(0)';
                    });
                });
                
                while (box.children.length > 14) box.removeChild(box.lastChild);
            }

            setTimeout(() => {
                isProcessingBids = false;
                if (bidsQueue.length > 0) processBidsQueue();
            }, 300);
        }

        let liveBidsIntervalMs = 800;
        const BASE_LIVE_BIDS_INTERVAL_MS = 800;
        const MAX_LIVE_BIDS_BACKOFF_MS = 30000;
        let liveBidsTimerId = null;

        function scheduleNextLiveBids(delayMs = liveBidsIntervalMs) {
            if (liveBidsTimerId) clearTimeout(liveBidsTimerId);
            liveBidsTimerId = setTimeout(fetchLiveBids, delayMs);
        }
        window.scheduleNextLiveBids = scheduleNextLiveBids;

        async function fetchLiveBids() {
            if (document.hidden || !window.isTabActive) {
                scheduleNextLiveBids(liveBidsIntervalMs);
                return;
            }
            try {
                const curA = (window.currentAsset || 'BTC').toLowerCase();
                const res = await fetch((window.API_BASE_URL||'')+'/api/engine/' + curA + '/kalshi/trades?since=' + lastBidTs);
                
                if (res.status === 429) {
                    // Exponential backoff on HTTP 429: double interval up to 30,000ms (30s)
                    liveBidsIntervalMs = Math.min(MAX_LIVE_BIDS_BACKOFF_MS, Math.max(BASE_LIVE_BIDS_INTERVAL_MS, liveBidsIntervalMs * 2));
                    console.warn(`[LiveBids] HTTP 429 rate limit received. Backing off polling interval to ${liveBidsIntervalMs}ms`);
                    return;
                }

                if (!res.ok) return;

                // Reset back to base interval upon successful response
                liveBidsIntervalMs = BASE_LIVE_BIDS_INTERVAL_MS;

                const d = await res.json();
                
                const newTrades = d.trades || [];
                if (newTrades.length > 0) {
                    newTrades.forEach(t => {
                        lastBidTs = Math.max(lastBidTs, t.ts || 0);
                        bidsQueue.push(t);
                    });
                    
                    if (bidsQueue.length > 50) bidsQueue = bidsQueue.slice(bidsQueue.length - 50);
                    if (!isProcessingBids) processBidsQueue();
                }
            } catch(_) {}
            finally {
                scheduleNextLiveBids(liveBidsIntervalMs);
            }
        }

        function hideChartLoader() {
            const el = document.getElementById('chart-loader');
            if (el) {
                el.style.opacity = '0';
                el.style.display = 'none';
                el.classList.add('pointer-events-none');
            }
        }

        setTimeout(hideChartLoader, 2000);
        setTimeout(hideChartLoader, 4000);

        window.closeTrade = async function(tradeId, action = 'MANUAL_CLOSE') {
            try {
                const res = await fetch((window.API_BASE_URL||'')+'/api/auth/trade/close/' + tradeId + (action ? '?action=' + encodeURIComponent(action) : ''), {
                    method:"POST", 
                    headers:{
                        'Authorization':'Bearer '+token,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ action: action })
                });
                let d = {}; try { d = await res.json(); } catch(e){} 
                if(d.success) { 
                    soundEngine.play('order_fill');
                    showToast('Position closed successfully', 'success'); 
                    loadDashboard();
                    if (typeof closeTradeDetailsModal === 'function') closeTradeDetailsModal();
                } else { 
                    showToast('Failed to close: ' + (d.detail || d.error || 'Unknown error'), 'error'); 
                }
            } catch(e) { 
                showToast('Error: ' + e.message, 'error'); 
            }
        };

        window.takeProfitTrade = async function(tradeId) {
            try {
                const res = await fetch((window.API_BASE_URL||'')+'/api/auth/trade/close/' + tradeId + '?action=TAKE_PROFIT', {
                    method:"POST", 
                    headers:{
                        'Authorization':'Bearer '+token,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ action: 'TAKE_PROFIT' })
                });
                let d = {}; try { d = await res.json(); } catch(e){} 
                if(d.success) { 
                    soundEngine.play('order_fill');
                    if (d.reentry_triggered) {
                        const rIdx = d.reentry_trade?.reentry_index || 2;
                        showToast(`⚡ Profit secured! Tactical Re-Entry #${rIdx} executed.`, 'success', 4000);
                    } else {
                        showToast('⚡ Profit secured! Bot re-entry enabled.', 'success', 3000);
                    }
                    loadDashboard();
                    if (typeof closeTradeDetailsModal === 'function') closeTradeDetailsModal();
                } else { 
                    showToast('Failed to take profit: ' + (d.detail || d.error || 'Unknown error'), 'error'); 
                }
            } catch(e) { 
                showToast('Error: ' + e.message, 'error'); 
            }
        };

                // ── Detailed Trade Breakdown Modal Functions ──
        window.openTradeDetailsModal = function(tradeIdOrObj) {
            const modal = document.getElementById('tradeDetailsModal');
            if (!modal) return;

            let t = null;
            if (typeof tradeIdOrObj === 'object' && tradeIdOrObj !== null) {
                t = tradeIdOrObj;
            } else if (window.tradesById && window.tradesById[tradeIdOrObj]) {
                t = window.tradesById[tradeIdOrObj];
            } else if (window.lastDashboardStats && window.lastDashboardStats.recent_trades) {
                t = window.lastDashboardStats.recent_trades.find(x => String(x.id) === String(tradeIdOrObj));
            }

            if (!t) {
                console.warn("[TradeModal] Trade not found for identifier:", tradeIdOrObj);
                return;
            }

            // Side & Direction
            const side = String(t.side || t.direction || "YES").toUpperCase();
            const isYes = side === "YES";
            const sideBadge = document.getElementById('tdm-side-badge');
            if (sideBadge) {
                sideBadge.textContent = isYes ? "BID YES" : "BID NO";
                sideBadge.className = isYes
                    ? "px-2.5 py-1 rounded-lg text-xs font-black uppercase tracking-wider bg-emerald-500/20 text-emerald-400 border border-emerald-500/35"
                    : "px-2.5 py-1 rounded-lg text-xs font-black uppercase tracking-wider bg-rose-500/20 text-rose-400 border border-rose-500/35";
            }

            // Ticker & Strike
            const ticker = t.ticker || "KXBTC15M";
            let rawStrike = t.strike || t.strike_price || t.target_price || t.target;
            if (!rawStrike && t.market_snapshot) {
                try {
                    const ms = typeof t.market_snapshot === 'string' ? JSON.parse(t.market_snapshot) : t.market_snapshot;
                    rawStrike = ms.target || ms.strike || ms.strike_price;
                } catch(e) {}
            }
            let sNum = Number(rawStrike);
            let strikeVal = (!isNaN(sNum) && isFinite(sNum) && sNum > 0)
                ? sNum.toLocaleString(undefined, { maximumFractionDigits: 2 })
                : null;

            const isSport = window.__isSportTrade ? window.__isSportTrade(t) : false;
            const sInfo = isSport && window.__getSportInfo ? window.__getSportInfo(t) : null;

            const assetType = isSport && sInfo ? sInfo.sport : String(t.asset || (['BTC','ETH','GOLD','EURUSD','GBPUSD','USDJPY','AUDUSD','NDQ','SOL','DOGE'].find(x => ticker.includes(x)) || 'BTC')).toUpperCase();
            const tickerEl = document.getElementById('tdm-ticker');
            if (tickerEl) tickerEl.textContent = isSport && sInfo ? `${sInfo.icon} ${sInfo.sport} · ${ticker}` : `${assetType} · ${ticker}`;
            const strikeTitleEl = document.getElementById('tdm-strike-title');
            if (strikeTitleEl) {
                if (isSport && sInfo) {
                    const linePart = (sInfo.line && sInfo.line !== 'Moneyline') ? ` • ${sInfo.line}` : '';
                    const propPart = sInfo.propType ? `[${sInfo.propType}] ` : '';
                    strikeTitleEl.textContent = `${propPart}${sInfo.team}${linePart}`;
                } else {
                    strikeTitleEl.textContent = (strikeVal ? `Target Strike $${strikeVal}` : 'Target Strike ---');
                }
            }
            const footerTicker = document.getElementById('tdm-footer-ticker');
            if (footerTicker) footerTicker.textContent = ticker;

            // Mode
            const mode = String(t.mode || "PAPER").toUpperCase();
            const modeBadge = document.getElementById('tdm-mode-badge');
            if (modeBadge) {
                modeBadge.textContent = mode;
                modeBadge.className = mode === "LIVE"
                    ? "text-[8px] font-black px-1.5 py-0.5 rounded uppercase bg-rose-500/20 text-rose-300 border border-rose-500/35"
                    : "text-[8px] font-black px-1.5 py-0.5 rounded uppercase bg-cyan-500/20 text-cyan-300 border border-cyan-500/35";
            }

            // Status & PnL
            const pnlVal = parseFloat(t.pnl_dollars !== undefined ? t.pnl_dollars : (t.pnl || 0));
            const isWin = (t.status || "").toUpperCase().includes("WIN") || pnlVal > 0;
            const isLoss = (t.status || "").toUpperCase().includes("LOSS") || pnlVal < 0;
            const isOpen = t.status === "OPEN";

            const statusBadge = document.getElementById('tdm-status-badge');
            if (statusBadge) {
                if (isOpen) {
                    statusBadge.textContent = "OPEN POSITION";
                    statusBadge.className = "px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-yellow-500/20 text-yellow-300 border border-yellow-500/35 animate-pulse";
                } else if (isWin) {
                    statusBadge.textContent = "WIN";
                    statusBadge.className = "px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-emerald-500/20 text-emerald-400 border border-emerald-500/35";
                } else if (isLoss) {
                    statusBadge.textContent = "LOSS";
                    statusBadge.className = "px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-rose-500/20 text-rose-400 border border-rose-500/35";
                } else {
                    statusBadge.textContent = "CLOSED";
                    statusBadge.className = "px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-gray-600/20 text-gray-400 border border-gray-600/35";
                }
            }

            // Financial Metrics
            const count = parseInt(t.count || t.size || 1) || 1;
            const entryPriceNum = parseFloat(t.entry_price || 0.50);
            const exitPriceNum = (t.exit_price !== undefined && t.exit_price !== null) ? parseFloat(t.exit_price) : null;
            const totalCost = count * entryPriceNum;

            const entryPriceEl = document.getElementById('tdm-entry-price');
            if (entryPriceEl) entryPriceEl.textContent = `${Math.round(entryPriceNum * 100)}¢ ($${entryPriceNum.toFixed(2)})`;

            const exitPriceEl = document.getElementById('tdm-exit-price');
            if (exitPriceEl) {
                if (exitPriceNum !== null) {
                    exitPriceEl.textContent = `${Math.round(exitPriceNum * 100)}¢ ($${exitPriceNum.toFixed(2)})`;
                } else {
                    exitPriceEl.textContent = isOpen ? 'Active Mark' : 'Settled';
                }
            }

            const contractsEl = document.getElementById('tdm-contracts');
            if (contractsEl) contractsEl.textContent = `${count} ${count === 1 ? 'Contract' : 'Contracts'}`;

            const totalCostEl = document.getElementById('tdm-total-cost');
            if (totalCostEl) totalCostEl.textContent = `$${totalCost.toFixed(2)}`;

            // Hero Outcome Card
            const heroCard = document.getElementById('tdm-hero-card');
            if (heroCard) {
                if (isOpen) {
                    heroCard.className = "relative overflow-hidden rounded-2xl p-4 sm:p-5 border border-yellow-500/30 bg-gradient-to-br from-yellow-950/20 via-[#0d1424] to-black flex flex-col sm:flex-row justify-between sm:items-center gap-3";
                    heroCard.innerHTML = `
                        <div class="flex items-center gap-3.5">
                            <div class="w-12 h-12 rounded-2xl bg-yellow-500/20 border border-yellow-500/40 flex items-center justify-center text-yellow-400 text-xl font-black animate-pulse">
                                ●
                            </div>
                            <div>
                                <div class="text-[10px] font-bold text-yellow-400 uppercase tracking-widest">Active Position Live</div>
                                <div class="text-2xl font-black text-white tabular-nums">${pnlVal >= 0 ? '+$' + pnlVal.toFixed(2) : '-$' + Math.abs(pnlVal).toFixed(2)}</div>
                                <div class="text-[10px] text-gray-400 font-mono">Unrealized PnL (Mark-to-Market)</div>
                            
                                <button onclick="closeTrade('${t.id}', 'MANUAL_CLOSE'); closeTradeDetailsModal();" class="mt-2 sm:mt-2.5 px-3 py-1.5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 rounded-xl text-[10px] font-bold uppercase tracking-wider flex items-center justify-center gap-1.5 transition-all active:scale-95 cursor-pointer"><span>✕</span> Cancel / Close Trade</button></div>
                        </div>
                        <div class="sm:text-right bg-black/40 p-2.5 rounded-xl border border-white/5">
                            <span class="text-[9px] font-bold uppercase tracking-wider text-gray-400 block mb-0.5">Direction Target</span>
                            <span class="text-xs font-black ${isYes ? 'text-emerald-400' : 'text-rose-400'}">${isSport && sInfo ? (sInfo.strikeDetails ? `${side} · ${sInfo.strikeDetails}` : `${side} (${sInfo.team}${sInfo.line ? ' ' + sInfo.line : ''})`) : (isYes ? (strikeVal ? 'YES (Above $' + strikeVal + ')' : 'YES (Above Target)') : (strikeVal ? 'NO (Below $' + strikeVal + ')' : 'NO (Below Target)'))}</span>
                        </div>
                    `;
                } else if (isWin) {
                    const roiPct = totalCost > 0 ? (pnlVal / totalCost) * 100 : 0;
                    heroCard.className = "relative overflow-hidden rounded-2xl p-4 sm:p-5 border border-emerald-500/30 bg-gradient-to-br from-emerald-950/30 via-[#0d1424] to-black flex flex-col sm:flex-row justify-between sm:items-center gap-3";
                    heroCard.innerHTML = `
                        <div class="flex items-center gap-3.5">
                            <div class="w-12 h-12 rounded-2xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 text-xl font-black shadow-[0_0_15px_rgba(16,185,129,0.2)]">
                                ✓
                            </div>
                            <div>
                                <div class="text-[10px] font-bold text-emerald-400 uppercase tracking-widest">Winning Trade Settled</div>
                                <div class="text-2xl font-black text-emerald-400 tabular-nums">+$${pnlVal.toFixed(2)}</div>
                                <div class="text-[10px] text-emerald-300/80 font-mono font-bold">+${roiPct.toFixed(1)}% Return on Capital Risked</div>
                            </div>
                        </div>
                        <div class="sm:text-right bg-black/40 p-2.5 rounded-xl border border-white/5">
                            <span class="text-[9px] font-bold uppercase tracking-wider text-gray-400 block mb-0.5">Outcome Result</span>
                            <span class="text-xs font-black text-emerald-400">${isSport && sInfo ? (sInfo.strikeDetails ? `Target Met: ${sInfo.strikeDetails}` : `Target Met (${sInfo.team} Won)`) : `Target Met (${isYes ? 'Closed Above' : 'Closed Below'} Strike)`}</span>
                        </div>
                    `;
                } else if (isLoss) {
                    heroCard.className = "relative overflow-hidden rounded-2xl p-4 sm:p-5 border border-rose-500/30 bg-gradient-to-br from-rose-950/30 via-[#0d1424] to-black flex flex-col sm:flex-row justify-between sm:items-center gap-3";
                    heroCard.innerHTML = `
                        <div class="flex items-center gap-3.5">
                            <div class="w-12 h-12 rounded-2xl bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-400 text-xl font-black shadow-[0_0_15px_rgba(244,63,94,0.2)]">
                                ✕
                            </div>
                            <div>
                                <div class="text-[10px] font-bold text-rose-400 uppercase tracking-widest">Loss Incurred</div>
                                <div class="text-2xl font-black text-rose-400 tabular-nums">-$${Math.abs(pnlVal).toFixed(2)}</div>
                                <div class="text-[10px] text-rose-300/80 font-mono font-bold">-100% Capital Risked ($${totalCost.toFixed(2)})</div>
                            </div>
                        </div>
                        <div class="sm:text-right bg-black/40 p-2.5 rounded-xl border border-white/5">
                            <span class="text-[9px] font-bold uppercase tracking-wider text-gray-400 block mb-0.5">Exit Outcome</span>
                            <span class="text-xs font-black text-rose-400">${t.exit_reason ? t.exit_reason.replace(/_/g, ' ') : 'Expired Out-of-the-Money'}</span>
                        </div>
                    `;
                } else {
                    heroCard.className = "relative overflow-hidden rounded-2xl p-4 sm:p-5 border border-white/10 bg-[#0e1424] flex flex-col sm:flex-row justify-between sm:items-center gap-3";
                    heroCard.innerHTML = `
                        <div class="flex items-center gap-3.5">
                            <div class="w-12 h-12 rounded-2xl bg-gray-700/20 border border-gray-600/40 flex items-center justify-center text-gray-400 text-xl font-black">
                                ■
                            </div>
                            <div>
                                <div class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Trade Closed</div>
                                <div class="text-2xl font-black text-white tabular-nums">$0.00</div>
                                <div class="text-[10px] text-gray-400 font-mono">Break-Even / Neutral Settlement</div>
                            </div>
                        </div>
                    `;
                }
            }

            // Strategy Descriptions
            const styleDescriptions = {
                'SNIPER': 'Disciplined sniper confluence targeting high-conviction order flow, structural bounces, and volume exhaustion.',
                'MOMENTUM_SURFER': 'High-momentum trend following utilizing CVD acceleration and aggressive breakout velocity.',
                'AMBUSH': 'Mean-reversion sniping at overextended Bollinger Band extremes and liquidity sweeps.',
                'PREDICTION': 'Machine-learning directional forecasting waiting 1 minute 30 seconds post-open for price confirmation.',
                'CHOP': 'Range-bound mean-reversion trading within low ADX consolidation zones.',
                'CAPITAL_GUARD': 'Defensive capital preservation strategy requiring 4+ confluence gates before entry.',
                'AUTO': 'Dynamic AI regime detection automatically selecting the highest EV strategy for current market conditions.',
                'AUTO 2.0': 'Next-gen regime detector dynamically routing between momentum and mean-reversion.',
                'MANUAL': 'Discretionary trade executed directly by trader.'
            };

            const isManual = t.is_manual === true || String(t.trading_style || '').toUpperCase() === 'MANUAL';
            const rawStyle = String(t.trading_style || (isManual ? 'MANUAL' : 'AUTO')).toUpperCase().replace(/_/g, ' ');
            const strategyNameEl = document.getElementById('tdm-strategy-name');
            if (strategyNameEl) {
                strategyNameEl.textContent = isManual ? '👤 MANUAL' : (rawStyle.includes('SNIPER') ? '🎯 SNIPER' : rawStyle.includes('MOMENTUM') ? '🏄 MOMENTUM SURFER' : rawStyle.includes('PREDICTION') ? '🔮 PREDICTION' : rawStyle.includes('AMBUSH') ? '🥷 AMBUSH' : rawStyle.includes('CHOP') ? '🪓 CHOP' : '🤖 ' + rawStyle);
            }

            const strategyDescEl = document.getElementById('tdm-strategy-desc');
            if (strategyDescEl) {
                const matchedKey = Object.keys(styleDescriptions).find(k => rawStyle.includes(k)) || 'AUTO';
                strategyDescEl.textContent = styleDescriptions[matchedKey];
            }

            // Signal Source
            const signalSource = isManual ? 'MANUAL' : String(t.signal_source || 'BLEND').toUpperCase();
            const signalSourceEl = document.getElementById('tdm-signal-source');
            if (signalSourceEl) {
                signalSourceEl.textContent = signalSource === 'AUTO' ? '🤖 AUTO' : signalSource === 'BLEND' ? '⚖️ BLEND' : signalSource === 'AI_ONLY' ? '🧠 AI ONLY' : signalSource === 'CHART_ONLY' ? '📊 CHART ONLY' : signalSource;
            }

            const sourceDescEl = document.getElementById('tdm-source-desc');
            if (sourceDescEl) {
                if (isManual) sourceDescEl.textContent = 'Manual order placed directly via dashboard controls.';
                else if (signalSource.includes('AI_ONLY')) sourceDescEl.textContent = 'Pure machine learning inference isolated from traditional charting indicators.';
                else if (signalSource.includes('CHART')) sourceDescEl.textContent = 'Pure price action, EMA ribbon alignment, and RSI/CVD momentum indicators.';
                else sourceDescEl.textContent = 'Weighted confluence of trained AI neural predictions and 15m technical indicators.';
            }

            // Model Pill
            const modelPill = document.getElementById('tdm-model-pill');
            if (modelPill) {
                const modelStr = t.model_choice ? String(t.model_choice) : (isManual ? 'Manual' : 'Dual-Engine ML');
                modelPill.textContent = `${modelStr} Engine`;
            }

            // Conviction / Confidence
            const confVal = t.confidence != null ? parseFloat(t.confidence) : (t.probability_percent != null ? parseFloat(t.probability_percent) : 55.0);
            const confValEl = document.getElementById('tdm-confidence-val');
            if (confValEl) confValEl.textContent = `${confVal.toFixed(1)}% Directional Conviction`;

            const confBarEl = document.getElementById('tdm-confidence-bar');
            if (confBarEl) {
                confBarEl.style.width = `${Math.min(100, Math.max(10, confVal))}%`;
                confBarEl.className = isYes
                    ? "h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-all duration-500"
                    : "h-full rounded-full bg-gradient-to-r from-rose-500 to-amber-500 transition-all duration-500";
            }

            // AI Catalysts List
            const catalystsContainer = document.getElementById('tdm-catalysts-container');
            const catalystCountEl = document.getElementById('tdm-catalyst-count');
            const catalysts = Array.isArray(t.catalysts) ? t.catalysts : [];
            
            if (catalystCountEl) catalystCountEl.textContent = `${catalysts.length} Signal${catalysts.length === 1 ? '' : 's'}`;

            if (catalystsContainer) {
                if (catalysts.length === 0) {
                    catalystsContainer.innerHTML = `
                        <div class="p-3 rounded-xl bg-[#0e1422] border border-white/5 text-gray-400 text-xs flex items-center gap-2">
                            <span class="text-base">💡</span>
                            <span>${isManual ? 'Manual trade: executed directly by trader.' : 'Executed via baseline confluence thresholds and standard risk management rules.'}</span>
                        </div>
                    `;
                } else {
                    let catHtml = '';
                    catalysts.forEach((cStr, idx) => {
                        let badge = 'SIGNAL';
                        let badgeClass = 'bg-blue-500/20 text-blue-300 border-blue-500/35';
                        let icon = '⚡';

                        if (cStr.includes('ML Confirmation') || cStr.includes('ML Engine') || cStr.includes('AI Model') || cStr.includes('Model')) {
                            badge = 'ML ENGINE';
                            badgeClass = 'bg-purple-500/20 text-purple-300 border-purple-500/35';
                            icon = '🧠';
                        } else if (cStr.includes('Head & Shoulders') || cStr.includes('Top') || cStr.includes('Bottom') || cStr.includes('Ribbon') || cStr.includes('Crossover')) {
                            badge = 'TECHNICAL';
                            badgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/35';
                            icon = '📉';
                        } else if (cStr.includes('Neckline') || cStr.includes('Distribution') || cStr.includes('Orderbook') || cStr.includes('Liquidity')) {
                            badge = 'FLOW';
                            badgeClass = 'bg-amber-500/20 text-amber-300 border-amber-500/35';
                            icon = '🌊';
                        } else if (cStr.includes('Pattern') || cStr.includes('Streak') || cStr.includes('samples')) {
                            badge = 'STATISTICAL';
                            badgeClass = 'bg-cyan-500/20 text-cyan-300 border-cyan-500/35';
                            icon = '📊';
                        }

                        const cleanText = cStr.replace(/^[^\w\s\$\%\-\(\)]+/g, '').trim();

                        catHtml += `
                            <div class="p-3 rounded-xl bg-[#0e1422] border border-white/5 flex flex-col gap-1">
                                <div class="flex items-center justify-between">
                                    <span class="text-[9px] font-bold px-2 py-0.5 rounded-full border uppercase ${badgeClass} flex items-center gap-1">
                                        <span>${icon}</span> ${badge}
                                    </span>
                                    <span class="text-[9px] text-gray-500 font-mono">#${idx + 1}</span>
                                </div>
                                <p class="text-xs text-gray-200 leading-snug mt-1 font-sans">
                                    ${cleanText || cStr}
                                </p>
                            </div>
                        `;
                    });
                    catalystsContainer.innerHTML = catHtml;
                }
            }

            // Plain English AI Executive Summary
            const summaryEl = document.getElementById('tdm-ai-summary');
            if (summaryEl) {
                const strikeText = (strikeVal && strikeVal !== '---') ? '$' + strikeVal : 'target';
                if (isSport && sInfo) {
                    const lineNote = (sInfo.line && sInfo.line !== 'Moneyline') ? ` [${sInfo.line}]` : '';
                    const strikeNote = sInfo.strikeDetails ? ` — <em>${sInfo.strikeDetails}</em>` : '';
                    if (isManual) {
                        summaryEl.innerHTML = `You manually executed <strong>${count} ${side} contracts</strong> at <strong>${Math.round(entryPriceNum * 100)}¢</strong> ($${totalCost.toFixed(2)} capital risked), betting on <strong>${sInfo.team}</strong> in <strong>${sInfo.sport}</strong>${lineNote}${strikeNote}.`;
                    } else {
                        let outcomePart = '';
                        if (isOpen) {
                            outcomePart = `Position is currently <strong>active</strong> and monitoring live game / market state.`;
                        } else if (isWin) {
                            outcomePart = `The prediction was <strong>correct</strong>: <strong>${sInfo.team}</strong> delivered the win, returning <strong>+$${pnlVal.toFixed(2)}</strong>.`;
                        } else if (isLoss) {
                            outcomePart = `The match resulted in an opposing outcome, resulting in an exit at ${t.exit_price ? Math.round(parseFloat(t.exit_price) * 100) + '¢' : 'settlement'}.`;
                        } else {
                            outcomePart = `The position settled flat.`;
                        }
                        summaryEl.innerHTML = `The AI system executed <strong>${count} ${side} contracts</strong> at <strong>${Math.round(entryPriceNum * 100)}¢</strong> ($${totalCost.toFixed(2)} total cost) for <strong>${sInfo.team}</strong> in <strong>${sInfo.sport}</strong>${lineNote}${strikeNote} with <strong>${confVal.toFixed(1)}% directional conviction</strong>. ${outcomePart}`;
                    }
                } else if (isManual) {
                    summaryEl.innerHTML = `You manually executed <strong>${count} ${side} contracts</strong> at <strong>${Math.round(entryPriceNum * 100)}¢</strong> ($${totalCost.toFixed(2)} capital risked), betting that Bitcoin would settle ${isYes ? 'above' : 'below'} the ${strikeText} strike.`;
                } else {
                    let outcomePart = '';
                    if (isOpen) {
                        outcomePart = `Position is currently <strong>active</strong> and monitoring live 15m order flow.`;
                    } else if (isWin) {
                        outcomePart = `The thesis was <strong>correct</strong>: the market settled ${isYes ? 'above' : 'below'} ${strikeText}, delivering a <strong>+$${pnlVal.toFixed(2)}</strong> profit.`;
                    } else if (isLoss) {
                        outcomePart = `The market moved against the position, resulting in an exit at ${t.exit_price ? Math.round(parseFloat(t.exit_price) * 100) + '¢' : 'settlement'}.`;
                    } else {
                        outcomePart = `The position settled flat.`;
                    }

                    summaryEl.innerHTML = `
                        The AI system executed <strong>${count} ${side} contracts</strong> at <strong>${Math.round(entryPriceNum * 100)}¢</strong> ($${totalCost.toFixed(2)} total cost) using the <strong>${rawStyle}</strong> strategy. 
                        Algorithms detected <strong>${confVal.toFixed(1)}% directional conviction</strong> that BTC would finish ${isYes ? 'above' : 'below'} the ${strikeText} strike based on ${catalysts.length > 0 ? catalysts.length + ' confluence triggers including ' + (catalysts[0].substring(0, 45) + '...') : 'trend alignment and orderbook imbalances'}. ${outcomePart}
                    `;
                }
            }

            // Timestamps & Duration
            const entryTs = t.timestamp || t.time || '';
            let entryDateStr = '--';
            let entryDateObj = null;
            try {
                if (entryTs) {
                    entryDateObj = new Date(entryTs);
                    entryDateStr = entryDateObj.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
                }
            } catch(e) {}

            let exitDateStr = '--';
            let exitDateObj = null;
            try {
                if (t.settled_at) {
                    exitDateObj = new Date(t.settled_at * 1000);
                    exitDateStr = exitDateObj.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
                } else if (isOpen) {
                    exitDateStr = 'In Progress (Active)';
                } else {
                    exitDateStr = 'Settled';
                }
            } catch(e) {}

            let durationStr = '--';
            if (entryDateObj && exitDateObj) {
                const diffMs = Math.max(0, exitDateObj - entryDateObj);
                const mins = Math.floor(diffMs / 60000);
                const secs = Math.floor((diffMs % 60000) / 1000);
                durationStr = `${mins}m ${secs}s`;
            } else if (entryDateObj && isOpen) {
                const diffMs = Math.max(0, new Date() - entryDateObj);
                const mins = Math.floor(diffMs / 60000);
                const secs = Math.floor((diffMs % 60000) / 1000);
                durationStr = `${mins}m ${secs}s (elapsed)`;
            }

            const entryTimeEl = document.getElementById('tdm-entry-time');
            if (entryTimeEl) entryTimeEl.textContent = entryDateStr;

            const exitTimeEl = document.getElementById('tdm-exit-time');
            if (exitTimeEl) exitTimeEl.textContent = exitDateStr;

            const durationEl = document.getElementById('tdm-duration');
            if (durationEl) durationEl.textContent = durationStr;

            const exitReasonEl = document.getElementById('tdm-exit-reason');
            if (exitReasonEl) {
                const er = String(t.exit_reason || t.reason || (isOpen ? 'In Progress' : 'Settlement')).toUpperCase();
                exitReasonEl.textContent = er.replace(/_/g, ' ');
            }

            // Reveal modal
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            document.body.style.overflow = 'hidden';
        };

        window.closeTradeDetailsModal = function() {
            const modal = document.getElementById('tradeDetailsModal');
            if (modal) {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
                document.body.style.overflow = '';
            }
        };

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeTradeDetailsModal();
                if (typeof dismissUpdateAnnouncement === 'function') dismissUpdateAnnouncement();
            }
        });

        // ── What's New & Upgrades Modal System ──
        let _currentUpdateId = null;
        let _updateCheckDone = false;

        function escapeUpdateHtml(text) {
            if (!text) return '';
            return String(text)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        async function checkUpdateAnnouncement() {
            if (_updateCheckDone) return;
            _updateCheckDone = true;

            try {
                const res = await fetch((window.API_BASE_URL||'')+'/api/auth/updates', {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (!res.ok) return;
                const data = await res.json();
                if (!data.success) return;

                window._updatesData = data;
                const bellBtn = document.getElementById('settings-nav-btn');
                const bellDot = document.getElementById('updates-bell-dot');
                const bellPulse = document.getElementById('updates-bell-dot-pulse');
                const settingsBtnDot = document.getElementById('settings-updates-dot');

                if (bellBtn && (data.show_bell || (data.updates && data.updates.length > 0))) {
                    bellBtn.classList.remove('hidden');
                }

                const unreadList = data.unread || [];
                const latestUpdate = (data.updates && data.updates[0]) || (unreadList.length > 0 ? unreadList[0] : null);

                if (latestUpdate) {
                    _currentUpdateId = latestUpdate.id;
                }

                if (unreadList.length > 0 && latestUpdate) {
                    if (bellDot) bellDot.classList.remove('hidden');
                    if (bellPulse) bellPulse.classList.remove('hidden');
                    if (settingsBtnDot) settingsBtnDot.classList.remove('hidden');

                    const dismissedKey = 'kalshi_dismissed_update_' + latestUpdate.id;
                    if (localStorage.getItem(dismissedKey) !== 'true') {
                        setTimeout(() => {
                            showUpdateModal(latestUpdate);
                        }, 750);
                    }
                } else {
                    if (bellDot) bellDot.classList.add('hidden');
                    if (bellPulse) bellPulse.classList.add('hidden');
                }
            } catch (err) {
                console.warn("[Updates] checkUpdateAnnouncement error:", err);
            }
        }

        function showUpdateModal(updateObj) {
            if (!updateObj) return;
            _currentUpdateId = updateObj.id;

            const modal = document.getElementById('updateAnnouncementModal');
            const card = document.getElementById('updateAnnouncementCard');
            const badgeEl = document.getElementById('update-badge');
            const dateEl = document.getElementById('update-date');
            const titleEl = document.getElementById('update-title');
            const summaryEl = document.getElementById('update-summary');
            const listEl = document.getElementById('update-items-list');

            if (!modal) return;

            if (badgeEl) badgeEl.textContent = updateObj.badge || 'NEW UPGRADES';
            if (dateEl) dateEl.textContent = updateObj.date || '';
            if (titleEl) titleEl.textContent = updateObj.title || 'Platform Updates';
            if (summaryEl) {
                summaryEl.textContent = updateObj.summary || 'Check out the latest features and engine improvements.';
                summaryEl.style.display = updateObj.summary ? 'block' : 'none';
            }

            if (listEl && Array.isArray(updateObj.items)) {
                listEl.innerHTML = updateObj.items.map(item => `
                    <div class="p-3 sm:p-3.5 rounded-xl bg-white/[0.03] hover:bg-white/[0.06] border border-white/5 transition-colors flex items-start gap-3 group">
                        <div class="w-9 h-9 rounded-xl bg-cyan-500/15 border border-cyan-500/25 flex items-center justify-center text-lg shrink-0 shadow-[0_0_12px_rgba(6,182,212,0.15)] group-hover:scale-105 transition-transform">
                            ${item.icon || '⚡'}
                        </div>
                        <div class="flex-1 min-w-0">
                            <h4 class="text-xs font-bold text-white group-hover:text-cyan-300 transition-colors flex items-center gap-1.5">
                                ${escapeUpdateHtml(item.title || '')}
                            </h4>
                            <p class="text-[11px] text-gray-300/90 mt-0.5 leading-relaxed font-normal">
                                ${escapeUpdateHtml(item.text || '')}
                            </p>
                        </div>
                    </div>
                `).join('');
            }

            modal.style.display = '';  // Reset in case dismiss set display:none
            modal.classList.remove('pointer-events-none', 'opacity-0');
            modal.classList.add('opacity-100');
            if (card) {
                card.classList.remove('scale-95');
                card.classList.add('scale-100');
            }
            document.body.style.overflow = 'hidden';
        }

        window.openUpdateModal = function() {
            if (window._updatesData && window._updatesData.updates && window._updatesData.updates.length > 0) {
                showUpdateModal(window._updatesData.updates[0]);
            } else {
                _updateCheckDone = false;
                checkUpdateAnnouncement().then(() => {
                    if (window._updatesData && window._updatesData.updates && window._updatesData.updates.length > 0) {
                        showUpdateModal(window._updatesData.updates[0]);
                    }
                });
            }
        };

        window.dismissUpdateAnnouncement = async function() {
            const modal = document.getElementById('updateAnnouncementModal');
            const card = document.getElementById('updateAnnouncementCard');
            const bellDot = document.getElementById('updates-bell-dot');
            const bellPulse = document.getElementById('updates-bell-dot-pulse');

            if (modal) {
                modal.classList.remove('opacity-100');
                modal.classList.add('opacity-0', 'pointer-events-none');
                // After CSS transition finishes, hide it completely
                setTimeout(() => { modal.style.display = 'none'; }, 350);
            }
            if (card) {
                card.classList.remove('scale-100');
                card.classList.add('scale-95');
            }
            document.body.style.overflow = '';

            if (bellDot) bellDot.classList.add('hidden');
            if (bellPulse) bellPulse.classList.add('hidden');
            const settingsBtnDot = document.getElementById('settings-updates-dot');
            if (settingsBtnDot) settingsBtnDot.classList.add('hidden');

            if (_currentUpdateId) {
                localStorage.setItem('kalshi_dismissed_update_' + _currentUpdateId, 'true');
                try {
                    await fetch((window.API_BASE_URL||'')+'/api/auth/updates/dismiss', {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ id: _currentUpdateId })
                    });
                } catch (e) {
                    console.warn("[Updates] Failed to notify backend of dismissal:", e);
                }
            }
        };

        // ── Native Mobile Pull-to-Refresh System ──
        window.manualDashboardRefresh = async function(btn) {
            const icon = document.getElementById('refresh-nav-icon') || btn?.querySelector('svg');
            if (icon) icon.classList.add('animate-spin');
            
            try {
                if (typeof soundEngine !== 'undefined' && soundEngine.play) soundEngine.play('refresh');
            } catch(e) {}

            try {
                const promises = [];
                if (typeof loadDashboard === 'function') promises.push(loadDashboard());
                if (typeof refreshWalletBalances === 'function') promises.push(refreshWalletBalances());
                if (window.currentUniverse === 'SPORTS') {
                    if (typeof filterSportsEvents === 'function') {
                        promises.push(filterSportsEvents(window.sportsFilter || 'NFL'));
                    }
                }
                await Promise.all(promises);
                if (typeof showToast === 'function') {
                    showToast('Dashboard Refreshed ⚡', 'success', 1500);
                }
            } catch(err) {
                console.warn('Manual refresh error:', err);
            } finally {
                setTimeout(() => {
                    if (icon) icon.classList.remove('animate-spin');
                }, 500);
            }
        };

        // ── Active Position HUD System (Audit Item 4) ──
        let previousOpenTradeCount = 0;
        let lastPlayedCountdownSec = null;

        function updateActivePositionHud(s) {
            const container = document.getElementById('activePositionHud');
            if (!container) return;

            const __isSportTrade = window.__isSportTrade || ((t) => {
                const a = String(t.asset || '').toUpperCase();
                const tk = String(t.ticker || '').toUpperCase();
                let meta = t.metadata;
                if (typeof meta === 'string') {
                    try { meta = JSON.parse(meta); } catch(e) { meta = {}; }
                }
                let ml = t.ml_reasoning;
                if (typeof ml === 'string') {
                    try { ml = JSON.parse(ml); } catch(e) { ml = {}; }
                }
                const hasSportProp = Boolean(t.sport || t.predicted_team || (meta && (meta.sport || meta.league)) || (ml && (ml.sport || ml.predicted_team)));
                const isSportsTicker = /^KX(NFL|MLB|NBA|NHL|NCAAF|NCAAB|WNBA|SOC|UFC|MMA|TEN|NPB|KBO|GAME|ATP)/.test(tk) ||
                                       /^(NFL|MLB|NBA|NHL|NCAAF|NCAAB|WNBA|SOC|UFC|MMA|TEN)-/.test(tk) ||
                                       tk.startsWith('KALSHI-') ||
                                       ['NFL','MLB','NBA','NCAAF','NCAAB','WNBA','NPB','KBO','NPB/KBO','NPB_KBO','NHL','SOC','UFC','TEN','MMA','SPORTS'].includes(a);
                const isSportsStyle = String(t.trading_style || '').toUpperCase() === 'SPORTS_AI';
                return isSportsStyle || hasSportProp || isSportsTicker;
            });
            const __inSports = window.currentUniverse === 'SPORTS';
            const openTrades = (s.recent_trades || [])
                .filter(t => String(t.status || '').toUpperCase() === 'OPEN')
                .filter(t => __inSports ? __isSportTrade(t) : !__isSportTrade(t));
            
            // Audio trigger on newly opened trade
            if (openTrades.length > previousOpenTradeCount && previousOpenTradeCount === 0) {
                soundEngine.play('order_fill');
            }
            previousOpenTradeCount = openTrades.length;

            if (openTrades.length === 0) {
                container.innerHTML = `
                    <div class="bg-[#0e1626]/95 border-t border-cyan-500/20 px-4 py-3 shadow-md flex items-center justify-between">
                        <div class="flex items-center gap-2.5">
                            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                            <span class="text-[10px] font-bold uppercase tracking-wider text-gray-400">Position Scanner:</span>
                            <span class="text-[10px] font-mono text-emerald-400 font-bold">${__inSports ? 'READY · Watching AI Picks' : 'READY · Bot Scanning Active'}</span>
                        </div>
                        <span class="text-[9px] font-mono text-gray-400 uppercase tracking-widest">${__inSports ? 'SPORTS · NFL · MLB · NHL · SOCCER · UFC · TENNIS · NPB/KBO' : (s.trading_style || 'AUTO') + ' · 10 ASSETS (BTC, ETH, GOLD, EURUSD, GBPUSD, USDJPY, AUDUSD, NDQ, SOL, DOGE)'}</span>
                    </div>
                `;
                return;
            }

            // Order: BTC first, then ETH, then GOLD, then others
            const assetOrder = { 'BTC': 1, 'ETH': 2, 'GOLD': 3, 'EURUSD': 4, 'GBPUSD': 5, 'USDJPY': 6, 'AUDUSD': 7, 'NDQ': 8, 'SOL': 9, 'DOGE': 10 };
            const sortedOpen = [...openTrades].sort((a, b) => {
                const aAsset = String(a.asset || (['BTC','ETH','GOLD','EURUSD','GBPUSD','USDJPY','AUDUSD','NDQ','SOL','DOGE'].find(x => String(a.ticker||'').includes(x)) || 'OTHER')).toUpperCase();
                const bAsset = String(b.asset || (['BTC','ETH','GOLD','EURUSD','GBPUSD','USDJPY','AUDUSD','NDQ','SOL','DOGE'].find(x => String(b.ticker||'').includes(x)) || 'OTHER')).toUpperCase();
                return (assetOrder[aAsset] || 99) - (assetOrder[bAsset] || 99);
            });

            let totalOpenPnl = 0;
            let rowsHtml = '';

            sortedOpen.forEach(t => {
                let asset = String(t.asset || '').toUpperCase();
                if (!asset || asset === 'NONE') {
                    const tk = String(t.ticker || '').toUpperCase();
                    if (tk.includes('BTC')) asset = 'BTC';
                    else if (tk.includes('ETH')) asset = 'ETH';
                    else if (tk.includes('GOLD')) asset = 'GOLD';
                    else if (tk.includes('EURUSD')) asset = 'EURUSD';
                    else if (tk.includes('GBPUSD')) asset = 'GBPUSD';
                    else if (tk.includes('USDJPY')) asset = 'USDJPY';
                    else if (tk.includes('AUDUSD')) asset = 'AUDUSD';
                    else if (tk.includes('NDQ')) asset = 'NDQ';
                    else if (tk.includes('SOL')) asset = 'SOL';
                    else if (tk.includes('DOGE')) asset = 'DOGE';
                    else asset = 'BTC';
                }

                const dir = String(t.side || 'YES').toUpperCase();
                const isYes = dir === 'YES';
                const count = t.count || t.size || 1;
                const entryPrice = t.entry_price ? Math.round(t.entry_price * 100) : 50;

                const isSport = window.__isSportTrade ? window.__isSportTrade(t) : false;
                const sportInfo = isSport && window.__getSportInfo ? window.__getSportInfo(t) : null;
                // User requested format: "YES BTC 11 Contracts @ 50c" or "YES Team 11 Contracts @ 50c" for sports
                const tradeLabel = isSport && sportInfo
                    ? `${dir} ${sportInfo.team} · ${count} Contracts @ ${entryPrice}¢`
                    : `${dir} ${asset} ${count} Contracts @ ${entryPrice}¢`;

                // Live PnL
                const estPnl = t.live_pnl !== undefined ? Number(t.live_pnl) : (t.pnl_dollars !== undefined ? Number(t.pnl_dollars) : 0);
                totalOpenPnl += estPnl;
                const pnlColor = estPnl >= 0 ? 'text-emerald-400' : 'text-rose-400';
                const pnlStr = (estPnl >= 0 ? '+$' : '-$') + Math.abs(estPnl).toFixed(2);
                const costBasis = (entryPrice / 100) * count;
                const pnlPct = costBasis > 0 ? ((estPnl / costBasis) * 100).toFixed(1) : '0.0';

                // Strike & distance
                let spot = 0;
                if (asset === 'BTC') spot = window.lastBtcPrice || window.lastSpotPrice || 0;
                else if (asset === 'ETH') spot = window.lastEthPrice || 0;
                else if (asset === 'GOLD') spot = window.lastGoldPrice || 0;
                else spot = window.lastSpotPrice || 0;

                const strikeNum = Number(t.strike || 0);
                const strike = (!isNaN(strikeNum) && isFinite(strikeNum) && strikeNum > 0) ? strikeNum : null;
                let distanceStr = '';
                if (spot && strike) {
                    const diff = spot - strike;
                    const isItm = (isYes && diff > 0) || (!isYes && diff < 0);
                    const absDiff = Math.abs(diff).toFixed(1);
                    distanceStr = isItm 
                        ? `<span class="text-emerald-400 font-bold">+$${absDiff} ITM</span>`
                        : `<span class="text-rose-400 font-bold">-$${absDiff} OTM</span>`;
                }

                let assetBadgeClass = 'bg-slate-500/20 text-slate-300 border-slate-500/40';
                let assetIcon = '';
                if (isSport && sportInfo) {
                    asset = (sportInfo && sportInfo.sport) || 'SPORTS';
                    assetBadgeClass = 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40';
                    assetIcon = (sportInfo.icon || '🏈') + ' ';
                    distanceStr = `<span class="text-cyan-400 font-bold">${sportInfo.team || ''}</span>`;
                } else 
                if (asset === 'BTC') { assetBadgeClass = 'bg-amber-500/20 text-amber-300 border-amber-500/40'; assetIcon = '₿ '; }
                else if (asset === 'ETH') { assetBadgeClass = 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40'; assetIcon = 'Ξ '; }
                else if (asset === 'GOLD') { assetBadgeClass = 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40'; assetIcon = '🪙 '; }
                    else if (asset === 'EURUSD') { assetBadgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'; assetIcon = '💵 '; }
                    else if (asset === 'GBPUSD') { assetBadgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'; assetIcon = '💵 '; }
                    else if (asset === 'USDJPY') { assetBadgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'; assetIcon = '💵 '; }
                    else if (asset === 'AUDUSD') { assetBadgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'; assetIcon = '💵 '; }
                    else if (asset === 'NDQ') { assetBadgeClass = 'bg-blue-500/20 text-blue-300 border-blue-500/40'; assetIcon = '📈 '; }
                    else if (asset === 'SOL') { assetBadgeClass = 'bg-purple-500/20 text-purple-300 border-purple-500/40'; assetIcon = '🚀 '; }
                    else if (asset === 'DOGE') { assetBadgeClass = 'bg-orange-500/20 text-orange-300 border-orange-500/40'; assetIcon = '🐕 '; }

                rowsHtml += `
                    <div class="px-3.5 py-2.5 flex flex-col gap-1.5 ${isYes ? 'bg-emerald-950/20' : 'bg-rose-950/20'} hover:bg-white/[0.04] transition-colors">
                        <!-- Line 1: Direction Badge, Asset Badge, Trade Label, Live PnL -->
                        <div class="flex items-center justify-between gap-2 flex-wrap">
                            <div class="flex items-center gap-2 flex-wrap min-w-0">
                                <span class="text-xs font-bold text-white tracking-wide truncate ${isYes ? 'text-emerald-400' : 'text-rose-400'}">
                                    ${tradeLabel}
                                </span>
                                <span class="text-[8px] font-black px-1.5 py-0.5 rounded uppercase bg-blue-500/20 text-blue-300 border border-blue-500/35">ACTIVE</span>
                            </div>
                            <div class="flex items-baseline gap-1.5 font-mono shrink-0">
                                <span class="text-xs sm:text-sm font-black tabular-nums ${pnlColor}">${pnlStr}</span>
                                <span class="text-[9px] sm:text-[10px] font-bold ${pnlColor}">(${pnlPct}%)</span>
                            </div>
                        </div>

                        <!-- Line 2: Strike & Distance or Sport Info, Quick Action Buttons -->
                        <div class="flex items-center justify-between gap-2 text-[10px] font-mono">
                            <div class="text-gray-400 truncate text-[9px]">
                                ${isSport && sportInfo
                                    ? `<span class="text-[9px] font-black px-1.5 py-0.5 rounded uppercase tracking-wider border bg-cyan-500/20 text-cyan-300 border-cyan-500/40">${sportInfo.icon} ${sportInfo.sport}</span> <span class="text-gray-400 ml-1 font-sans">${t.ticker || ''}</span>`
                                    : (strike ? `Strike <span class="text-white font-bold">$${strike.toLocaleString()}</span>` + (distanceStr ? `<span class="ml-1.5">${distanceStr}</span>` : '') : '')}
                            </div>
                            <div class="flex items-center gap-1.5 shrink-0">
                                ${isSport ? '' : `<button onclick="executeManualTrade('${t.side}', '${t.asset}')" class="py-1 px-2.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-300 border border-blue-500/40 rounded-lg text-[9px] font-bold uppercase tracking-wider active:scale-95 transition-all flex items-center gap-1 cursor-pointer">
                                    <span>➕</span> ADD
                                </button>`}
                                <button onclick="takeProfitTrade('${t.id}')" class="py-1 px-2.5 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 rounded-lg text-[9px] font-bold uppercase tracking-wider active:scale-95 transition-all flex items-center gap-1 cursor-pointer">
                                    <span>⚡</span> TP
                                </button>
                                <button onclick="closeTrade('${t.id}', 'MANUAL_CLOSE')" class="py-1 px-2.5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 rounded-lg text-[9px] font-bold uppercase tracking-wider active:scale-95 transition-all flex items-center gap-1 cursor-pointer">
                                    <span>🛑</span> Close
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            });

            const totalColor = totalOpenPnl >= 0 ? 'text-emerald-400' : 'text-rose-400';
            const totalStr = (totalOpenPnl >= 0 ? '+$' : '-$') + Math.abs(totalOpenPnl).toFixed(2);

            container.innerHTML = `
                <div class="relative bg-[#0c1220]/95 border-b lg:border lg:border-t-0 lg:border-cyan-500/20 lg:rounded-b-2xl border-cyan-500/20 shadow-md overflow-hidden">
                    <div class="bg-black/60 px-3.5 py-1.5 border-b border-white/10 flex items-center justify-between text-[10px] font-mono">
                        <div class="flex items-center gap-2">
                            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                            <span class="text-gray-300 font-bold uppercase tracking-wider">Position Scanner · Active (${sortedOpen.length})</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="text-gray-400">Total PnL:</span>
                            <span class="font-bold tabular-nums ${totalColor}">${totalStr}</span>
                        </div>
                    </div>
                    <div class="divide-y divide-white/5 max-h-[35vh] overflow-y-auto">
                        ${rowsHtml}
                    </div>
                </div>
            `;
        }

        // ── Battle Tape Social Activity Feed (Feature 4) ──
        let battleTapeItems = [];
        let battleTapeIndex = 0;

        async function fetchBattleTape() {
            if (document.hidden || !window.isTabActive) return;
            try {
                const res = await fetch((window.API_BASE_URL||'')+'/api/auth/community/activity');
                if (!res.ok) return;
                const data = await res.json();
                battleTapeItems = data.activity || [];
                renderCurrentTapeItem();
            } catch(e) {}
        }

        function renderCurrentTapeItem() {
            const feed = document.getElementById('battleTapeFeed');
            if (!feed) return;
            if (battleTapeItems.length === 0) {
                feed.innerHTML = '<span class="text-[10px] text-gray-500 font-mono">No recent community executions</span>';
                return;
            }

            const item = battleTapeItems[battleTapeIndex % battleTapeItems.length];
            const isWin = item.pnl > 0;
            const pnlColor = isWin ? 'text-emerald-400' : 'text-rose-400';
            const pnlStr = (item.pnl >= 0 ? '+$' : '-$') + Math.abs(item.pnl).toFixed(2);
            const style = item.trading_style ? item.trading_style.replace(/_/g, ' ') : 'AUTO';

            feed.innerHTML = `
                <div class="flex items-center gap-2 overflow-hidden truncate font-mono text-[11px]">
                    <img src="${item.profile_pic || './assets/icon.png'}" class="w-4 h-4 rounded-full object-cover border border-kalshi-border shrink-0">
                    <span class="font-bold text-gray-200">@${item.username}</span>
                    <span class="px-1.5 py-0.5 rounded text-[8px] font-black uppercase ${item.side === 'YES' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'}">${item.side}</span>
                    <span class="text-[9px] text-gray-400 uppercase tracking-wider">${style}</span>
                    <span class="font-black ${pnlColor} text-[11px]">${pnlStr}</span>
                    <span class="text-[9px] text-gray-500 opacity-80 truncate">${item.exit_reason || item.status}</span>
                </div>
            `;
        }

        setInterval(() => {
            if (battleTapeItems.length > 0) {
                battleTapeIndex++;
                renderCurrentTapeItem();
            }
        }, 4000);

        setInterval(fetchBattleTape, 8000);
        window.addEventListener('load', fetchBattleTape);


        // ── Daily Quests & Badges ──
        async function fetchDailyQuests() {
            if (document.hidden || !window.isTabActive) return;
            try {
                const authToken = localStorage.getItem('saas_token') || token;
                const res = await fetch((window.API_BASE_URL||'')+'/api/auth/user/quests', {
                    headers: { 'Authorization': 'Bearer ' + authToken }
                });
                if (!res.ok) return;
                const data = await res.json();
                const q = data.quests || {};

                const lvl = 'LVL ' + (q.level || 1);
                const xpStr = `${q.xp_current_level || 0} / ${q.xp_next_level || 150} XP`;
                const pct = Math.min(100, Math.max(5, Math.round(((q.xp_current_level || 0) / (q.xp_next_level || 150)) * 100)));

                // Update Profile Dropdown Level Badge
                const dLvlBadge = document.getElementById('dropdown-quest-level-badge');
                if (dLvlBadge) dLvlBadge.textContent = lvl;
                
                // Update Profile Dropdown XP Text & Bar
                const dXpText = document.getElementById('dropdown-quest-xp-text');
                if (dXpText) dXpText.textContent = xpStr;

                const dXpBar = document.getElementById('dropdown-quest-xp-bar');
                if (dXpBar) dXpBar.style.width = pct + '%';

                const questHtml = (q.quests || []).map(item => `
                    <div class="flex items-center justify-between p-2 rounded-xl bg-black/40 border border-white/5 font-mono text-[9px]">
                        <div class="flex items-center gap-1.5 min-w-0">
                            <span class="text-xs shrink-0">${item.icon || '🎯'}</span>
                            <div class="flex flex-col truncate">
                                <span class="font-bold text-gray-200 truncate">${item.title}</span>
                                <span class="text-[7.5px] text-gray-500 truncate">${item.desc}</span>
                            </div>
                        </div>
                        <div class="flex items-center gap-1.5 shrink-0 pl-1">
                            <span class="font-bold ${item.completed ? 'text-emerald-400' : 'text-gray-400'}">${item.current}/${item.target}</span>
                            ${item.completed ? '<span class="text-emerald-400 font-bold">✓</span>' : `<span class="text-amber-400 font-bold">+${item.reward_xp}XP</span>`}
                        </div>
                    </div>
                `).join('');

                const dList = document.getElementById('dropdown-quest-list');
                if (dList && q.quests) dList.innerHTML = questHtml;

                const badgesHtml = (q.badges || []).map(b => `
                    <div class="p-1 rounded bg-amber-500/10 border border-amber-500/30 text-xs cursor-pointer hover:scale-110 transition-transform" title="${b.name}: ${b.desc}">
                        ${b.icon}
                    </div>
                `).join('') || '<span class="text-[8px] text-gray-600 font-mono">No badges yet</span>';

                const dBadges = document.getElementById('dropdown-badges-shelf');
                if (dBadges && q.badges) dBadges.innerHTML = badgesHtml;
            } catch(e) {}
        }
        setInterval(fetchDailyQuests, 12000);
        window.addEventListener('load', fetchDailyQuests);

        // ── Interactive Equity Curve & Analytics Studio (Feature 2) ──
        let activeEquityFilter = 'all';
        window.currentEquityData = null;

        window.openEquityModal = async function() {
            document.getElementById('profileDropdown')?.classList.add('hidden');
            const modal = document.getElementById('equityModal');
            if (!modal) return;
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';

            try {
                const res = await fetch((window.API_BASE_URL||'')+'/api/engine/analytics/equity', {
                    headers: { 'Authorization': 'Bearer ' + token }
                });
                if (!res.ok) throw new Error('Failed to fetch equity');
                const data = await res.json();
                const eq = data.equity || {};
                window.currentEquityData = eq;

                // High level metrics
                const curEl = document.getElementById('equity-cur-pnl');
                if (curEl) {
                    curEl.textContent = (eq.current_pnl >= 0 ? '+$' : '-$') + Math.abs(eq.current_pnl || 0).toFixed(2);
                    curEl.className = 'text-lg font-black tabular-nums ' + (eq.current_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400');
                }
                
                const peakEl = document.getElementById('equity-peak-pnl');
                if (peakEl) peakEl.textContent = '+$' + (eq.peak_pnl || 0).toFixed(2);

                const ddEl = document.getElementById('equity-max-dd');
                if (ddEl) ddEl.textContent = '-$' + (eq.max_drawdown || 0).toFixed(2);

                const tradesEl = document.getElementById('equity-total-trades');
                if (tradesEl) tradesEl.textContent = (eq.total_trades || 0) + ' Trades';

                // User Trading Analysis
                const u = eq.user_stats || {};
                const uPnlEl = document.getElementById('user-analysis-pnl');
                if (uPnlEl) {
                    uPnlEl.textContent = (u.pnl >= 0 ? '+$' : '-$') + Math.abs(u.pnl || 0).toFixed(2);
                    uPnlEl.className = 'text-sm font-black tabular-nums ' + (u.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400');
                }
                const uWrEl = document.getElementById('user-analysis-wr');
                if (uWrEl) uWrEl.textContent = (u.win_rate || 0).toFixed(1) + '%';
                const uWlEl = document.getElementById('user-analysis-wl');
                if (uWlEl) uWlEl.textContent = `${u.wins || 0}W - ${u.losses || 0}L (${u.total || 0})`;
                const uPfEl = document.getElementById('user-analysis-pf');
                if (uPfEl) uPfEl.textContent = (u.profit_factor || 1.0).toFixed(2);
                const uWinEl = document.getElementById('user-analysis-avg-win');
                if (uWinEl) uWinEl.textContent = '+$' + (u.avg_win || 0).toFixed(2);
                const uLossEl = document.getElementById('user-analysis-avg-loss');
                if (uLossEl) uLossEl.textContent = '-$' + (u.avg_loss || 0).toFixed(2);
                const uDirEl = document.getElementById('user-analysis-dir');
                if (uDirEl) uDirEl.textContent = `YES: ${u.yes_win_rate || 0}% (${u.yes_count || 0}) · NO: ${u.no_win_rate || 0}% (${u.no_count || 0})`;

                // Bot Trading Analysis
                const b = eq.bot_stats || {};
                const bPnlEl = document.getElementById('bot-analysis-pnl');
                if (bPnlEl) {
                    bPnlEl.textContent = (b.pnl >= 0 ? '+$' : '-$') + Math.abs(b.pnl || 0).toFixed(2);
                    bPnlEl.className = 'text-sm font-black tabular-nums ' + (b.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400');
                }
                const bWrEl = document.getElementById('bot-analysis-wr');
                if (bWrEl) bWrEl.textContent = (b.win_rate || 0).toFixed(1) + '%';
                const bWlEl = document.getElementById('bot-analysis-wl');
                if (bWlEl) bWlEl.textContent = `${b.wins || 0}W - ${b.losses || 0}L (${b.total || 0})`;
                const bPfEl = document.getElementById('bot-analysis-pf');
                if (bPfEl) bPfEl.textContent = (b.profit_factor || 1.0).toFixed(2);
                const bWinEl = document.getElementById('bot-analysis-avg-win');
                if (bWinEl) bWinEl.textContent = '+$' + (b.avg_win || 0).toFixed(2);
                const bLossEl = document.getElementById('bot-analysis-avg-loss');
                if (bLossEl) bLossEl.textContent = '-$' + (b.avg_loss || 0).toFixed(2);
                const bDirEl = document.getElementById('bot-analysis-dir');
                if (bDirEl) bDirEl.textContent = `YES: ${b.yes_win_rate || 0}% (${b.yes_count || 0}) · NO: ${b.no_win_rate || 0}% (${b.no_count || 0})`;

                // Strategy Performance Matrix
                const matrixBody = document.getElementById('strategy-matrix-body');
                if (matrixBody) {
                    const styles = eq.styles || [];
                    if (styles.length === 0) {
                        matrixBody.innerHTML = '<tr><td colspan="5" class="py-3 text-center text-gray-500 font-mono">No bot strategy trades recorded</td></tr>';
                    } else {
                        const styleIcons = {
                            'SNIPER': '🎯', 'AUTO': '🤖', 'CHOP': '✂️', 'MOMENTUM_SURFER': '🏄',
                            'AMBUSH': '🪤', 'PREDICTION': '🔮', 'SECOND_ENTRY': '🔄'
                        };
                        matrixBody.innerHTML = styles.map(s => {
                            const isPos = s.pnl >= 0;
                            const pnlColor = isPos ? 'text-emerald-400' : 'text-rose-400';
                            const pnlStr = (isPos ? '+$' : '-$') + Math.abs(s.pnl || 0).toFixed(2);
                            const avgStr = (s.avg_pnl >= 0 ? '+$' : '-$') + Math.abs(s.avg_pnl || 0).toFixed(2);
                            const icon = styleIcons[s.style] || '⚡';
                            return `
                                <tr class="hover:bg-white/5 transition-colors">
                                    <td class="py-2.5 font-bold text-gray-200 flex items-center gap-1.5">
                                        <span>${icon}</span> <span>${s.style}</span>
                                    </td>
                                    <td class="py-2.5 text-center text-gray-400">${s.total}</td>
                                    <td class="py-2.5 text-center font-bold ${s.win_rate >= 50 ? 'text-emerald-400' : 'text-rose-400'}">${s.win_rate}%</td>
                                    <td class="py-2.5 text-right font-black ${pnlColor}">${pnlStr}</td>
                                    <td class="py-2.5 text-right text-gray-400">${avgStr}</td>
                                </tr>
                            `;
                        }).join('');
                    }
                }

                // Asset Performance Matrix
                const assetBody = document.getElementById('asset-matrix-body');
                if (assetBody) {
                    const assets = eq.assets || [];
                    if (assets.length === 0) {
                        assetBody.innerHTML = '<tr><td colspan="5" class="py-3 text-center text-gray-500 font-mono">No asset trades recorded</td></tr>';
                    } else {
                        const assetIcons = {
                            'BTC': '₿', 'ETH': 'Ξ', 'GOLD': '🪙', 'NDQ': '📈', 'EURUSD': '💵',
                            'GBPUSD': '💷', 'USDJPY': '💴', 'AUDUSD': '🇦🇺', 'SOL': '🚀', 'DOGE': '🐕'
                        };
                        assetBody.innerHTML = assets.map(a => {
                            const isPos = a.pnl >= 0;
                            const pnlColor = isPos ? 'text-emerald-400' : 'text-rose-400';
                            const pnlStr = (isPos ? '+$' : '-$') + Math.abs(a.pnl || 0).toFixed(2);
                            const avgStr = (a.avg_pnl >= 0 ? '+$' : '-$') + Math.abs(a.avg_pnl || 0).toFixed(2);
                            const icon = assetIcons[a.asset] || '🔹';
                            return `
                                <tr class="hover:bg-white/5 transition-colors">
                                    <td class="py-2.5 font-bold text-gray-200 flex items-center gap-1.5">
                                        <span>${icon}</span> <span>${a.asset}</span>
                                    </td>
                                    <td class="py-2.5 text-center text-gray-400">${a.total}</td>
                                    <td class="py-2.5 text-center font-bold ${a.win_rate >= 50 ? 'text-emerald-400' : 'text-rose-400'}">${a.win_rate}%</td>
                                    <td class="py-2.5 text-right font-black ${pnlColor}">${pnlStr}</td>
                                    <td class="py-2.5 text-right text-gray-400">${avgStr}</td>
                                </tr>
                            `;
                        }).join('');
                    }
                }

                // Actionable AI Profit Improvement Recommendations
                const recContainer = document.getElementById('recommendations-container');
                if (recContainer) {
                    const recs = eq.recommendations || [];
                    if (recs.length === 0) {
                        recContainer.innerHTML = '<div class="text-[10px] text-gray-500 font-mono text-center py-2">Need more trade history to generate recommendations</div>';
                    } else {
                        const typeStyles = {
                            'danger': 'border-rose-500/30 bg-rose-950/20 text-rose-300',
                            'warning': 'border-amber-500/30 bg-amber-950/20 text-amber-300',
                            'success': 'border-emerald-500/30 bg-emerald-950/20 text-emerald-300',
                            'tip': 'border-cyan-500/30 bg-cyan-950/20 text-cyan-300',
                            'info': 'border-indigo-500/30 bg-indigo-950/20 text-indigo-300'
                        };
                        recContainer.innerHTML = recs.map(r => {
                            const styleClass = typeStyles[r.type] || typeStyles['tip'];
                            return `
                                <div class="p-3 rounded-xl border ${styleClass} flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                                    <div class="flex items-start gap-2.5">
                                        <span class="text-lg shrink-0 mt-0.5">${r.icon}</span>
                                        <div class="space-y-1">
                                            <div class="flex items-center gap-2">
                                                <h4 class="text-xs font-black uppercase tracking-wider text-white">${r.title}</h4>
                                                <span class="px-1.5 py-0.2 rounded text-[7.5px] font-black uppercase bg-black/40 border border-white/10">${r.badge}</span>
                                            </div>
                                            <p class="text-[10px] leading-relaxed text-gray-300 font-sans">${r.desc}</p>
                                        </div>
                                    </div>
                                    <button onclick="closeEquityModal(); openSettings();" class="shrink-0 px-3 py-1.5 rounded-lg bg-black/40 hover:bg-black/60 border border-white/20 text-[9px] font-black uppercase tracking-wider text-white active:scale-95 transition-all cursor-pointer">
                                        ${r.action || 'Configure'} →
                                    </button>
                                </div>
                            `;
                        }).join('');
                    }
                }

                switchEquityChart(activeEquityFilter || 'all');
            } catch(e) {
                document.getElementById('equity-chart-wrapper').innerHTML = '<div class="text-[10px] text-rose-400 font-mono">Failed to load equity analytics</div>';
            }
        };

        window.closeEquityModal = function() {
            document.getElementById('equityModal')?.classList.add('hidden');
            document.body.style.overflow = 'auto';
        };

        window.switchEquityChart = function(filter) {
            activeEquityFilter = filter;
            ['all', 'manual', 'bot'].forEach(k => {
                const btn = document.getElementById('eqTab-' + k);
                if (btn) {
                    if (k === filter) {
                        btn.className = 'px-2.5 py-1 rounded bg-indigo-600 text-white uppercase tracking-wider cursor-pointer transition-all shadow-sm';
                    } else {
                        btn.className = 'px-2.5 py-1 rounded text-gray-400 hover:text-white uppercase tracking-wider cursor-pointer transition-all';
                    }
                }
            });

            if (!window.currentEquityData) return;
            const pts = window.currentEquityData.points || [];
            let chartSeries = [];
            if (filter === 'manual') {
                chartSeries = pts.map(p => ({ pnl: p.manual_pnl !== undefined ? p.manual_pnl : p.pnl, ts: p.ts }));
            } else if (filter === 'bot') {
                chartSeries = pts.map(p => ({ pnl: p.bot_pnl !== undefined ? p.bot_pnl : p.pnl, ts: p.ts }));
            } else {
                chartSeries = pts.map(p => ({ pnl: p.pnl, ts: p.ts }));
            }
            renderEquitySvgChart(chartSeries);
        };

                function renderEquitySvgChart(points) {
            const wrapper = document.getElementById('equity-chart-wrapper');
            if (!wrapper) return;
            if (points.length < 2) {
                wrapper.innerHTML = '<div class="text-[10px] text-gray-500 font-mono">Need at least 2 closed trades to chart equity curve</div>';
                return;
            }
            wrapper.innerHTML = '';
            
            const chart = LightweightCharts.createChart(wrapper, {
                width: wrapper.clientWidth,
                height: 240,
                layout: { background: { type: 'solid', color: 'transparent' }, textColor: '#9ca3af' },
                grid: { vertLines: { color: 'rgba(255, 255, 255, 0.05)' }, horzLines: { color: 'rgba(255, 255, 255, 0.05)' } },
                rightPriceScale: { borderVisible: false },
                timeScale: { borderVisible: false, timeVisible: true }
            });
            const lineSeries = chart.addAreaSeries({
                lineColor: points[points.length-1].pnl >= 0 ? '#10b981' : '#f43f5e',
                topColor: points[points.length-1].pnl >= 0 ? 'rgba(16, 185, 129, 0.4)' : 'rgba(244, 63, 94, 0.4)',
                bottomColor: 'rgba(0, 0, 0, 0.0)',
                lineWidth: 2
            });
            
            const data = [];
            let lastTime = 0;
            for (let i = 0; i < points.length; i++) {
                let p = points[i];
                let ts = p.ts ? Math.floor(p.ts) : (Math.floor(Date.now() / 1000) - (points.length - i) * 60);
                if (ts <= lastTime) { ts = lastTime + 1; }
                data.push({ time: ts, value: p.pnl });
                lastTime = ts;
            }
            lineSeries.setData(data);
            chart.timeScale().fitContent();
        }



        // Update execution panel from status data
        function updateExecPanel(s) {
            const strike = document.getElementById('exec-strike');
            const spot = document.getElementById('exec-spot');
            const countdown = document.getElementById('exec-countdown');
            const yesBtn = document.getElementById('kalshi-yes');
            const noBtn = document.getElementById('kalshi-no');
            const timerYes = document.getElementById('timer-bid-yes');
            const timerNo = document.getElementById('timer-bid-no');
            const modeBadge = document.getElementById('exec-mode-badge');

            if (strike) {
                const sNum = Number(s.kalshi_strike);
                if (s.kalshi_strike && !isNaN(sNum) && isFinite(sNum) && sNum > 0) {
                    strike.textContent = '$' + sNum.toLocaleString();
                } else if (strike.textContent === '$--,---' || !strike.textContent) {
                    strike.textContent = '$--,---';
                }
            }
            if (s.btc_price && spot && (window.currentAsset || 'BTC') === 'BTC' && typeof updateSpotPriceDisplay === 'function' && !(typeof spotWsLive === 'function' && spotWsLive())) updateSpotPriceDisplay(Number(s.btc_price), 'BTC');
            if (s.countdown && countdown) countdown.textContent = s.countdown;
            if (s.yes_prob !== undefined) {
                const yPct = Math.round(s.yes_prob) + '%';
                if (yesBtn) yesBtn.textContent = yPct;
                if (timerYes) timerYes.textContent = yPct;
            }
            if (s.no_prob !== undefined) {
                const nPct = Math.round(s.no_prob) + '%';
                if (noBtn) noBtn.textContent = nPct;
                if (timerNo) timerNo.textContent = nPct;
            }
            if (s.mode && modeBadge) {
                modeBadge.textContent = s.mode;
                modeBadge.className = s.mode === 'LIVE' ? 'px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-widest bg-red-500/20 text-red-300 border border-red-500/40' : 'px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-widest bg-cyan-500/20 text-cyan-300 border border-cyan-500/40';
            }
        }


        // Real-Time High-Frequency Spot WebSocket & Display Sync
        let spotWs = null;
        let spotWsAsset = null;
        let _pendingWsSpotPrice = null;
        let _spotWsRafScheduled = false;

        function updateSpotPriceDisplay(spotVal, reqAsset) {
            reqAsset = (reqAsset || window.currentAsset || 'BTC').toUpperCase();
            if (!isFinite(spotVal) || spotVal <= 0) return;
            if (reqAsset !== (window.currentAsset || 'BTC').toUpperCase()) return;

            const spotEl = document.getElementById('exec-spot');
            if (!spotEl) return;

            const isFx = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'].includes(reqAsset);
            const decimals = reqAsset === 'USDJPY' ? 3 : (isFx ? 5 : (reqAsset === 'DOGE' ? 4 : 2));
            const prefix = isFx ? '' : '$';

            if (!window.assetSpotPrices) window.assetSpotPrices = {};
            const prevSpot = (window.assetSpotPrices && window.assetSpotPrices[reqAsset] !== undefined) ? window.assetSpotPrices[reqAsset] : (window.lastSpotPrice || spotVal);
            window.assetSpotPrices[reqAsset] = spotVal;
            window.lastSpotPrice = spotVal;

            const newText = prefix + spotVal.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

            if (spotEl.textContent !== newText) {
                if (spotVal < prevSpot) {
                    spotEl.classList.remove('text-emerald-400');
                    spotEl.classList.add('text-kalshi-red');
                } else if (spotVal > prevSpot) {
                    spotEl.classList.remove('text-kalshi-red');
                    spotEl.classList.add('text-emerald-400');
                }

                // Update chart candle / line seamlessly with real-time ticks
                if (window.lastCandle && typeof window.lastCandle.close === 'number') {
                    const ratio = spotVal / window.lastCandle.close;
                    if (ratio > 0.4 && ratio < 2.5) {
                        const newCandle = { ...window.lastCandle };
                        newCandle.close = spotVal;
                        if (spotVal > newCandle.high) newCandle.high = spotVal;
                        if (spotVal < newCandle.low) newCandle.low = spotVal;

                        try {
                            if (window.currentChartType === 'line' && lineSeries) {
                                lineSeries.update({ time: newCandle.time, value: spotVal });
                            } else if (candleSeries) {
                                candleSeries.update(newCandle);
                            }
                            window.lastCandle = newCandle;
                        } catch (updateErr) {
                            console.warn('[Chart] realtime tick update error:', updateErr);
                        }
                    }
                }

                spotEl.textContent = newText;
                spotEl.classList.remove('pulse-tick');
                void spotEl.offsetWidth;
                spotEl.classList.add('pulse-tick');
            }

            // Sync Strike Delta spread
            if (window.currentKalshiTarget) {
                const targetVal = Number(window.currentKalshiTarget);
                const diff = spotVal - targetVal;

                const diffArrow = document.getElementById('exec-diff-arrow');
                const diffVal = document.getElementById('exec-diff-val');
                const diffLabel = document.getElementById('exec-diff-label');

                if (diffArrow && diffVal) {
                    diffVal.textContent = prefix + Math.abs(diff).toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

                    diffLabel.classList.remove('text-emerald-400', 'text-kalshi-red');
                    diffArrow.classList.remove('text-emerald-400', 'text-kalshi-red');
                    diffVal.classList.remove('text-emerald-400', 'text-kalshi-red');

                    if (diff >= 0) {
                        diffArrow.textContent = '⬆';
                        diffLabel.classList.add('text-emerald-400');
                        diffArrow.classList.add('text-emerald-400');
                        diffVal.classList.add('text-emerald-400');
                    } else {
                        diffArrow.textContent = '⬇';
                        diffLabel.classList.add('text-kalshi-red');
                        diffArrow.classList.add('text-kalshi-red');
                        diffVal.classList.add('text-kalshi-red');
                    }
                }
            }
        }

        // ── Composite BRTI-style real-time feed ──────────────────────────────
        // Binance.com geo-blocks US users (HTTP 451), so we blend three US-accessible
        // public order-book feeds (Coinbase, Kraken, Binance.US) into one mid price,
        // mirroring how CF Benchmarks builds the BRTI from multiple exchanges.
        let spotFeeds = {};          // name -> WebSocket
        let spotMids = {};           // name -> { mid, ts }
        let _spotLastTickTs = 0;

        function spotWsLive() {
            return spotWsAsset === (window.currentAsset || 'BTC').toUpperCase() &&
                   (Date.now() - _spotLastTickTs) < 4000;
        }

        function _pushSpotMid(source, bid, ask, asset) {
            if (!(bid > 0) || !(ask > 0) || asset !== spotWsAsset) return;
            const now = Date.now();
            spotMids[source] = { mid: (bid + ask) / 2, ts: now };
            const fresh = Object.values(spotMids).filter(m => now - m.ts < 5000).map(m => m.mid);
            if (!fresh.length) return;
            const composite = fresh.reduce((s, v) => s + v, 0) / fresh.length;
            _spotLastTickTs = now;
            _pendingWsSpotPrice = composite;
            if (!_spotWsRafScheduled) {
                _spotWsRafScheduled = true;
                requestAnimationFrame(() => {
                    _spotWsRafScheduled = false;
                    if ((window.currentAsset || 'BTC').toUpperCase() !== spotWsAsset) return;
                    if (_pendingWsSpotPrice !== null) updateSpotPriceDisplay(_pendingWsSpotPrice, spotWsAsset);
                });
            }
        }

        function _closeSpotFeeds() {
            Object.values(spotFeeds).forEach(ws => { try { ws.onclose = null; ws.close(); } catch (e) {} });
            spotFeeds = {};
            spotMids = {};
            spotWs = null;
        }

        function _openSpotFeed(name, url, onOpen, onMsg, asset) {
            try {
                const ws = new WebSocket(url);
                ws.onopen = () => { try { onOpen && onOpen(ws); } catch (e) {} };
                ws.onmessage = (ev) => {
                    if (document.hidden) return;
                    try { onMsg(JSON.parse(ev.data)); } catch (e) {}
                };
                ws.onerror = () => { try { ws.close(); } catch (e) {} };
                ws.onclose = () => {
                    if (spotFeeds[name] === ws) delete spotFeeds[name];
                    setTimeout(() => {
                        if (spotWsAsset === asset && (window.currentAsset || 'BTC').toUpperCase() === asset && !spotFeeds[name]) {
                            _openSpotFeed(name, url, onOpen, onMsg, asset);
                        }
                    }, 3000);
                };
                spotFeeds[name] = ws;
                spotWs = ws;
            } catch (e) { console.warn('[SpotWS] ' + name + ' failed:', e); }
        }

        function initSpotWebSocket() {
            const asset = (window.currentAsset || 'BTC').toUpperCase();
            const map = {
                BTC:  { cb: 'BTC-USD',  kr: 'BTC/USD',  bu: 'btcusd'  },
                ETH:  { cb: 'ETH-USD',  kr: 'ETH/USD',  bu: 'ethusd'  },
                SOL:  { cb: 'SOL-USD',  kr: 'SOL/USD',  bu: 'solusd'  },
                DOGE: { cb: 'DOGE-USD', kr: 'DOGE/USD', bu: 'dogeusd' },
            };
            const sym = map[asset];
            if (!sym) { _closeSpotFeeds(); spotWsAsset = null; return; }
            if (spotWsAsset === asset && Object.keys(spotFeeds).length) return;

            _closeSpotFeeds();
            spotWsAsset = asset;

            // 1) Coinbase Exchange ticker (includes best_bid / best_ask)
            _openSpotFeed('coinbase', 'wss://ws-feed.exchange.coinbase.com',
                ws => ws.send(JSON.stringify({ type: 'subscribe', product_ids: [sym.cb], channels: ['ticker'] })),
                d => { if (d.type === 'ticker' && d.product_id === sym.cb) _pushSpotMid('coinbase', parseFloat(d.best_bid), parseFloat(d.best_ask), asset); },
                asset);

            // 2) Kraken v2 ticker with event_trigger=bbo -> fires on every best bid/offer change
            _openSpotFeed('kraken', 'wss://ws.kraken.com/v2',
                ws => ws.send(JSON.stringify({ method: 'subscribe', params: { channel: 'ticker', symbol: [sym.kr], event_trigger: 'bbo' } })),
                d => {
                    if (d.channel === 'ticker' && Array.isArray(d.data)) {
                        d.data.forEach(t => { if (t.symbol === sym.kr) _pushSpotMid('kraken', parseFloat(t.bid), parseFloat(t.ask), asset); });
                    }
                },
                asset);

            // 3) Binance.US raw bookTicker (top-of-book, millisecond updates)
            _openSpotFeed('binanceus', `wss://stream.binance.us:9443/ws/${sym.bu}@bookTicker`,
                null,
                d => { if (d.b && d.a) _pushSpotMid('binanceus', parseFloat(d.b), parseFloat(d.a), asset); },
                asset);
        }

        // Fetch Kalshi contract data for execution panel
        async function fetchKalshiData() {
            if (document.hidden || !window.isTabActive) return;
            const thisReqId = ++currentKalshiRequestId;
            const reqAsset = (window.currentAsset || 'BTC').toUpperCase();
            const curA = reqAsset.toLowerCase();

            try {
                const [kRes, cRes, tickerRes] = await Promise.all([
                    fetch((window.API_BASE_URL||'')+'/api/engine/' + curA + '/kalshi'),
                    fetch((window.API_BASE_URL||'')+'/api/engine/' + curA + '/countdown'),
                    fetch((window.API_BASE_URL||'')+'/api/engine/' + curA + '/ticker'),
                ]);

                // Drop response if user switched asset while awaiting
                if (reqAsset !== (window.currentAsset || 'BTC').toUpperCase()) {
                    return;
                }

                if (kRes.ok) {
                    const k = await kRes.json();
                    window.currentKalshiTarget = k.target_price;

                    // Save bids for active position PnL computation
                    if (k.yes_bid !== undefined) window.lastYesBid = Math.round(k.yes_bid * 100);
                    if (k.no_bid !== undefined) window.lastNoBid = Math.round(k.no_bid * 100);
                    
                    if (window.lastDashboardStats && typeof updateActivePositionHud === 'function') {
                        updateActivePositionHud(window.lastDashboardStats);
                    }

                    const strikeEl = document.getElementById('exec-strike');
                    if (strikeEl) {
                        const tp = Number(k.target_price);
                        if (k.target_price && !isNaN(tp) && isFinite(tp) && tp > 0) {
                            strikeEl.textContent = '$' + tp.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                        } else if (strikeEl.textContent === '$--,---' || !strikeEl.textContent) {
                            strikeEl.textContent = '$--,---';
                        }
                    }

                    const yesBid = document.getElementById('kalshi-yes');
                    const noBid  = document.getElementById('kalshi-no');
                    const timerYes = document.getElementById('timer-bid-yes');
                    const timerNo  = document.getElementById('timer-bid-no');
                    if (k.yes_prob !== undefined) {
                        const pct = Math.round(k.yes_prob) + '%';
                        if (yesBid) yesBid.textContent = pct;
                        if (timerYes) timerYes.textContent = pct;
                    }
                    if (k.no_prob !== undefined) {
                        const pct = Math.round(k.no_prob) + '%';
                        if (noBid) noBid.textContent = pct;
                        if (timerNo) timerNo.textContent = pct;
                    }
                    if (typeof updateTimerBidsVisibility === 'function') updateTimerBidsVisibility();
                }

                if (cRes.ok) {
                    const c = await cRes.json();
                    const cdEl = document.getElementById('exec-countdown');
                    if (cdEl) cdEl.textContent = c.formatted || c.countdown || '--:--';

                    // Audio cue warning at <= 15s
                    const sec = c.seconds_left !== undefined ? c.seconds_left : (c.countdown ? parseInt(c.countdown.split(':')[1]) : 99);
                    if (sec <= 15 && sec > 0 && lastPlayedCountdownSec !== sec && (sec === 15 || sec === 10 || sec === 5)) {
                        lastPlayedCountdownSec = sec;
                        soundEngine.play('countdown_warning');
                    }
                }

                if (tickerRes.ok) {
                    const tickerData = await tickerRes.json();
                    if (tickerData && tickerData.price) {
                        const spotVal = Number(tickerData.price);
                        if (isFinite(spotVal) && spotVal > 0) {
                            // If WebSocket stream is actively updating this asset, let WebSocket drive the live ticks;
                            // otherwise, update from the periodic ticker snapshot
                            if (!spotWsLive()) {
                                updateSpotPriceDisplay(spotVal, reqAsset);
                            }
                        }
                    }
                }
            } catch(e) { console.warn('[ExecPanel] fetch err', e); }
        }
        fetchKalshiData();
        if (typeof initSpotWebSocket === 'function') initSpotWebSocket();
        if (typeof syncSoundSettingsUI === 'function') syncSoundSettingsUI();
        setInterval(fetchKalshiData, 1000);

        // Close profile dropdown when clicking outside
        document.addEventListener('click', function(e) {
            const dd = document.getElementById('profileDropdown');
            const avatar = document.getElementById('nav-avatar');
            if (dd && !dd.contains(e.target) && avatar && !avatar.parentElement.contains(e.target)) {
                dd.classList.add('hidden');
            }
        });

        if (new URLSearchParams(window.location.search).get('open') === 'community') {
            setTimeout(openCommunityModal, 300);
        }
