
        // Check URL query parameters for token rehydration, e.g. ?token=... or ?auth_token=...
        (function() {
            try {
                const qp = new URLSearchParams(window.location.search);
                const queryToken = qp.get('token') || qp.get('auth_token');
                if (queryToken && queryToken.split('.').length === 3) {
                    localStorage.setItem('saas_token', queryToken);
                    document.cookie = "saas_token=" + queryToken + "; path=/; max-age=7776000; SameSite=Lax";
                    qp.delete('token');
                    qp.delete('auth_token');
                    const newSearch = qp.toString() ? '?' + qp.toString() : '';
                    window.history.replaceState({}, document.title, window.location.pathname + newSearch + window.location.hash);
                }
            } catch(e) {}
        })();

        // Resolve active session token from localStorage or cookie
        function getCookie(name) {
            const v = '; ' + document.cookie;
            const parts = v.split('; ' + name + '=');
            if (parts.length === 2) return parts.pop().split(';').shift();
            return null;
        }
        let token = localStorage.getItem('saas_token') || getCookie('saas_token');
        if (!token) {
            window.location.replace('./login.html?logged_out=1');
        } else if (!localStorage.getItem('saas_token')) {
            localStorage.setItem('saas_token', token);
        }
        
        let currentMode = "PAPER";
        let aiEnabled = true; // Assume true since we removed toggle to simplify iPhone UI. We could re-add if requested.

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
            document.querySelectorAll('#settings-sound-toggle, #sports-settings-sound-toggle, #inv-settings-sound-toggle').forEach(toggle => {
                toggle.checked = isEnabled;
            });
            document.querySelectorAll('#settings-sound-icon, #sports-settings-sound-icon, #inv-settings-sound-icon').forEach(icon => {
                icon.textContent = isEnabled ? '🔊' : '🔇';
            });
            document.querySelectorAll('#settings-sound-status, #sports-settings-sound-status, #inv-settings-sound-status').forEach(statusBadge => {
                statusBadge.textContent = isEnabled ? 'ACTIVE' : 'MUTED';
                statusBadge.className = isEnabled 
                    ? 'text-[9px] font-bold text-emerald-400 uppercase tracking-widest' 
                    : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';
            });
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
            const bidsContainer = document.getElementById('timer-bids-container');
            if (!bidsContainer) return;
            bidsContainer.classList.remove('hidden');
            bidsContainer.classList.add('flex');
            bidsContainer.style.display = 'flex';
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
                        showToast(`Switched to ${mode} mode`, mode === 'LIVE' ? 'warning' : 'success', 2000);
                    }
                    loadDashboard(true);
                    if (typeof fetchInvestmentsPortfolio === 'function') {
                        fetchInvestmentsPortfolio();
                    }
                    if (window.currentUniverse === 'INVESTMENTS') {
                        if (typeof fetchInvestmentsFeed === 'function') fetchInvestmentsFeed(true);
                    }
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
                    ? 'w-12 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest text-center bg-red-500/20 text-red-300 border border-red-500/40 leading-none shadow-sm cursor-pointer hover:scale-105 transition-all' 
                    : 'w-12 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest text-center bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 leading-none shadow-sm cursor-pointer hover:scale-105 transition-all';
            }

            const stTexts = document.querySelectorAll('#settings-mode-text, #sports-settings-mode-text, #inv-settings-mode-text');
            stTexts.forEach(stText => {
                stText.textContent = currentMode;
                stText.className = currentMode === 'LIVE' 
                    ? 'text-[9px] font-bold text-red-400 uppercase tracking-widest' 
                    : 'text-[9px] font-bold text-cyan-400 uppercase tracking-widest';
            });

            const paperBtns = document.querySelectorAll('#btn-mode-paper-settings, #sports-btn-mode-paper-settings, #inv-btn-mode-paper-settings');
            const liveBtns = document.querySelectorAll('#btn-mode-live-settings, #sports-btn-mode-live-settings, #inv-btn-mode-live-settings');

            if (currentMode === 'LIVE') {
                liveBtns.forEach(b => { b.className = 'flex-1 py-2 text-[11px] font-bold tracking-wider rounded-lg transition-all z-10 text-white bg-red-500/25 border border-red-500/40 shadow-sm flex items-center justify-center gap-1.5 cursor-pointer'; });
                paperBtns.forEach(b => { b.className = 'flex-1 py-2 text-[11px] font-bold tracking-wider rounded-lg transition-all z-10 text-gray-400 hover:text-white border border-transparent flex items-center justify-center gap-1.5 cursor-pointer'; });
            } else {
                paperBtns.forEach(b => { b.className = 'flex-1 py-2 text-[11px] font-bold tracking-wider rounded-lg transition-all z-10 text-white bg-cyan-500/25 border border-cyan-500/40 shadow-sm flex items-center justify-center gap-1.5 cursor-pointer'; });
                liveBtns.forEach(b => { b.className = 'flex-1 py-2 text-[11px] font-bold tracking-wider rounded-lg transition-all z-10 text-gray-400 hover:text-white border border-transparent flex items-center justify-center gap-1.5 cursor-pointer'; });
            }

            const invKpiMode = document.getElementById('inv-kpi-mode-badge');
            if (invKpiMode) {
                invKpiMode.textContent = currentMode;
                invKpiMode.className = currentMode === 'LIVE'
                    ? 'text-[8px] font-black px-1.5 py-0.5 rounded uppercase bg-red-500/20 text-red-300 border border-red-500/35'
                    : 'text-[8px] font-black px-1.5 py-0.5 rounded uppercase bg-cyan-500/20 text-cyan-300 border border-cyan-500/35';
            }
            const invTicketMode = document.getElementById('inv-ticket-mode-badge');
            if (invTicketMode) {
                invTicketMode.textContent = currentMode;
                invTicketMode.className = currentMode === 'LIVE'
                    ? 'px-1.5 py-0.5 rounded text-[8px] font-black uppercase tracking-wider bg-red-500/20 text-red-300 border border-red-500/35 cursor-pointer'
                    : 'px-1.5 py-0.5 rounded text-[8px] font-black uppercase tracking-wider bg-cyan-500/20 text-cyan-300 border border-cyan-500/35 cursor-pointer';
            }

            // Only show paper trading settings when in PAPER mode across all universes
            const isPaperMode = (currentMode === 'PAPER');
            document.querySelectorAll('.paper-only-setting').forEach(el => {
                el.style.display = isPaperMode ? '' : 'none';
            });

            // Dynamically contextualize sizing labels across Financial and Sports drawers
            const finLabel = document.getElementById('fin-trade-size-label');
            if (finLabel) {
                finLabel.textContent = isPaperMode ? 'Paper Trade Size ($)' : 'Live Trade Size ($)';
            }
            const sportsLabel = document.getElementById('sports-trade-size-label');
            if (sportsLabel) {
                sportsLabel.textContent = isPaperMode ? 'Sports Paper Wager ($)' : 'Sports Live Wager ($)';
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
                    const activeAsset = overrideAsset || (window.currentAsset || 'BTC');
                    const payload = { direction: direction, amount_dollars: parseFloat(amt), asset: activeAsset,
                min_sports_confidence: document.getElementById('sports-conf-slider') ? parseInt(document.getElementById('sports-conf-slider').value) : 70,
                min_sports_edge: document.getElementById('sports-edge-slider') ? parseInt(document.getElementById('sports-edge-slider').value) : 3,
                sports_max_wager: document.getElementById('sports-wager-dollars') ? parseInt(document.getElementById('sports-wager-dollars').value) : 10,
                sports_include_live: document.getElementById('sports-include-live-toggle') ? document.getElementById('sports-include-live-toggle').checked : false
        };
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
                const headerToggles = document.querySelectorAll('#header-auto-toggle, #sports-header-auto-toggle, #inv-header-auto-toggle');
                headerToggles.forEach(t => { t.checked = enabled; });

                const navAutoBadge = document.getElementById('nav-auto-badge');
                if (navAutoBadge) {
                    navAutoBadge.innerHTML = enabled ? '<span class="flex items-center justify-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>AUTO</span>' : 'AUTO';
                    navAutoBadge.className = enabled
                        ? 'w-12 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest text-center flex items-center justify-center bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 leading-none shadow-sm'
                        : 'w-12 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest text-center flex items-center justify-center bg-gray-800 text-gray-400 border border-gray-700 leading-none shadow-sm';
                }

                // Update Dynamic Island
                if (typeof updateDynamicIsland === 'function') updateDynamicIsland(enabled);

                const inSports = (window.currentUniverse === 'SPORTS');
                const inInvestments = (window.currentUniverse === 'INVESTMENTS');
                let targetAsset = inInvestments ? 'INVESTMENTS' : (inSports ? 'SPORTS' : ((window.currentAsset || 'BTC').toLowerCase()));
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
                    const msg = enabled
                        ? (inInvestments ? '🏛️ Agentic Auto-Trader Active (Investments)' : (inSports ? '🏈 Auto-Trading Active (Sports Universe)' : '⚡ Auto-Trading Active'))
                        : '⏸ Auto-Trading Paused';
                    showToast(msg, enabled ? 'success' : 'info');
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
            if (typeof window.updateFinancialAssetSelectorVisibility === 'function') {
                window.updateFinancialAssetSelectorVisibility();
            }

            // Collect active sports leagues
            const activeSportsLeagues = [];
            document.querySelectorAll('input.sports-league-toggle').forEach(t => {
                const v = String(t.value).trim().toUpperCase();
                if (t.checked && !activeSportsLeagues.includes(v)) activeSportsLeagues.push(v);
            });
            const sportsActiveLeaguesStr = activeSportsLeagues.length > 0 ? activeSportsLeagues.join(',') : 'NFL,MLB,NBA,NHL,NCAAF,NPB/KBO,SOC,UFC,TEN';
            if (typeof window.updateSportsAssetSelectorVisibility === 'function') {
                window.updateSportsAssetSelectorVisibility();
            }

            // Collect allowed sports market types
            const activeSportsMarketTypes = [];
            document.querySelectorAll('input.sports-market-toggle').forEach(t => {
                const v = String(t.value).trim().toUpperCase();
                if (t.checked && !activeSportsMarketTypes.includes(v)) activeSportsMarketTypes.push(v);
            });
            const sportsMarketTypesStr = activeSportsMarketTypes.length > 0 ? activeSportsMarketTypes.join(',') : 'GAME,SPREAD,TOTAL,PROP,INNING';

            // Collect allowed sports player props
            const activeSportsProps = [];
            document.querySelectorAll('input.sports-prop-toggle').forEach(t => {
                const v = String(t.value).trim().toUpperCase();
                if (t.checked && !activeSportsProps.includes(v)) activeSportsProps.push(v);
            });
            const sportsActivePropsStr = activeSportsProps.length > 0 ? activeSportsProps.join(',') : 'ANYTIME_TD,PASSING_YDS,RUSHING_YDS,RECEIVING_YDS,HOME_RUNS,STRIKEOUTS,HITS_RUNS_RBIS,TOTAL_BASES,OTHER';

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
                    gemini_every_interval_enabled: document.getElementById('gemini-every-interval-toggle') ? document.getElementById('gemini-every-interval-toggle').checked : false,
                    regime_mode: document.getElementById('regime-mode-select') ? document.getElementById('regime-mode-select').value : 'AUTO_ADAPTIVE',
                    chop_engine_enabled: true,
                    chop_take_profit_cents: document.getElementById('chop-tp-cents-input') ? parseFloat(document.getElementById('chop-tp-cents-input').value) || 12.0 : 12.0,
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
                    sports_market_types: sportsMarketTypesStr,
                    sports_active_props: sportsActivePropsStr,
                    sports_strategy: window.currentSportsStrategy || 'STANDARD',
                    sports_max_parlay_legs: parseInt(document.getElementById('sports-max-parlay-legs')?.value || 2),
                    sports_sport_config: (typeof window.getSportsSportConfig === 'function' ? window.getSportsSportConfig() : null)
                };

                // Immediately update local cache so background polling doesn't fight this
                if (window.lastDashboardStats) {
                    Object.assign(window.lastDashboardStats, configPayload);
                }
                if (typeof renderTradeSlip === 'function' && window.sportsTradeSlip && window.sportsTradeSlip.length > 0) {
                    renderTradeSlip();
                }
                if (typeof updateParlayPayoutPreviews === 'function') {
                    updateParlayPayoutPreviews();
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

        // Visual Distinction for Every-Interval Gemini Deep Reasoning
        window.updateGeminiEveryIntervalVisuals = function(enabled) {
            // 1. Settings Drawer Badge & Icon
            const badge = document.getElementById('gemini-every-interval-status-badge');
            const row = document.getElementById('gemini-every-interval-row');
            const icon = document.getElementById('gemini-every-interval-icon');
            if (badge) {
                if (enabled) {
                    badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-purple-400 animate-ping"></span>ACTIVE ON';
                    badge.className = 'px-1.5 py-0.5 rounded text-[8px] font-black uppercase tracking-wider bg-purple-500/30 text-purple-200 border border-purple-400/50 flex items-center gap-1 shadow-[0_0_10px_rgba(168,85,247,0.4)]';
                } else {
                    badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-gray-500"></span>OFF';
                    badge.className = 'px-1.5 py-0.5 rounded text-[8px] font-black uppercase tracking-wider bg-purple-500/20 text-purple-300 border border-purple-500/30 flex items-center gap-1';
                }
            }
            if (row) {
                if (enabled) {
                    row.classList.add('bg-purple-900/25', 'border-purple-500/40', 'shadow-[0_0_20px_rgba(168,85,247,0.15)]');
                    row.classList.remove('border-transparent');
                } else {
                    row.classList.remove('bg-purple-900/25', 'border-purple-500/40', 'shadow-[0_0_20px_rgba(168,85,247,0.15)]');
                    row.classList.add('border-transparent');
                }
            }
            if (icon) {
                if (enabled) {
                    icon.className = 'w-7 h-7 rounded-lg bg-purple-500/30 border border-purple-400/60 text-purple-300 flex items-center justify-center shrink-0 text-xs font-bold mt-0.5 shadow-[0_0_10px_rgba(168,85,247,0.5)]';
                } else {
                    icon.className = 'w-7 h-7 rounded-lg bg-purple-500/15 border border-purple-500/30 text-purple-400 flex items-center justify-center shrink-0 text-xs font-bold mt-0.5';
                }
            }

            // 2. Top Navigation Bar Badge
            const navBadge = document.getElementById('nav-gemini-every-badge');
            if (navBadge) {
                if (enabled) {
                    navBadge.classList.remove('hidden');
                    navBadge.classList.add('inline-flex');
                } else {
                    navBadge.classList.add('hidden');
                    navBadge.classList.remove('inline-flex');
                }
            }

            // 3. Main Dashboard Gemini Dossier Card Banner
            const banner = document.getElementById('gemini-dossier-force-banner');
            const card = document.getElementById('gemini-live-dossier-card');
            if (banner) {
                if (enabled) {
                    banner.classList.remove('hidden');
                    banner.classList.add('flex');
                } else {
                    banner.classList.add('hidden');
                    banner.classList.remove('flex');
                }
            }
            if (card) {
                if (enabled) {
                    card.classList.add('ring-1', 'ring-purple-500/50', 'shadow-[0_0_25px_rgba(168,85,247,0.2)]');
                } else {
                    card.classList.remove('ring-1', 'ring-purple-500/50', 'shadow-[0_0_25px_rgba(168,85,247,0.2)]');
                }
            }
        };

        window.onGeminiEveryIntervalChange = function(checked) {
            window.updateGeminiEveryIntervalVisuals(checked);
            saveUserConfig();
        };

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
                const inInvestments = (window.currentUniverse === 'INVESTMENTS');
                if (inInvestments) {
                    if (typeof fetchInvestmentsConfig === 'function') fetchInvestmentsConfig();
                    return;
                }
                const curA = inSports ? 'sports' : (window.currentAsset || 'BTC').toLowerCase();
                const res = await fetch(`${window.API_BASE_URL||''}/api/engine/${curA}/trade/config`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if(res.ok) {
                    const c = await res.json();
                    
                    if(c.enabled !== undefined) {
                        const headerToggles = document.querySelectorAll('#header-auto-toggle, #sports-header-auto-toggle');
                        headerToggles.forEach(t => { t.checked = c.enabled; });
                        
                        const navAutoBadge = document.getElementById('nav-auto-badge');
                        if(navAutoBadge) {
                            navAutoBadge.innerHTML = c.enabled ? '<span class="flex items-center justify-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>AUTO</span>' : 'AUTO';
                            navAutoBadge.className = c.enabled ? 'w-12 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest text-center flex items-center justify-center bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 leading-none shadow-sm' : 'w-12 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest text-center flex items-center justify-center bg-gray-800 text-gray-400 border border-gray-700 leading-none shadow-sm';
                        }
                        // Sync Dynamic Island glow with server state
                        if (typeof updateDynamicIsland === 'function') updateDynamicIsland(c.enabled);
                    }
                }
            } catch(e) {}
        }

        
        let knownOpenTrades = new Set();

        var knownCompletedTrades = new Set();
        let _knownInitializedModes = new Set();
        window.enableIosNotifications = localStorage.getItem("enableIosNotifications") !== "false";

        window.toggleIosNotifications = function(checked) {
            window.enableIosNotifications = checked;
            localStorage.setItem("enableIosNotifications", checked);
            if (checked && "Notification" in window && Notification.permission !== "granted" && Notification.permission !== "denied") {
                Notification.requestPermission().then(permission => {
                    if (permission === "granted") {
                        if (typeof showToast === "function") showToast("System notifications enabled!", "success");
                    }
                });
            }
        };

        window.iosNotify = function(title, subtitle, type="success") {
            if (!window.enableIosNotifications) return;

            const isUserInApp = (document.visibilityState === 'visible') || (typeof document.hasFocus === 'function' && document.hasFocus()) || Boolean(window.isTabActive);
            if (!isUserInApp && "Notification" in window && Notification.permission === "granted") {
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
            const toast = document.createElement('div');
            const badgeColor = type === 'success' ? 'border-emerald-500/40 bg-slate-900/95 text-emerald-400' : 'border-rose-500/40 bg-slate-900/95 text-rose-400';
            toast.className = `px-4 py-2.5 rounded-xl border ${badgeColor} shadow-lg backdrop-blur-md text-xs font-bold transition-all duration-300 translate-y-[-150%] opacity-0`;
            toast.innerHTML = `<div class="font-extrabold">${title}</div><div class="text-[11px] text-slate-300 font-normal">${subtitle || ''}</div>`;
            container.appendChild(toast);
            requestAnimationFrame(() => requestAnimationFrame(() => toast.classList.remove('translate-y-[-150%]', 'opacity-0')));
            setTimeout(() => {
                toast.classList.add('translate-y-[-150%]', 'opacity-0');
                setTimeout(() => toast.remove(), 500);
            }, 5000);
            try { if(type === "success" && window.soundEngine) window.soundEngine.play('order_fill'); } catch(e){}
        };

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
                        script.src = './js/admin_users.js?v=1792013050';
                        document.body.appendChild(script);
                    }
                } else {
                    adminGroup.classList.add('hidden');
                }
            }
            
            const finDrawer = document.getElementById('financialSettingsDrawer');
            const sportsDrawer = document.getElementById('sportsSettingsDrawer');
            const invDrawer = document.getElementById('investmentsSettingsDrawer');
            const isSettingsOpen = (finDrawer && !finDrawer.classList.contains('hidden')) || (sportsDrawer && !sportsDrawer.classList.contains('hidden')) || (invDrawer && !invDrawer.classList.contains('hidden'));
            const isFocusInSettings = (finDrawer && finDrawer.contains(document.activeElement)) || (sportsDrawer && sportsDrawer.contains(document.activeElement)) || (invDrawer && invDrawer.contains(document.activeElement));

            // If the user has already loaded settings and the settings drawer is currently open or focused,
            // DO NOT overwrite inputs/toggles under the user's cursor unless explicitly forced!
            if (!force && window.userSettingsPopulated && (isSettingsOpen || isFocusInSettings)) {
                return;
            }

            if (s.trading_mode) {
                currentMode = s.trading_mode;
                if (typeof updateModeUI === 'function') updateModeUI();
            }

            if (s.ai_enabled !== undefined) {
                const autoToggles = document.querySelectorAll('#header-auto-toggle, #sports-header-auto-toggle, #inv-header-auto-toggle');
                autoToggles.forEach(t => { t.checked = !!s.ai_enabled; });
                const navAutoBadge = document.getElementById('nav-auto-badge');
                if (navAutoBadge) {
                    navAutoBadge.innerHTML = s.ai_enabled ? '<span class="flex items-center justify-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>AUTO</span>' : 'AUTO';
                    navAutoBadge.className = s.ai_enabled
                        ? 'w-12 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest text-center flex items-center justify-center bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 leading-none shadow-sm'
                        : 'w-12 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest text-center flex items-center justify-center bg-gray-800 text-gray-400 border border-gray-700 leading-none shadow-sm';
                }
                if (typeof updateDynamicIsland === 'function') updateDynamicIsland(!!s.ai_enabled);
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
                    const viewTab = (tu === 'SPORTS') ? 'SPORTS' : (tu === 'INVESTMENTS' ? 'INVESTMENTS' : 'FINANCIAL');
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
                if (typeof window.updateSportsAssetSelectorVisibility === 'function') {
                    window.updateSportsAssetSelectorVisibility();
                }
            }
            // Sports market types
            if (s.sports_market_types !== undefined) {
                const mtypes = (s.sports_market_types || '').split(',').map(m => m.trim().toUpperCase());
                document.querySelectorAll('input.sports-market-toggle').forEach(t => {
                    const v = String(t.value).trim().toUpperCase();
                    t.checked = mtypes.includes(v) || (v === 'PROP' && (mtypes.includes('PLAYER_PROP') || mtypes.includes('PROPS')));
                });
            }
            if (s.sports_active_props !== undefined) {
                const ptypes = (s.sports_active_props || '').split(',').map(m => m.trim().toUpperCase());
                document.querySelectorAll('input.sports-prop-toggle').forEach(t => {
                    t.checked = ptypes.includes(String(t.value).trim().toUpperCase());
                });
            }
            if (typeof window.sportsPanelsFromSettings === 'function') window.sportsPanelsFromSettings(s);
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
            // Sports Strategy & Parlay settings
            if (s.sports_max_parlay_legs !== undefined) {
                const legVal = Math.max(2, Math.min(30, parseInt(s.sports_max_parlay_legs) || 2));
                if (document.getElementById('sports-max-parlay-legs') && document.activeElement?.id !== 'sports-max-parlay-legs') {
                    document.getElementById('sports-max-parlay-legs').value = String(legVal);
                }
                if (document.getElementById('sports-parlay-legs-input') && document.activeElement?.id !== 'sports-parlay-legs-input') {
                    document.getElementById('sports-parlay-legs-input').value = String(legVal);
                }
                if (legVal < 10 && document.getElementById('strat-card-power-legs') && document.activeElement?.id !== 'strat-card-power-legs') {
                    document.getElementById('strat-card-power-legs').value = String(legVal);
                } else if (legVal >= 10 && document.getElementById('strat-card-ultra-legs') && document.activeElement?.id !== 'strat-card-ultra-legs') {
                    document.getElementById('strat-card-ultra-legs').value = String(legVal);
                }
            }
            if (s.sports_strategy !== undefined && typeof applySportsStrategyUI === 'function') {
                applySportsStrategyUI(s.sports_strategy);
            }
            if (typeof updateParlayPayoutPreviews === 'function') {
                updateParlayPayoutPreviews();
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
                if (typeof window.updateFinancialAssetSelectorVisibility === 'function') {
                    window.updateFinancialAssetSelectorVisibility();
                }
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

            const geminiEveryEl = document.getElementById('gemini-every-interval-toggle');
            if (geminiEveryEl && s.gemini_every_interval_enabled !== undefined) {
                geminiEveryEl.checked = !!s.gemini_every_interval_enabled;
                if (typeof window.updateGeminiEveryIntervalVisuals === 'function') {
                    window.updateGeminiEveryIntervalVisuals(!!s.gemini_every_interval_enabled);
                }
            }
            if (document.getElementById('regime-mode-select') && s.regime_mode) {
                document.getElementById('regime-mode-select').value = s.regime_mode;
                const rContainer = document.querySelector('[data-target="regime-mode-select"]');
                if (rContainer) {
                    const rText = rContainer.querySelector('.selected-text');
                    const rOpt = document.getElementById('regime-mode-select').querySelector(`option[value="${s.regime_mode}"]`);
                    if (rText && rOpt) rText.textContent = rOpt.textContent;
                }
            }
            if (document.getElementById('chop-tp-cents-input') && s.chop_take_profit_cents !== undefined) {
                document.getElementById('chop-tp-cents-input').value = s.chop_take_profit_cents;
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

            // Investments Settings Drawer population
            const setInvField = (id, val) => {
                const el = document.getElementById(id);
                if (el && val !== undefined && val !== null && document.activeElement !== el) {
                    if (el.type === 'checkbox') el.checked = !!val;
                    else el.value = val;
                }
            };
            setInvField('inv-auto-toggle', s.investments_enabled);
            setInvField('inv-mode-select', s.investments_trading_mode);
            setInvField('inv-rh-auth-mode', s.rh_auth_mode);
            setInvField('inv-rh-username', s.robinhood_username);
            setInvField('inv-paper-balance', s.investments_paper_balance);
            setInvField('inv-trade-size', s.investments_trade_size_dollars);
            setInvField('inv-paper-trade-size', s.investments_paper_trade_size_dollars);
            setInvField('inv-max-open-positions', s.investments_max_open_positions);
            setInvField('inv-max-daily-trades', s.investments_max_daily_trades);
            setInvField('inv-max-daily-risk', s.investments_max_daily_risk ?? s.investments_max_daily_loss_dollars);
            setInvField('inv-asset-classes', s.investments_asset_classes);
            setInvField('inv-min-confidence', s.investments_min_confidence ?? s.investments_min_ai_confidence);
            setInvField('inv-min-rvol', s.investments_min_rvol);
            setInvField('inv-options-delta', s.investments_options_delta_target);
            setInvField('inv-options-dte', s.investments_options_dte_window);
            setInvField('inv-options-spread', s.investments_options_max_spread_pct);
            setInvField('inv-options-oi', s.investments_options_min_oi);
            setInvField('inv-eod-flatten-toggle', s.investments_eod_auto_flatten ?? s.investments_auto_flatten_eod);
            setInvField('inv-trailing-stop-toggle', s.investments_trailing_stop_enabled);
            setInvField('inv-stock-tp', s.investments_stock_tp_pct ?? s.investments_take_profit_pct);
            setInvField('inv-stock-sl', s.investments_stock_sl_pct ?? s.investments_stop_loss_pct);
            setInvField('inv-option-tp', s.investments_option_tp_pct);
            setInvField('inv-option-sl', s.investments_option_sl_pct);
            setInvField('inv-watchlist', s.investments_watchlist);

            if (typeof syncCustomDropdowns === 'function') {
                syncCustomDropdowns();
            }
            window.userSettingsPopulated = true;
        }

        let _hasInitialDashboardLoaded = false;
        let _loadDashboardInFlight = false;
        async function loadDashboard(force = false) {
            if ((document.hidden || !window.isTabActive) && !force && _hasInitialDashboardLoaded) return;
            if (_loadDashboardInFlight && !force) return;
            _loadDashboardInFlight = true;
            try {
                token = localStorage.getItem('saas_token') || getCookie('saas_token') || token;
                const res = await fetch((window.API_BASE_URL||'')+'/api/auth/dashboard_stats', {
                    headers: { 'Authorization': `Bearer ${token}` },
                    credentials: 'include'
                });
                if(!res.ok) {
                    if(res.status === 401) logout();
                    return;
                }
                const s = await res.json();
                _hasInitialDashboardLoaded = true;
                window.lastDashboardStats = s;

                if (currentMode !== s.trading_mode) {
                    currentMode = s.trading_mode || "PAPER";
                    updateModeUI();
                }

                // First time loading a mode (e.g. initial load or switching between LIVE/PAPER),
                // seed all existing completed trades into knownCompletedTrades so they don't trigger false alerts
                const isNewModeLoad = !_knownInitializedModes.has(currentMode);

                // iOS Notifications for newly closed trades (mode-scoped and deduplicated by contract)
                if (s.recent_trades && Array.isArray(s.recent_trades)) {
                    s.recent_trades.forEach(t => {
                        const status = String(t.status || '').toUpperCase();
                        const tradeMode = String(t.mode || currentMode).toUpperCase();
                        const scopedTradeId = `${tradeMode}_${t.id}`;
                        const contractOutcomeKey = `${tradeMode}_${t.ticker}_${String(t.side || '').toUpperCase()}_${status}`;
                        if (status === 'CLOSED' || status.includes('WIN') || status.includes('LOSS')) {
                            if (!knownCompletedTrades.has(scopedTradeId)) {
                                if (!initialLoad && !isNewModeLoad && !knownCompletedTrades.has(contractOutcomeKey)) {
                                    const pnl = parseFloat(t.live_pnl !== undefined ? t.live_pnl : (t.pnl_dollars || t.pnl || 0));
                                    const isWin = status.includes('WIN') || pnl > 0;
                                    const assetStr = String(t.asset || t.ticker || 'Asset').toUpperCase().replace('KX', '').replace('15M', '');
                                    if (isWin) {
                                        window.iosNotify(`Trade Won! [${tradeMode}]`, `${assetStr} profit secured: +$${pnl.toFixed(2)}`, 'success');
                                    } else {
                                        window.iosNotify(`Trade Closed [${tradeMode}]`, `${assetStr} loss incurred: -$${Math.abs(pnl).toFixed(2)}`, 'error');
                                    }
                                }
                                knownCompletedTrades.add(scopedTradeId);
                                knownCompletedTrades.add(contractOutcomeKey);
                            }
                        }
                    });
                }
                _knownInitializedModes.add(currentMode);

                if (s.api_configured) {
                    document.getElementById('connection-status').innerText = "SECURE";
                    document.getElementById('connection-status').className = "text-[9px] uppercase font-bold text-kalshi-green tracking-wider";
                } else {
                    document.getElementById('connection-status').innerText = "NO API KEY";
                    document.getElementById('connection-status').className = "text-[9px] uppercase font-bold text-kalshi-red tracking-wider";
                }

                const hasValidBalance = s.balance_dollars !== undefined && s.balance_dollars !== null && !isNaN(Number(s.balance_dollars));
                const balNum = hasValidBalance ? Number(s.balance_dollars) : null;

                if(currentMode === "PAPER") {
                    if (balNum !== null) {
                        document.getElementById('val-balance').innerText = `$${balNum.toFixed(2)}`;
                        document.getElementById('val-balance').classList.remove('text-kalshi-red');
                    } else {
                        document.getElementById('val-balance').innerText = "--";
                        document.getElementById('val-balance').classList.remove('text-kalshi-red');
                    }
                } else {
                    if (balNum !== null) {
                        document.getElementById('val-balance').innerText = `$${balNum.toFixed(2)}`;
                        document.getElementById('val-balance').classList.remove('text-kalshi-red');
                    } else {
                        document.getElementById('val-balance').innerText = "Auth Error";
                        document.getElementById('val-balance').classList.add('text-kalshi-red');
                    }
                }

                const pnl = Number(s.total_pnl) || 0;
                const pnlEl = document.getElementById('val-pnl');
                pnlEl.innerText = `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`;
                pnlEl.className = `text-sm font-black tabular-nums ${pnl >= 0 ? 'text-kalshi-green' : 'text-kalshi-red'}`;
                
                document.getElementById('val-winrate').innerText = `${s.win_rate ?? 0}%`;

                // Update nav bar center Open Trade PnL (isolated strictly to active universe)
                if (typeof window.updateNavLivePnl === 'function') {
                    window.updateNavLivePnl(s);
                }

                // Update nav bar safely (never call .toFixed on null!)
                const navBal = document.getElementById('nav-balance');
                if (navBal) {
                    if (window.currentUniverse === 'INVESTMENTS') {
                        const invBal = window.cachedInvestmentsPortfolio?.portfolio_value ?? window.cachedInvestmentsPortfolio?.buying_power ?? s.investments_paper_balance ?? balNum;
                        navBal.textContent = invBal !== null && invBal !== undefined ? '$' + Number(invBal).toFixed(2) : '$0.00';
                    } else if (balNum !== null) {
                        navBal.textContent = '$' + balNum.toFixed(2);
                    } else {
                        navBal.textContent = '$0.00';
                    }
                }
                const navPnl = document.getElementById('nav-pnl');
                if (navPnl) {
                    const effectivePnl = (window.currentUniverse === 'INVESTMENTS' && window.cachedInvestmentsPortfolio?.day_pnl_dollars !== undefined)
                        ? Number(window.cachedInvestmentsPortfolio.day_pnl_dollars)
                        : pnl;
                    navPnl.textContent = (effectivePnl >= 0 ? '+' : '') + '$' + effectivePnl.toFixed(2);
                    navPnl.className = 'text-[11px] font-bold tabular-nums ' + (effectivePnl >= 0 ? 'text-emerald-400' : 'text-red-400');
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
                    if (s.profile_pic.startsWith('/static/') && window.API_BASE_URL) s.profile_pic = window.API_BASE_URL + s.profile_pic;
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
                    execMode.className = currentMode === 'LIVE' ? 'w-12 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest text-center bg-red-500/20 text-red-300 border border-red-500/40 leading-none shadow-sm' : 'w-12 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest text-center bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 leading-none shadow-sm';
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
                                ${!t.is_self ? `
                                <button id="btn-copy-settings-${t.id}" onclick="copyTraderSettings(${t.id}, '${t.username}')" class="px-2 py-0.5 mt-0.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded text-[8px] font-bold uppercase tracking-wider transition-colors border border-kalshi-border active:scale-95 cursor-pointer">
                                    Copy Settings
                                </button>
                                ` : ''}
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
            if (!confirm(`Are you sure you want to copy the trading settings from ${username}? This will overwrite your current configuration (your wager sizes will be preserved).`)) return;
            
            try {
                const userToken = localStorage.getItem('saas_token') || (typeof token !== 'undefined' ? token : '');
                const res = await fetch(`${window.API_BASE_URL||''}/api/auth/community/copy_settings/${targetId}`, {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + userToken }
                });
                let data = {}; try { data = await res.json(); } catch(e){} if(res.ok) {
                    if (data.result && data.result.copied_settings && typeof populateUserSettings === 'function') {
                        const mergedStats = Object.assign({}, window.lastDashboardStats || {}, data.result.copied_settings);
                        window.lastDashboardStats = mergedStats;
                        populateUserSettings(mergedStats, true);
                    }
                    alert(data.message || `Successfully copied settings from ${username}!`);
                    await loadDashboard(); // Refresh UI with new settings
                    if (window.lastDashboardStats && typeof populateUserSettings === 'function') {
                        populateUserSettings(window.lastDashboardStats, true);
                    }
                    if (typeof openCommunityModal === 'function' && !document.getElementById('communityModal')?.classList.contains('hidden')) {
                        openCommunityModal();
                    }
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
                    window.__isInvestmentTrade = function(t) {
                        if (!t) return false;
                        const a = String(t.asset || '').toUpperCase();
                        if (a === 'INVESTMENTS' || a === 'STOCK' || a === 'OPTION' || a === 'EQUITY') return true;
                        let meta = t.metadata;
                        if (typeof meta === 'string') {
                            try { meta = JSON.parse(meta); } catch(e) { meta = {}; }
                        }
                        return Boolean(meta && (
                            String(meta.universe || '').toUpperCase() === 'INVESTMENTS' ||
                            String(meta.vehicle || '').toUpperCase() === 'STOCK' ||
                            String(meta.vehicle || '').toUpperCase() === 'OPTION'
                        ));
                    };
                    window.__isSportTrade = function(t) {
                        if (!t) return false;
                        if (window.__isInvestmentTrade && window.__isInvestmentTrade(t)) return false;
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
                        const isSportsTicker = /^KX(NFL|MLB|NBA|NHL|NCAAF|NCAAB|WNBA|SOC|UFC|MMA|TEN|NPB|KBO|GAME|ATP|MVECROSSCATEGORY|MVE)/.test(tk) ||
                                               /^(NFL|MLB|NBA|NHL|NCAAF|NCAAB|WNBA|SOC|UFC|MMA|TEN)-/.test(tk) ||
                                               tk.startsWith('KALSHI-') ||
                                               tk.includes('KXMVECROSSCATEGORY') ||
                                               ['NFL','MLB','NBA','NCAAF','NCAAB','WNBA','NPB','KBO','NPB/KBO','NPB_KBO','NHL','SOC','UFC','TEN','MMA','SPORTS','MULTIVARIATE_COMBO'].includes(a);
                        const isSportsStyle = String(t.trading_style || '').toUpperCase().startsWith('SPORTS') || String(t.trading_style || '').toUpperCase().includes('COMBO') || String(t.trading_style || '').toUpperCase() === 'SPORTS_AI';
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

                        // Only the market text and the part of the reason before "|" can name a player:
                        // the rest is "AI Edge: Team (Conf: 70.0%, ...)", and "Conf: 70" used to be read
                        // as a player prop called "Conf" with a line of 70 ("70 Props").
                        const reasonHead = String(t.reason || '').split('|')[0];
                        const mPlayer = (strikeDetails + ' ' + reasonHead).match(/([A-Z][a-zA-Z\.\'\-\s]{2,35}?):\s*(\d+\+?|\d+\.\d+|\d+)\s*([a-zA-Z\s]*)/);
                        if (mPlayer) {
                            const pName = mPlayer[1].trim();
                            if (!/^(total|totals|over|under|spread|run line|puck line|moneyline|game|winner|match|conf|confidence|edge|ai edge|prob|probability)\b/i.test(pName)) {
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
                        const __inInvestments = window.currentUniverse === 'INVESTMENTS';
                        const isInvFn = window.__isInvestmentTrade || (() => false);
                        const activeMode = String(sTrades.trading_mode || currentMode || 'PAPER').toUpperCase();
                        let universeFiltered = (sTrades.recent_trades || [])
                            .filter(t => String(t.mode || 'PAPER').toUpperCase() === activeMode)
                            .filter(t => {
                                if (__inInvestments) return isInvFn(t);
                                if (__inSports) return window.__isSportTrade(t) && !isInvFn(t);
                                return !window.__isSportTrade(t) && !isInvFn(t);
                            });
                        const recent = universeFiltered.slice(0, 15);
                        const tradesKey = JSON.stringify(recent.map(t => [t.id, t.status, t.live_pnl, t.pnl_dollars, t.pnl, t.side, t.exit_reason])) + '_' + (__inSports ? 'S' : 'F') + '_' + activeMode;
                        if (window._lastTradesContainerKey === tradesKey) return;
                        window._lastTradesContainerKey = tradesKey;
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
                                if (styleStr.includes("GEMINI")) styleStr = "🧠 GEMINI REASONING";
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

                            // ── Compact trade card ───────────────────────────────────────────
                            // One line for what was bought, one for where/when, one for the money.
                            // (Replaces the old 5-row card: the badges repeated the same source three
                            // times, "OUT 0c" showed on open trades, and the breakdown banner duplicated
                            // the tap target.) Tapping the card still opens the full details modal.
                            const rxEsc = (v) => String(v == null ? '' : v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
                            const rxTk = String(t.ticker || '').toUpperCase();
                            const rxIsSport = window.__isSportTrade(t);
                            let rxTitle = '', rxMeta = '';
                            if (rxIsSport) {
                                const isComboTrade = (t.combo_id || String(t.trading_style || '').toUpperCase() === 'SPORTS_COMBO' || rxTk.includes('KXMVECROSSCATEGORY') || String(t.sport || '').toUpperCase() === 'MULTIVARIATE_COMBO');
                                const si = window.__getSportInfo(t) || {};
                                let seg = '';
                                if (/KXNHL1P/.test(rxTk)) seg = '1st Period';
                                else if (/KXNHL2P/.test(rxTk)) seg = '2nd Period';
                                else if (/KXNHL3P/.test(rxTk)) seg = '3rd Period';
                                else if (/KXMLBF5/.test(rxTk)) seg = 'First 5 Inn';
                                const pt = seg || si.propType || 'Moneyline';
                                const team = si.team || '';
                                if (isComboTrade) {
                                    rxTitle = t.predicted_team || t.team || 'Mega Parlay Combo';
                                    rxMeta = '⚡ COMBO · ' + (t.line || (t.prop_type || 'Kalshi Multivariate Parlay'));
                                } else if (pt === 'Player Prop') rxTitle = team + (si.line ? ' · ' + si.line : '');
                                else if (pt === 'Spread') rxTitle = team + ' ' + (si.spreadAmount || (si.line && si.line !== 'Spread' ? si.line : 'spread'));
                                else if (/total|o\/u/i.test(pt)) rxTitle = si.strikeDetails || (si.overUnderAmount ? 'O/U ' + si.overUnderAmount : si.line) || team;
                                else if (seg) rxTitle = team + ' wins ' + seg.toLowerCase();
                                else rxTitle = team + ' to win';
                                if (!isComboTrade) {
                                    const schedLabel = (window.__gameInfoLabel && typeof window.__gameInfoLabel === 'function') ? window.__gameInfoLabel(t) : '';
                                    rxMeta = (si.icon || '🏟️') + ' ' + (si.sport || 'SPORTS') + ' · ' + (/total|o\/u/i.test(pt) ? 'Total' : pt) + (schedLabel ? ' · ' + schedLabel : '');
                                }
                            } else {
                                let a = String(t.asset || '').toUpperCase();
                                if (!a || a === 'NONE') {
                                    a = ['BTC', 'ETH', 'GOLD', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'NDQ', 'SOL', 'DOGE'].find(x => rxTk.includes(x)) || 'BTC';
                                }
                                const icons = { BTC: '₿', ETH: 'Ξ', GOLD: '🪙', NDQ: '📈', SOL: '🚀', DOGE: '🐕' };
                                rxTitle = a + (hasValidStrike ? ' · strike ' + formattedStrike : '');
                                rxMeta = (icons[a] || '💵') + ' ' + a + (t.trading_style && !isManual ? ' · ' + String(t.trading_style).replace(/_/g, ' ').toLowerCase() : '');
                            }

                            const rxIsOpen = String(t.status || '').toUpperCase() === 'OPEN';
                            const rxQty = Number(t.count || t.size || 0) || 0;
                            const rxFmtCents = (val) => {
                                if (val == null || val === '' || !isFinite(parseFloat(val))) return null;
                                const c = parseFloat(val) * 100;
                                return (Math.abs(c - Math.round(c)) > 0.04) ? c.toFixed(1) : String(Math.round(c));
                            };
                            const rxIn = t.entry_price != null ? rxFmtCents(t.entry_price) : null;
                            const rxOutRaw = rxIsOpen ? (t.current_bid ?? t.current_price ?? t.cur_price) : t.exit_price;
                            const rxOut = (rxOutRaw != null && rxOutRaw !== '' && isFinite(parseFloat(rxOutRaw)) && (!rxIsOpen || parseFloat(rxOutRaw) > 0)) ? rxFmtCents(rxOutRaw) : null;
                            const rxCost = (t.entry_price != null && isFinite(parseFloat(t.entry_price))) ? (rxQty * parseFloat(t.entry_price)) : null;
                            let rxPos = rxQty ? rxQty + ' × ' + (rxIn != null ? rxIn + '¢' : '--') : (rxIn != null ? rxIn + '¢' : '');
                            if (rxCost != null) rxPos += ' = $' + rxCost.toFixed(2);
                            if (rxOut != null) rxPos += rxIsOpen ? ' · now ' + rxOut + '¢' : ' → ' + rxOut + '¢';
                            if (t.mve_leg_stats && t.mve_leg_stats.legs_total) {
                                const ls = t.mve_leg_stats;
                                rxPos += ` · ${ls.legs_won || 0}/${ls.legs_total} won`;
                            }

                            let rxConf = '';
                            const mConf = String(t.reason || '').match(/Conf:\s*([\d.]+)%/i);
                            if (mConf) rxConf = Math.round(parseFloat(mConf[1])) + '% conf';
                            else if (t.confidence != null) rxConf = Math.round(t.confidence) + '% conf';

                            const rxTags = [];
                            rxTags.push(mode === 'LIVE' ? '<span class="rx-tag rx-live">LIVE</span>' : '<span class="rx-tag rx-paper">PAPER</span>');
                            rxTags.push(isManual ? '<span class="rx-tag rx-manual">MANUAL</span>' : '<span class="rx-tag">AUTO</span>');
                            if (t.combo_id || String(t.trading_style || '').toUpperCase() === 'SPORTS_COMBO') rxTags.push('<span class="rx-tag bg-cyan-500/20 text-cyan-300 border border-cyan-500/35">COMBO</span>');
                            if (rxConf) rxTags.push('<span class="rx-tag">' + rxConf + '</span>');
                            if (isReversal) rxTags.push('<span class="rx-tag rx-warn">REVERSAL</span>');
                            if (exitReason && !['KALSHI_POSITION_RECONCILED', 'AI_SIGNAL', 'SETTLEMENT', 'MANUAL'].includes(exitReason) && !/AI_COPY|REVERSAL|SECOND_ENTRY|THIRD_ENTRY|STOP_LOSS_REENTRY/.test(exitReason)) {
                                rxTags.push('<span class="rx-tag rx-warn">' + rxEsc(exitReason.replace(/_/g, ' ')) + '</span>');
                            }
                            if (resultBadge) rxTags.push(resultBadge.replace(/class="[^"]*"/, 'class="rx-tag ' + (resultBadge.includes('CORRECT') ? 'rx-win' : 'rx-loss') + '"'));

                            let rxState = '', rxActions = '';
                            if (rxIsOpen) {
                                rxState = '<span class="rx-state rx-open">OPEN</span>';
                                if (!rxIsSport) rxActions += `<button type="button" class="rx-act" onclick="event.stopPropagation(); executeManualTrade('${t.side}', '${t.asset || ''}')">+ Add</button>`;
                                if (pnlVal > 0) rxActions += `<button type="button" class="rx-act rx-act-tp" onclick="event.stopPropagation(); takeProfitTrade('${t.id}')">TP</button>`;
                                rxActions += `<button type="button" class="rx-act rx-act-close" onclick="event.stopPropagation(); closeTrade('${t.id}')">Close</button>`;
                            } else if (isWin) rxState = '<span class="rx-state rx-win">WIN</span>';
                            else if (isLoss) rxState = '<span class="rx-state rx-loss">LOSS</span>';
                            else rxState = '<span class="rx-state">CLOSED</span>';
                            const rxWhen = entryTime + (!rxIsOpen && exitTime && exitTime !== '--' ? ' → ' + exitTime : '');
                            const rxEdgeCls = rxIsOpen ? 'rx-b-open' : isWin ? 'rx-b-win' : isLoss ? 'rx-b-loss' : 'rx-b-closed';

                            htmlString += `
                                <div onclick="openTradeDetailsModal('${tradeKey}')" class="rx-card ${rxEdgeCls}" title="Tap for full trade details">
                                    <div class="rx-row">
                                        <span class="rx-side ${dir === 'YES' ? 'rx-yes' : 'rx-no'}">${rxEsc(dir || '—')}</span>
                                        <span class="rx-title">${rxEsc(rxTitle)}</span>
                                        <span class="rx-pnl ${pnlColor}">${pnlStr}</span>
                                    </div>
                                    <div class="rx-row rx-sub">
                                        <span class="rx-meta">${rxEsc(rxMeta)}</span>
                                        <span class="rx-when">${rxEsc(rxWhen)}</span>
                                        ${rxActions ? `<span class="rx-acts">${rxActions}</span>` : rxState}
                                    </div>
                                    <div class="rx-row rx-sub">
                                        <span class="rx-pos">${rxEsc(rxPos)}</span>
                                        <span class="rx-tags">${rxTags.join('')}</span>
                                        <span class="rx-go">›</span>
                                    </div>
                                </div>
                            `;
                        });
                        container.innerHTML = htmlString;
                        if (window.__fetchGameInfo && typeof window.__fetchGameInfo === 'function') {
                            window.__fetchGameInfo(recent.filter(x => window.__isSportTrade && window.__isSportTrade(x)).map(x => x.ticker));
                        }
                    }
                };
                
                
                window.renderTradesContainer(s);
                if (typeof updateActivePositionHud === 'function') updateActivePositionHud(s);
                if (initialLoad) initialLoad = false;
            } catch (err) {
                console.error("loadDashboard error:", err);
            } finally {
                _loadDashboardInFlight = false;
            }
        }

        let chartInitialized = false;
        let lwChart, candleSeries, lineSeries, volumeSeries;
        let lastBidTs = 0;
        let isChartInitializing = false;
        // Poll Gemini Live Dossier for active asset
        async function updateGeminiLiveDossier() {
            try {
                const asset = window.currentAsset || 'BTC';
                const res = await fetch(`/api/engine/${asset}/gemini/live-dossier`);
                if (!res.ok) return;
                const data = await res.json();
                const card = document.getElementById('gemini-live-dossier-card');
                if (!card) return;
                if (window.currentTradingUniverse === 'INVESTMENTS' || window.currentTradingUniverse === 'SPORTS') {
                    card.style.display = 'none';
                    return;
                } else {
                    card.style.display = 'block';
                }
                if (data && data.has_decision) {
                    const dirEl = document.getElementById('gemini-dossier-dir-badge');
                    const confEl = document.getElementById('gemini-dossier-conf-badge');
                    const reasonEl = document.getElementById('gemini-dossier-reason');
                    const modelEl = document.getElementById('gemini-dossier-model');
                    const dir = String(data.direction || 'PASS').toUpperCase();
                    if (dirEl) {
                        dirEl.textContent = dir;
                        dirEl.className = dir === 'YES' ? 'text-[10px] font-black px-2 py-0.5 rounded-md bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : (dir === 'NO' ? 'text-[10px] font-black px-2 py-0.5 rounded-md bg-rose-500/20 text-rose-300 border border-rose-500/40' : 'text-[10px] font-black px-2 py-0.5 rounded-md bg-amber-500/20 text-amber-300 border border-amber-500/40');
                    }
                    if (confEl && data.confidence) confEl.textContent = `${Math.round(data.confidence)}% Conviction`;
                    if (reasonEl && data.reason) reasonEl.textContent = data.reason;
                    if (modelEl && data.model) modelEl.textContent = String(data.model).toUpperCase();
                    const updatedEl = document.getElementById('gemini-dossier-updated');
                    if (updatedEl && data.timestamp) {
                        const secAgo = Math.max(0, Math.round(Date.now() / 1000 - data.timestamp));
                        updatedEl.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse"></span> Evaluated ${secAgo}s ago`;
                    }
                }
            } catch(e) {
                // non-blocking
            }
        }
        setInterval(updateGeminiLiveDossier, 10000);
        setTimeout(updateGeminiLiveDossier, 2500);

        function init() {
            try {
                // Non-blocking background chart initialization
                if (!chartInitialized && document.getElementById('lw-chart-container') && !document.querySelector('#lw-chart-container canvas')) {
                    initChart().then(() => {
                        if (document.querySelector('#lw-chart-container canvas')) {
                            chartInitialized = true;
                        }
                    }).catch(e => console.warn('[Chart] initChart non-blocking error:', e));
                }

                // Data fetching runs without waiting on chart
                if (window.isTabActive) {
                    const now = Date.now();
                    if (!window._lastConfigLoadTs || (now - window._lastConfigLoadTs) > 10000) {
                        window._lastConfigLoadTs = now;
                        if (typeof loadConfig === 'function') loadConfig().catch(e => console.warn('[Config] error:', e));
                    }
                    if (typeof loadDashboard === 'function') loadDashboard().catch(e => console.warn('[Dashboard] error:', e));
                    if (typeof updateTimerBidsVisibility === 'function') updateTimerBidsVisibility();
                    if (typeof checkUpdateAnnouncement === 'function') checkUpdateAnnouncement();
                }
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
            if (panel) {
                if (window.currentUniverse === 'INVESTMENTS' || window.currentUniverse === 'SPORTS') {
                    panel.style.display = 'none';
                } else {
                    panel.style.display = showPanel ? 'block' : 'none';
                }
            }
            if (typeof updateTimerBidsVisibility === 'function') updateTimerBidsVisibility();
            if (typeof updatePositionScannerCloseButton === 'function') updatePositionScannerCloseButton();
        }

        // Apply immediately and on lifecycle events
        applyTradePanelPreference();
        
        // Immediate and unconditional initial dashboard data fetch
        if (typeof loadDashboard === 'function') {
            loadDashboard(true).catch(e => console.warn('[Init] loadDashboard(true) error:', e));
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                init();
                applyTradePanelPreference();
            });
        } else {
            init();
        }

        window.addEventListener('load', () => {
            init();
            applyTradePanelPreference();
            if(typeof checkUpdateAnnouncement === 'function') checkUpdateAnnouncement();
        });

        // Auto refresh
        setInterval(init, 1000);

        
        // Logout function
        
    
        // ── Real BTC 15m Chart + Live Kalshi Bids ──
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
                window.lwChart = lwChart;
                window.candleSeries = candleSeries;
                window.lineSeries = lineSeries;
                window.volumeSeries = volumeSeries;

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
            const __inInvestments = window.currentUniverse === 'INVESTMENTS';
            const activeMode = String(s.trading_mode || currentMode || 'PAPER').toUpperCase();
            const isSportTradeFn = window.__isSportTrade || (() => false);
            const isInvTradeFn = window.__isInvestmentTrade || (() => false);
            let openTrades = (s.recent_trades || [])
                .filter(t => String(t.status || '').toUpperCase() === 'OPEN')
                .filter(t => String(t.mode || 'PAPER').toUpperCase() === activeMode)
                .filter(t => {
                    if (__inInvestments) return isInvTradeFn(t);
                    if (__inSports) return isSportTradeFn(t) && !isInvTradeFn(t);
                    return !isSportTradeFn(t) && !isInvTradeFn(t);
                });

            if (__inInvestments && Array.isArray(window.cachedInvestmentsPositions) && window.cachedInvestmentsPositions.length > 0) {
                openTrades = window.cachedInvestmentsPositions;
            }

            const hasOpenTrades = openTrades.length > 0;
            const livePnlContainer = document.getElementById('nav-live-pnl-container');
            const livePnlVal = document.getElementById('nav-live-pnl-val');
            if (livePnlContainer && livePnlVal) {
                if (hasOpenTrades) {
                    livePnlContainer.classList.remove('hidden');
                    livePnlContainer.classList.add('flex');
                    let lPnl = openTrades.reduce((acc, t) => {
                        let p = (t.live_pnl !== undefined && t.live_pnl !== null) ? Number(t.live_pnl) : (t.pnl_dollars !== undefined ? Number(t.pnl_dollars) : 0);
                        return acc + (isNaN(p) ? 0 : p);
                    }, 0);
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

        window.updateFinancialAssetSelectorVisibility = function() {
            // When in SPORTS or INVESTMENTS universe, financial asset buttons are hidden by selectUniverse()
            if (window.currentUniverse === 'SPORTS' || window.currentUniverse === 'INVESTMENTS') return;

            const assetBtnMap = {
                'BTC': 'btn-asset-btc',
                'ETH': 'btn-asset-eth',
                'SOL': 'btn-asset-sol',
                'DOGE': 'btn-asset-doge'
            };

            const toggles = document.querySelectorAll('input.asset-toggle');
            let selectedAssets = [];

            if (toggles && toggles.length > 0) {
                toggles.forEach(t => {
                    const v = String(t.value || '').trim().toUpperCase();
                    if (t.checked && v && !selectedAssets.includes(v)) {
                        selectedAssets.push(v);
                    }
                });
            }

            // Fallback: if user settings are not yet populated into DOM or nothing checked, check window.lastDashboardStats
            if (selectedAssets.length === 0 && window.lastDashboardStats && window.lastDashboardStats.target_asset) {
                selectedAssets = String(window.lastDashboardStats.target_asset).split(',').map(a => a.trim().toUpperCase()).filter(Boolean);
            }

            // Default safe fallback if user has no assets selected at all
            if (selectedAssets.length === 0) {
                selectedAssets = ['BTC'];
            }

            // Show only enabled asset buttons, hide unselected ones
            Object.keys(assetBtnMap).forEach(sym => {
                const btn = document.getElementById(assetBtnMap[sym]);
                if (!btn) return;
                const isEnabled = selectedAssets.includes(sym);
                if (isEnabled) {
                    btn.style.display = '';
                    btn.classList.remove('hidden');
                } else {
                    btn.style.display = 'none';
                    btn.classList.add('hidden');
                }
            });

            // If the currently viewed asset is now disabled/hidden, auto-switch to the first enabled asset
            const curAsset = (window.currentAsset || 'BTC').toUpperCase();
            if (!selectedAssets.includes(curAsset)) {
                const fallbackAsset = selectedAssets[0] || 'BTC';
                if (typeof selectDashboardAsset === 'function') {
                    selectDashboardAsset(fallbackAsset);
                }
            }
        };

        window.updateSportsAssetSelectorVisibility = function() {
            // When in FINANCIAL or INVESTMENTS universe, sports asset buttons are hidden by selectUniverse()
            if (window.currentUniverse === 'FINANCIAL' || window.currentUniverse === 'INVESTMENTS') return;

            const sportsBtnMap = {
                'NFL': 'btn-asset-nfl',
                'NCAAF': 'btn-asset-ncaaf',
                'NBA': 'btn-asset-nba',
                'MLB': 'btn-asset-mlb',
                'NHL': 'btn-asset-nhl',
                'NPB/KBO': 'btn-asset-npb-kbo',
                'SOC': 'btn-asset-soc',
                'UFC': 'btn-asset-ufc',
                'TEN': 'btn-asset-ten'
            };

            const toggles = document.querySelectorAll('input.sports-league-toggle');
            let selectedLeagues = [];

            if (toggles && toggles.length > 0) {
                toggles.forEach(t => {
                    const v = String(t.value || '').trim().toUpperCase();
                    if (t.checked && v && !selectedLeagues.includes(v)) {
                        selectedLeagues.push(v);
                    }
                });
            }

            // Fallback: check window.lastDashboardStats if toggles aren't populated yet
            if (selectedLeagues.length === 0 && window.lastDashboardStats && window.lastDashboardStats.sports_active_leagues) {
                selectedLeagues = String(window.lastDashboardStats.sports_active_leagues).split(',').map(l => l.trim().toUpperCase()).filter(Boolean);
            }

            // Fallback: check per-sport config in localStorage if present
            if (selectedLeagues.length === 0) {
                try {
                    const savedCfg = JSON.parse(localStorage.getItem('st_sports_sport_cfg_v1') || '{}');
                    Object.keys(savedCfg).forEach(k => {
                        if (savedCfg[k] && savedCfg[k].on) {
                            const normK = k.toUpperCase();
                            if (!selectedLeagues.includes(normK)) selectedLeagues.push(normK);
                        }
                    });
                } catch(_) {}
            }

            // Default safe fallback if user has no sports leagues enabled at all: show all supported sports
            if (selectedLeagues.length === 0) {
                selectedLeagues = ['NFL', 'MLB', 'NBA', 'NHL', 'NCAAF', 'NPB/KBO', 'SOC', 'UFC', 'TEN'];
            }

            // Show only enabled sport buttons, hide disabled ones
            Object.keys(sportsBtnMap).forEach(league => {
                const btn = document.getElementById(sportsBtnMap[league]);
                if (!btn) return;
                const isEnabled = selectedLeagues.includes(league) ||
                    ((league === 'NPB/KBO' || league === 'NPB' || league === 'KBO') && (selectedLeagues.includes('NPB/KBO') || selectedLeagues.includes('NPB') || selectedLeagues.includes('KBO'))) ||
                    ((league === 'SOC' || league === 'SOCCER') && (selectedLeagues.includes('SOC') || selectedLeagues.includes('SOCCER'))) ||
                    ((league === 'TEN' || league === 'TENNIS') && (selectedLeagues.includes('TEN') || selectedLeagues.includes('TENNIS'))) ||
                    ((league === 'UFC' || league === 'MMA') && (selectedLeagues.includes('UFC') || selectedLeagues.includes('MMA')));

                if (isEnabled) {
                    btn.style.display = 'inline-flex';
                    btn.classList.remove('hidden');
                } else {
                    btn.style.display = 'none';
                    btn.classList.add('hidden');
                }
            });

            // If the currently filtered sport is now disabled/hidden, auto-switch to 'ALL' or first enabled sport
            const curFilter = String(window.sportsFilter || 'ALL').toUpperCase();
            if (curFilter !== 'ALL') {
                const isCurEnabled = selectedLeagues.some(l => {
                    if (curFilter === l) return true;
                    if ((curFilter === 'NPB/KBO' || curFilter === 'NPB' || curFilter === 'KBO') && (l === 'NPB/KBO' || l === 'NPB' || l === 'KBO')) return true;
                    if ((curFilter === 'SOC' || curFilter === 'SOCCER') && (l === 'SOC' || l === 'SOCCER')) return true;
                    if ((curFilter === 'TEN' || curFilter === 'TENNIS') && (l === 'TEN' || l === 'TENNIS')) return true;
                    if ((curFilter === 'UFC' || curFilter === 'MMA') && (l === 'UFC' || l === 'MMA')) return true;
                    return false;
                });
                if (!isCurEnabled) {
                    if (typeof filterSportsEvents === 'function') {
                        filterSportsEvents('ALL');
                    }
                }
            }
        };

        window.selectUniverse = function(universe) {
            window.currentUniverse = universe;
            try { localStorage.setItem('preferred_universe', universe); } catch(_) {}
            document.body.classList.toggle('universe-sports', universe === 'SPORTS');
            document.body.classList.toggle('universe-investments', universe === 'INVESTMENTS');
            const label = document.getElementById('market-universe-label');
            if (label) {
                if (universe === 'SPORTS') label.innerText = 'SPORTS';
                else if (universe === 'INVESTMENTS') label.innerText = 'INVESTMENTS';
                else label.innerText = 'CRYPTO';
            }

            const dd = document.getElementById('universe-dropdown');
            if (dd) {
                dd.classList.add('opacity-0', 'scale-95');
                setTimeout(() => {
                    dd.classList.add('hidden');
                }, 200);
            }
            
            const finAssets = document.querySelectorAll('.asset-btn');
            const sportsAssets = document.querySelectorAll('.asset-btn-sports');
            const invAssets = document.querySelectorAll('.asset-btn-investments');

            const lw = document.getElementById('lw-chart-container');
            const sbt = document.getElementById('stats-bar-target');
            const spl = document.getElementById('sports-event-list');
            const invView = document.getElementById('investments-universe-view');
            const slip = document.getElementById('sports-trade-slip-panel');
            const chartLoader = document.getElementById('chart-loader');
            const tradeExecPanel = document.getElementById('trade-execution-panel');
            const activeHud = document.getElementById('activePositionHud');
            const recentExecPanel = document.getElementById('recent-executions-panel');
            const invTicketPanel = document.getElementById('investments-order-ticket-panel');
            const invLedgerPanel = document.getElementById('investments-ledger-panel');

            if (universe === 'INVESTMENTS') {
                finAssets.forEach(el => { el.style.display = 'none'; el.classList.add('hidden'); });
                sportsAssets.forEach(el => { el.style.display = 'none'; el.classList.add('hidden'); });
                invAssets.forEach(el => { el.style.display = 'inline-flex'; el.classList.remove('hidden'); });

                if (lw) lw.style.display = 'none';
                if (sbt) sbt.style.display = 'none';
                if (chartLoader) chartLoader.style.display = 'none';
                if (spl) { spl.style.display = 'none'; spl.classList.add('hidden'); }
                if (slip) { slip.classList.add('hidden'); slip.classList.remove('flex'); }
                if (tradeExecPanel) { tradeExecPanel.style.display = 'none'; }
                if (activeHud) { activeHud.style.display = 'none'; activeHud.classList.add('hidden'); }
                if (recentExecPanel) { recentExecPanel.style.display = 'none'; recentExecPanel.classList.add('hidden'); }

                if (invView) { invView.style.display = 'block'; invView.classList.remove('hidden'); }
                if (invTicketPanel) { invTicketPanel.style.display = 'flex'; invTicketPanel.classList.remove('hidden'); invTicketPanel.classList.add('flex'); }
                if (invLedgerPanel) { invLedgerPanel.style.display = 'flex'; invLedgerPanel.classList.remove('hidden'); invLedgerPanel.classList.add('flex'); }

                if (typeof fetchInvestmentsFeed === 'function') {
                    fetchInvestmentsFeed();
                }
                if (typeof initInvestmentsTapeWebSocket === 'function') {
                    initInvestmentsTapeWebSocket();
                }
            } else if (universe === 'SPORTS') {
                invAssets.forEach(el => { el.style.display = 'none'; el.classList.add('hidden'); });
                finAssets.forEach(el => { el.style.display = 'none'; el.classList.add('hidden'); });
                if (typeof window.updateSportsAssetSelectorVisibility === 'function') {
                    window.updateSportsAssetSelectorVisibility();
                } else {
                    sportsAssets.forEach(el => { el.style.display = 'inline-flex'; el.classList.remove('hidden'); });
                }

                if (lw) lw.style.display = 'none';
                if (sbt) sbt.style.display = 'none';
                if (chartLoader) chartLoader.style.display = 'none';
                if (invView) { invView.style.display = 'none'; invView.classList.add('hidden'); }
                if (invTicketPanel) { invTicketPanel.style.display = 'none'; invTicketPanel.classList.add('hidden'); invTicketPanel.classList.remove('flex'); }
                if (invLedgerPanel) { invLedgerPanel.style.display = 'none'; invLedgerPanel.classList.add('hidden'); invLedgerPanel.classList.remove('flex'); }
                if (tradeExecPanel) { tradeExecPanel.style.display = 'none'; }
                if (activeHud) { activeHud.style.display = ''; activeHud.classList.remove('hidden'); }
                if (recentExecPanel) { recentExecPanel.style.display = ''; recentExecPanel.classList.remove('hidden'); }
                if (spl) { spl.style.display = 'block'; spl.classList.remove('hidden'); }
                
                if (typeof renderTradeSlip === 'function') renderTradeSlip();

                // Cache-first rendering: Render sports events immediately from cache to eliminate blanking/pulse loader
                if (window.__sportsEventsCache && window.__sportsEventsCache.length > 0 && typeof renderSportsEvents === 'function') {
                    renderSportsEvents();
                }

                if (window.activeSportsEventMarket) {
                    const found = Array.from(sportsAssets).find(b => b.innerText.includes(window.activeSportsEventMarket));
                    if (found) found.click();
                    else filterSportsEvents(window.sportsFilter || 'ALL');
                } else {
                    filterSportsEvents(window.sportsFilter || 'ALL');
                }
            } else {
                invAssets.forEach(el => { el.style.display = 'none'; el.classList.add('hidden'); });
                sportsAssets.forEach(el => { el.style.display = 'none'; el.classList.add('hidden'); });
                if (typeof window.updateFinancialAssetSelectorVisibility === 'function') {
                    window.updateFinancialAssetSelectorVisibility();
                } else {
                    finAssets.forEach(el => { el.style.display = ''; el.classList.remove('hidden'); });
                }

                if (invView) { invView.style.display = 'none'; invView.classList.add('hidden'); }
                if (invTicketPanel) { invTicketPanel.style.display = 'none'; invTicketPanel.classList.add('hidden'); invTicketPanel.classList.remove('flex'); }
                if (invLedgerPanel) { invLedgerPanel.style.display = 'none'; invLedgerPanel.classList.add('hidden'); invLedgerPanel.classList.remove('flex'); }
                if (spl) { spl.style.display = 'none'; spl.classList.add('hidden'); }
                if (slip) { slip.classList.add('hidden'); slip.classList.remove('flex'); }
                if (activeHud) { activeHud.style.display = ''; activeHud.classList.remove('hidden'); }
                if (recentExecPanel) { recentExecPanel.style.display = ''; recentExecPanel.classList.remove('hidden'); }
                if (typeof applyTradePanelPreference === 'function') applyTradePanelPreference();

                if (lw) lw.style.display = 'block';
                if (sbt) sbt.style.display = 'flex';

                // Immediate resize & fitContent in requestAnimationFrame to eliminate canvas dimensions collapse
                requestAnimationFrame(() => {
                    const chart = lwChart || window.lwChart;
                    if (chart && lw) {
                        const w = lw.clientWidth || lw.offsetWidth;
                        const h = lw.clientHeight || lw.offsetHeight;
                        if (w > 0 && h > 0) {
                            try { chart.applyOptions({ width: w, height: h }); } catch(_) {}
                        }
                        try {
                            if (chart.timeScale) chart.timeScale().fitContent();
                        } catch(_) {}
                    }
                });

                const activeTarget = window.currentAsset || 'BTC';
                if (typeof selectDashboardAsset === 'function') {
                    selectDashboardAsset(activeTarget, true);
                }
            }

            if (window.lastDashboardStats) {
                if (typeof window.renderTradesContainer === 'function') window.renderTradesContainer(window.lastDashboardStats);
                if (typeof updateActivePositionHud === 'function') updateActivePositionHud(window.lastDashboardStats);
                if (typeof window.updateNavLivePnl === 'function') window.updateNavLivePnl(window.lastDashboardStats);
            }
            // Tab switching is decoupled: purely client-side view selection, no implicit backend mutation
        };

        window.configuredTradingUniverse = 'CRYPTO';

        // Synchronize on/off universe toggle checkboxes across all settings drawers
        window.syncUniverseToggles = function(activeUniverses) {
            const hasCrypto = activeUniverses.has('CRYPTO') || activeUniverses.has('FINANCIAL');
            const hasSports = activeUniverses.has('SPORTS');
            const hasInv = activeUniverses.has('INVESTMENTS');

            document.querySelectorAll('#univ-toggle-crypto, #sports-univ-toggle-crypto, #inv-univ-toggle-crypto').forEach(el => { el.checked = hasCrypto; });
            document.querySelectorAll('#univ-toggle-sports, #sports-univ-toggle-sports, #inv-univ-toggle-sports').forEach(el => { el.checked = hasSports; });
            document.querySelectorAll('#univ-toggle-investments, #sports-univ-toggle-investments, #inv-univ-toggle-investments').forEach(el => { el.checked = hasInv; });

            const badges = document.querySelectorAll('#auto-universe-label-badge, #sports-auto-universe-label-badge, #inv-auto-universe-label-badge');
            badges.forEach(badge => {
                const count = (hasCrypto ? 1 : 0) + (hasSports ? 1 : 0) + (hasInv ? 1 : 0);
                if (count === 3) {
                    badge.innerText = 'ALL UNIVERSES';
                    badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-purple-500/15 text-purple-300 border border-purple-500/30';
                } else if (count === 2) {
                    if (hasCrypto && hasSports) {
                        badge.innerText = 'CRYPTO + SPORTS';
                        badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-indigo-500/15 text-indigo-300 border border-indigo-500/30';
                    } else if (hasCrypto && hasInv) {
                        badge.innerText = 'CRYPTO + STOCKS';
                        badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-blue-500/15 text-blue-300 border border-blue-500/30';
                    } else {
                        badge.innerText = 'SPORTS + STOCKS';
                        badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-teal-500/15 text-teal-300 border border-teal-500/30';
                    }
                } else if (count === 1) {
                    if (hasCrypto) {
                        badge.innerText = 'CRYPTO';
                        badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-cyan-500/15 text-cyan-400 border border-cyan-500/30';
                    } else if (hasSports) {
                        badge.innerText = 'SPORTS';
                        badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-amber-500/15 text-amber-400 border border-amber-500/30';
                    } else {
                        badge.innerText = 'INVESTMENTS';
                        badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-400 border border-emerald-500/30';
                    }
                } else {
                    badge.innerText = 'NONE ACTIVE';
                    badge.className = 'px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-red-500/15 text-red-400 border border-red-500/30';
                }
            });
        };

        window.setAutoTradingUniverse = function(univ, skipSave = false) {
            const raw = String(univ || 'CRYPTO').toUpperCase().trim();
            const activeSet = new Set();
            if (raw === 'ALL' || raw === 'BOTH') {
                if (raw === 'BOTH') {
                    activeSet.add('CRYPTO');
                    activeSet.add('SPORTS');
                } else {
                    activeSet.add('CRYPTO');
                    activeSet.add('SPORTS');
                    activeSet.add('INVESTMENTS');
                }
            } else if (raw.includes(',')) {
                raw.split(',').forEach(p => {
                    const clean = p.trim().toUpperCase();
                    if (clean === 'FINANCIAL' || clean === 'CRYPTO') activeSet.add('CRYPTO');
                    else if (clean === 'SPORTS') activeSet.add('SPORTS');
                    else if (clean === 'INVESTMENTS') activeSet.add('INVESTMENTS');
                });
            } else {
                if (raw === 'FINANCIAL' || raw === 'CRYPTO' || raw === 'CRYPTO/FOREX' || raw === 'CRYPTO_FOREX') {
                    activeSet.add('CRYPTO');
                } else if (raw === 'SPORTS') {
                    activeSet.add('SPORTS');
                } else if (raw === 'INVESTMENTS') {
                    activeSet.add('INVESTMENTS');
                }
            }

            // Fallback: at least one universe active if empty
            if (activeSet.size === 0) activeSet.add('CRYPTO');

            window.configuredTradingUniverse = activeSet.has('INVESTMENTS') && activeSet.has('SPORTS') && activeSet.has('CRYPTO') ? 'ALL'
                : (activeSet.has('CRYPTO') && activeSet.has('SPORTS') ? 'BOTH'
                : (activeSet.has('SPORTS') ? 'SPORTS' : (activeSet.has('INVESTMENTS') ? 'INVESTMENTS' : 'CRYPTO')));

            window.syncUniverseToggles(activeSet);

            if (!skipSave && typeof saveConfig === 'function') {
                saveConfig();
            }
        };

        window.onUniverseToggleChange = function(univType, isChecked) {
            const cryptoToggle = document.getElementById('univ-toggle-crypto') || document.getElementById('sports-univ-toggle-crypto') || document.getElementById('inv-univ-toggle-crypto');
            const sportsToggle = document.getElementById('univ-toggle-sports') || document.getElementById('sports-univ-toggle-sports') || document.getElementById('inv-univ-toggle-sports');
            const invToggle = document.getElementById('univ-toggle-investments') || document.getElementById('sports-univ-toggle-investments') || document.getElementById('inv-univ-toggle-investments');

            let hasCrypto = cryptoToggle ? cryptoToggle.checked : true;
            let hasSports = sportsToggle ? sportsToggle.checked : false;
            let hasInv = invToggle ? invToggle.checked : false;

            if (univType === 'crypto') hasCrypto = isChecked;
            if (univType === 'sports') hasSports = isChecked;
            if (univType === 'investments') hasInv = isChecked;

            // Ensure at least one universe remains on
            if (!hasCrypto && !hasSports && !hasInv) {
                if (univType === 'crypto') hasCrypto = true;
                else if (univType === 'sports') hasSports = true;
                else hasInv = true;
                if (typeof showToast === 'function') {
                    showToast("At least one trading universe must remain active", "warning");
                }
            }

            const activeSet = new Set();
            if (hasCrypto) activeSet.add('CRYPTO');
            if (hasSports) activeSet.add('SPORTS');
            if (hasInv) activeSet.add('INVESTMENTS');

            let newUniv = 'FINANCIAL';
            if (hasCrypto && hasSports && hasInv) {
                newUniv = 'ALL';
            } else if (hasCrypto && hasSports) {
                newUniv = 'BOTH';
            } else if (hasCrypto && hasInv) {
                newUniv = 'FINANCIAL,INVESTMENTS';
            } else if (hasSports && hasInv) {
                newUniv = 'SPORTS,INVESTMENTS';
            } else if (hasSports) {
                newUniv = 'SPORTS';
            } else if (hasInv) {
                newUniv = 'INVESTMENTS';
            } else {
                newUniv = 'FINANCIAL';
            }

            window.configuredTradingUniverse = newUniv;
            window.syncUniverseToggles(activeSet);

            if (typeof saveConfig === 'function') {
                saveConfig();
            }
        };

        const SPORT_ICONS = {
            'NFL': '🏈',
            'FOOTBALL': '🏈',
            'NCAAF': '🏈',
            'MLB': '⚾',
            'BASEBALL': '⚾',
            'NBA': '🏀',
            'NCAAB': '🏀',
            'WNBA': '🏀',
            'NHL': '🏒',
            'HOCKEY': '🏒',
            'NPB': '⚾',
            'KBO': '⚾',
            'NPB/KBO': '⚾',
            'NPB_KBO': '⚾',
            'SOC': '⚽',
            'SOCCER': '⚽',
            'EPL': '⚽',
            'MLS': '⚽',
            'UEFA': '⚽',
            'WC': '⚽',
            'UFC': '🥊',
            'MMA': '🥊',
            'TEN': '🎾',
            'TENNIS': '🎾',
            'ATP': '🎾',
            'WTA': '🎾'
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
            if (!evt || typeof evt !== 'object') return false;
            if (!f || f === 'ALL') return true;
            const filterNorm = f.toUpperCase();
            const eSport = String(evt.sport || '').toUpperCase();
            const eLeague = String(evt.league || evt.metadata?.league || '').toUpperCase();
            const eSeries = String(evt.series_ticker || evt.metadata?.series_ticker || '').toUpperCase();
            const eTicker = String(evt.event_ticker || evt.ticker || evt.metadata?.event_ticker || evt.metadata?.market_ticker || '').toUpperCase();

            if (filterNorm === 'NPB/KBO' || filterNorm === 'NPB_KBO' || filterNorm === 'NPB-KBO' || filterNorm === 'NPB' || filterNorm === 'KBO') {
                return eSport.includes('NPB') || eSport.includes('KBO') ||
                       eLeague.includes('NPB') || eLeague.includes('KBO') ||
                       eSeries.includes('NPB') || eSeries.includes('KBO') ||
                       /^KX(NPB|KBO)/.test(eTicker);
            }
            if (filterNorm === 'SOC' || filterNorm === 'SOCCER') {
                return eSport === 'SOC' || eSport === 'SOCCER' || eSport === 'EPL' || eSport === 'MLS' ||
                       eLeague === 'SOC' || eLeague === 'SOCCER' || eLeague === 'EPL' || eLeague === 'MLS' || eLeague === 'UEFA' || eLeague === 'WC' ||
                       eSeries.includes('EPL') || eSeries.includes('MLS') || eSeries.includes('UEFA') || eSeries.includes('UCL') || eSeries.includes('UEL') || eSeries.includes('UECL') || eSeries.includes('WC') || eSeries.includes('SOC') ||
                       /^KX(EPL|MLS|UEFA|UCL|UEL|UECL|WC|SOC|LALIGA|SERIEA|BUNDES|LIGUE|LIGA|EFL|USL|CONMEBOL|ARG|DIMAYOR|BRAS|ERED|SAUDI|SCOT)/.test(eTicker);
            }
            if (filterNorm === 'TEN' || filterNorm === 'TENNIS') {
                return eSport === 'TEN' || eSport === 'TENNIS' || eSport === 'ATP' || eSport === 'WTA' ||
                       eLeague === 'TEN' || eLeague === 'TENNIS' || eLeague === 'ATP' || eLeague === 'WTA' ||
                       eSeries.includes('ATP') || eSeries.includes('WTA') || eSeries.includes('TEN') ||
                       /^KX(ATP|WTA|TEN)/.test(eTicker);
            }
            if (filterNorm === 'UFC' || filterNorm === 'MMA') {
                return eSport === 'UFC' || eSport === 'MMA' ||
                       eLeague === 'UFC' || eLeague === 'MMA' ||
                       eSeries.includes('UFC') || eSeries.includes('MMA') ||
                       /^KXUFC/.test(eTicker);
            }
            if (filterNorm === 'MLB' || filterNorm === 'BASEBALL') {
                return eSport === 'MLB' || eSport === 'BASEBALL' ||
                       eLeague === 'MLB' || eLeague === 'BASEBALL' ||
                       eSeries.includes('MLB') || /^KXMLB/.test(eTicker);
            }
            if (filterNorm === 'NFL' || filterNorm === 'FOOTBALL') {
                return eSport === 'NFL' || eSport === 'FOOTBALL' ||
                       eLeague === 'NFL' || eLeague === 'FOOTBALL' ||
                       eSeries.includes('NFL') || /^KXNFL/.test(eTicker);
            }
            if (filterNorm === 'NBA' || filterNorm === 'BASKETBALL') {
                return eSport === 'NBA' || eLeague === 'NBA' || /^KXNBA/.test(eSeries) || /^KXNBA/.test(eTicker);
            }
            if (filterNorm === 'NCAAF' || filterNorm === 'CFB') {
                return eSport === 'NCAAF' || eSport === 'CFB' || eLeague === 'NCAAF' || eLeague === 'CFB' ||
                       /^KXNCAAF/.test(eSeries) || /^KXNCAAF/.test(eTicker);
            }
            if (filterNorm === 'NHL' || filterNorm === 'HOCKEY') {
                return eSport === 'NHL' || eSport === 'HOCKEY' ||
                       eLeague === 'NHL' || eLeague === 'HOCKEY' ||
                       eSeries.includes('NHL') || /^KXNHL/.test(eTicker);
            }
            return eSport === filterNorm || eLeague === filterNorm || eSeries.includes(filterNorm) || eTicker.includes(filterNorm);
        }

        window.__sportsLoading = false;
        window.__sportsReqId = 0;

        
        
        
        function expandMatchupNames(str, sport) {
            if (!str || typeof str !== 'string') return str;
            var sp = String(sport || '').toUpperCase();
            var map = {
                // MLB
                "ARI": "Arizona Diamondbacks", "ATL": "Atlanta Braves", "BAL": "Baltimore Orioles", "BOS": "Boston Red Sox",
                "CHC": "Chicago Cubs", "CWS": "Chicago White Sox", "CHW": "Chicago White Sox", "CIN": "Cincinnati Reds",
                "CLE": "Cleveland Guardians", "COL": (sp === "NHL") ? "Colorado Avalanche" : "Colorado Rockies",
                "DET": "Detroit Tigers", "HOU": "Houston Astros", "KC": "Kansas City Royals", "KCR": "Kansas City Royals",
                "LAA": "Los Angeles Angels", "LAD": "Los Angeles Dodgers", "MIA": "Miami Marlins", "MIL": "Milwaukee Brewers",
                "MIN": "Minnesota Twins", "NYM": "New York Mets", "NYY": "New York Yankees", "OAK": "Oakland Athletics",
                "PHI": "Philadelphia Phillies", "PIT": "Pittsburgh Pirates", "SD": "San Diego Padres", "SDP": "San Diego Padres",
                "SF": "San Francisco Giants", "SFG": "San Francisco Giants", "SEA": "Seattle Mariners", "STL": "St. Louis Cardinals",
                "TB": "Tampa Bay Rays", "TBR": "Tampa Bay Rays", "TEX": "Texas Rangers", "TOR": "Toronto Blue Jays",
                "WSH": "Washington Nationals", "WAS": "Washington Nationals",
                // NFL
                "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears", "DAL": "Dallas Cowboys",
                "DEN": "Denver Broncos", "GB": "Green Bay Packers", "GBP": "Green Bay Packers", "IND": "Indianapolis Colts",
                "JAC": "Jacksonville Jaguars", "JAX": "Jacksonville Jaguars", "LV": "Las Vegas Raiders", "LVR": "Las Vegas Raiders",
                "LAC": "Los Angeles Chargers", "LAR": "Los Angeles Rams", "NE": "New England Patriots", "NEP": "New England Patriots",
                "NO": "New Orleans Saints", "NOS": "New Orleans Saints", "NYG": "New York Giants", "NYJ": "New York Jets",
                "TEN": "Tennessee Titans",
                // NBA
                "BKN": "Brooklyn Nets", "CHA": "Charlotte Hornets", "GSW": "Golden State Warriors", "MEM": "Memphis Grizzlies",
                "NOP": "New Orleans Pelicans", "OKC": "Oklahoma City Thunder", "ORL": "Orlando Magic", "PHX": "Phoenix Suns",
                "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs", "UTA": "Utah Jazz",
                // NHL
                "ANA": "Anaheim Ducks", "CGY": "Calgary Flames", "CBJ": "Columbus Blue Jackets", "EDM": "Edmonton Oilers",
                "FLA": "Florida Panthers", "LAK": "Los Angeles Kings", "MTL": "Montreal Canadiens", "NSH": "Nashville Predators",
                "NJD": "New Jersey Devils", "NYI": "New York Islanders", "NYR": "New York Rangers", "OTT": "Ottawa Senators",
                "SJS": "San Jose Sharks", "TBL": "Tampa Bay Lightning", "VAN": "Vancouver Canucks", "VGK": "Vegas Golden Knights",
                "WPG": "Winnipeg Jets",
                // UCL / Soccer
                "MCI": "Manchester City", "MUN": "Manchester United", "RMA": "Real Madrid", "BAR": "Barcelona", "FCB": "Bayern Munich",
                "BVB": "Borussia Dortmund", "ATM": "Atletico Madrid", "PSG": "Paris Saint-Germain", "INT": "Inter Milan", "ACM": "AC Milan"
            };
            return str.replace(/\b([A-Z]{2,4})\b/g, function(match, code) {
                return map[code] || match;
            });
        }

        function renderSportsEvents() {
            const container = document.getElementById('sports-events-container');
            if (!container) return;
            const all = window.__sportsEventsCache || [];
            const f = window.sportsFilter || 'ALL';
            const includeLive = document.getElementById('sports-include-live-toggle') ? document.getElementById('sports-include-live-toggle').checked : false;
            const nowSec = Date.now() / 1000;
            const currentStrat = window.currentSportsStrategy || 'STANDARD';

            const filterEvents = (enforceUserSettings, enforceStrategy, enforceNoLive) => {
                return all.filter(e => {
                    if (!isSportMatch(e, f)) return false;
                    if (e.market_type === 'Futures' || e.prop_type === 'Futures') return false; // Exclude Futures from default list
                    if (/KX(?:NFL|NBA|MLB|NHL)WINS|TOTAL WINS|WINS-\d/i.test(String(e.event_ticker || e.ticker || '') + ' ' + String(e.title || ''))) return false; // season win totals
                    if (enforceUserSettings && f === 'ALL' && typeof window.sportsEventAllowed === 'function' && !window.sportsEventAllowed(e)) return false; // Sports & Markets settings

                    // Filter by active sports betting strategy (if specific strategy selected)
                    if (enforceStrategy && currentStrat !== 'ALL_ACTIVE' && f === 'ALL') {
                        const eStrat = e.strategy_tag || 'STANDARD';
                        const eConf = parseFloat(e.confidence_pct || 0);
                        if (currentStrat === 'POWER_COMBO' || currentStrat === 'ULTRA_COMBO' || currentStrat === 'MEGA_PARLAY') {
                            if (eStrat !== 'FLOOR_TOTALS' && eStrat !== 'MILESTONE_PROPS' && eConf < 60.0) return false;
                        } else if (currentStrat === 'FLOOR_TOTALS') {
                            if (eStrat !== 'FLOOR_TOTALS') return false;
                        } else if (currentStrat === 'MILESTONE_PROPS') {
                            if (eStrat !== 'MILESTONE_PROPS') return false;
                        }
                    }
                    // Hide finished games: explicit final status, or started longer ago than the sport's usual length.
                    {
                        const st = String(e.status || (e.metadata || {}).status || '').toLowerCase();
                        if (e.is_final || /^(final|completed|closed|ended|post|finished)/.test(st)) return false;
                        const se = parseFloat(e.start_epoch) || 0;
                        if (se > 0) {
                            const sp = String(e.sport || e.league || '').toUpperCase();
                            const capH = /TEN|TENNIS/.test(sp) ? 6 : /MLB|NPB|KBO/.test(sp) ? 5.5 : /NFL|NCAAF/.test(sp) ? 4.5 : /NHL|NBA/.test(sp) ? 3.5 : /SOC|EPL|MLS/.test(sp) ? 3.2 : /UFC/.test(sp) ? 9 : 5;
                            if (nowSec - se > capH * 3600) return false;
                        }
                    }
                    const startEpoch = parseFloat(e.start_epoch) || 0;
                    const isLive = startEpoch > 0 && startEpoch < nowSec && !/KX(?:NFL|NBA|MLB|NHL)WINS|TOTAL WINS|WINS-\d/i.test(String(e.event_ticker||e.ticker||'')+' '+String(e.title||''));
                    if (enforceNoLive && isLive && !includeLive) return false;
                    if ((f === 'SOC' || String(e.sport).toUpperCase() === 'SOCCER') && e.is_today === false && enforceStrategy) return false;
                    return true;
                });
            };

            let list = filterEvents(true, true, true);
            if (list.length === 0 && all.length > 0) list = filterEvents(true, false, true);
            if (list.length === 0 && all.length > 0) list = filterEvents(false, false, true);
            if (list.length === 0 && all.length > 0) list = filterEvents(false, false, false);

            const label = f === 'ALL' ? 'any sport' : f;

            if (list.length === 0) {
                if (window.__sportsLoading) {
                    container.innerHTML = '<div class="col-span-full text-center text-cyan-400 text-xs py-6 animate-pulse">⚡ Loading ' + label + ' AI picks...</div>';
                } else {
                    container.innerHTML = '<div class="col-span-full text-center text-gray-500 text-xs py-6">No active AI picks for ' + label + ' right now.</div>';
                }
                return;
            }

            // ── helpers ──────────────────────────────────────────────────────
            const esc = (v) => String(v == null ? '' : v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
            const jsq = (v) => String(v == null ? '' : v).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/\n/g, ' ');
            const GENERIC = new Set(['the', 'and', 'city', 'team', 'club', 'vs', 'game', 'wins', 'win', 'will']);
            const tokens = (s) => new Set(String(s || '').toLowerCase().match(/[a-z0-9]+/g)?.filter(w => w.length >= 3 && !GENERIC.has(w)) || []);
            const cents = (m, side) => {
                if (!m) return null;
                const d = m[side + '_ask_dollars'];
                if (d != null && d !== '') { const v = Math.round(parseFloat(d) * 100); return isFinite(v) ? v : null; }
                const c = m[side + '_ask'];
                if (c != null && c !== '') {
                    let v = parseFloat(c);
                    if (!isFinite(v)) return null;
                    // The market cache sends dollars (0.37), older feeds sent cents (37).
                    if (v > 0 && (v < 1 || (/\./.test(String(c)) && v <= 1))) v = v * 100;
                    return Math.round(v);
                }
                return null;
            };
            const tradable = (c) => c != null && c > 0 && c < 100;
            const mktName = (m) => String(m.yes_sub_title || m.subtitle || (m.ticker || '').split('-').pop() || 'YES').replace(/^yes\s*/i, '').trim();
            const teamMatches = (team, m) => {
                if (!team || !m) return false;
                const t = String(team).toLowerCase();
                const sub = mktName(m).toLowerCase();
                if (sub && sub.length >= 3 && (t.includes(sub) || sub.includes(t))) return true;
                const a = tokens(team), b = tokens(sub + ' ' + (m.title || ''));
                for (const w of a) if (b.has(w)) return true;
                return false;
            };
            // NPB/KBO start time: the Kalshi ticker carries the date and start time in US Eastern
            // (KXKBOGAME-26OCT100400SSGKIA = Oct 10, 4:00 AM ET), matching Kalshi's milestone start_date.
            const MON3 = { JAN: 0, FEB: 1, MAR: 2, APR: 3, MAY: 4, JUN: 5, JUL: 6, AUG: 7, SEP: 8, OCT: 9, NOV: 10, DEC: 11 };
            const etWallToEpoch = (y, mo, d, hh, mm) => {
                const target = Date.UTC(y, mo, d, hh, mm) / 1000;
                let guess = target + 4 * 3600;
                try {
                    const fmt = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
                    for (let i = 0; i < 2; i++) {
                        const parts = fmt.formatToParts(new Date(guess * 1000));
                        const g = (k) => +((parts.find(p => p.type === k) || {}).value || 0);
                        const wall = Date.UTC(g('year'), g('month') - 1, g('day'), g('hour') % 24, g('minute')) / 1000;
                        guess += target - wall;
                    }
                } catch (e) { /* keep EDT guess */ }
                return guess;
            };
            // Same format for MLB (KXMLBGAME-26OCT102000CWSCLE = Oct 10, 8:00 PM ET) and its prop series.
            const asianBaseballStart = (evt) => {
                const tk = String(evt.event_ticker || evt.ticker || '');
                const m = /^KX(?:NPB|KBO|MLB)[A-Z0-9]*-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})(?=[A-Z])/.exec(tk);
                if (m && MON3[m[2]] != null && +m[4] < 24 && +m[5] < 60) return etWallToEpoch(2000 + (+m[1]), MON3[m[2]], +m[3], +m[4], +m[5]);
                return 0;
            };
            const fmtStartEpoch = (sec, approx) => {
                const d = new Date(sec * 1000); if (isNaN(d)) return '';
                const now = new Date();
                const sameDay = d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
                const t = (approx ? '~' : '') + d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
                return (sameDay ? 'Today' : d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })) + ' · ' + t;
            };
            // NFL start time: the ticker has the date only (KXNFLGAME-26OCT11CINMIA). Kalshi schedules each
            // NFL game market to close 48 h after kickoff and to expire 3 h after it, so either gives the
            // kickoff. Use it only when both agree and the Eastern date matches the ticker's date;
            // otherwise show just the ticker's date (never a guessed time).
            const etDateKey = (sec) => {
                try { return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(sec * 1000)); } catch (e) { return ''; }
            };
            // Kalshi's start-time offsets, checked against its schedule: NFL, NHL and soccer games expire
            // 3 h and close 48 h after the start; UFC bouts expire 5 h and close 14 days after the bout's
            // estimated slot (shown with "~", since fight times depend on how earlier bouts go).
            const kalshiTimeRule = (evt, tk) => {
                if (/^KX(?:NFL|NHL)[A-Z0-9]*-/.test(tk)) return { exp: 3, close: 48 };
                if (/^KXUFC[A-Z0-9]*-/.test(tk)) return { exp: 5, close: 336, approx: true };
                if (/^(SOC|SOCCER|EPL|MLS)$/i.test(String(evt.sport || '')) || /^KX(?:EPL|MLS)GAME-/.test(tk)) return { exp: 3, close: 48 };
                return null;
            };
            // Start epoch from Kalshi's market times (0 if the check fails). Used for the label and the sort.
            const ruleStartEpoch = (evt) => {
                const tk = String(evt.event_ticker || evt.ticker || '');
                const rule = kalshiTimeRule(evt, tk);
                if (!rule) return 0;
                const m = /^KX[A-Z0-9]*-(\d{2})([A-Z]{3})(\d{2})(?![0-9])/.exec(tk);
                if (!m || MON3[m[2]] == null) return 0;
                const tickerKey = (2000 + (+m[1])) + '-' + String(MON3[m[2]] + 1).padStart(2, '0') + '-' + String(+m[3]).padStart(2, '0');
                const mk = (evt.markets || []).find(x => x && (x.close_time || x.expected_expiration_time)) || {};
                const fromClose = mk.close_time ? Date.parse(mk.close_time) / 1000 - rule.close * 3600 : NaN;
                const fromExp = mk.expected_expiration_time ? Date.parse(mk.expected_expiration_time) / 1000 - rule.exp * 3600 : NaN;
                return (isFinite(fromClose) && isFinite(fromExp) && Math.abs(fromClose - fromExp) < 60 && etDateKey(fromClose) === tickerKey) ? fromClose : 0;
            };
            const nflWhen = (evt) => {
                const tk = String(evt.event_ticker || evt.ticker || '');
                const rule = kalshiTimeRule(evt, tk);
                if (!rule) return '';
                const m = /^KX[A-Z0-9]*-(\d{2})([A-Z]{3})(\d{2})(?![0-9])/.exec(tk);
                if (!m || MON3[m[2]] == null) return '';
                const y = 2000 + (+m[1]), mo = MON3[m[2]], d = +m[3];
                const tickerKey = y + '-' + String(mo + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0');
                const dateOnly = new Date(y, mo, d).toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
                const sec = ruleStartEpoch(evt);
                return sec > 0 ? fmtStartEpoch(sec, rule.approx) : dateOnly;
            };
            // Tennis: Kalshi's market times don't track the order of play, so use the scheduled start
            // that comes with the AI pick (ESPN), but only if it's within a few days of the ticker date.
            const tennisWhen = (evt, md) => {
                const sec = tennisStartEpoch(evt, md);
                return sec > 0 ? fmtStartEpoch(sec) : '';
            };
            const tennisStartEpoch = (evt, md) => {
                md = md || {};
                const tk = String(evt.event_ticker || evt.ticker || '');
                const m = /^KX(?:ATP|WTA)MATCH-(\d{2})([A-Z]{3})(\d{2})/.exec(tk);
                if (!m || MON3[m[2]] == null) return 0;
                const tkDay = Date.UTC(2000 + (+m[1]), MON3[m[2]], +m[3]) / 1000;

                // Prefer verified Kalshi start_epoch if available and within window
                if (evt.start_epoch && isFinite(evt.start_epoch) && evt.start_epoch > 0) {
                    if (evt.start_epoch >= tkDay - 86400 && evt.start_epoch <= tkDay + 3 * 86400) {
                        return evt.start_epoch;
                    }
                }

                const am = (evt.ai_prediction && evt.ai_prediction.metadata) || {};
                const raw = String(am.start_label || am.game_time || md.start_label || md.game_time || evt.game_time || '');
                if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(raw)) return 0;
                const sec = Date.parse(/Z|[+-]\d{2}:?\d{2}$/.test(raw) ? raw : raw + 'Z') / 1000;
                if (!isFinite(sec) || sec < tkDay - 86400 || sec > tkDay + 3 * 86400) return 0;
                return sec;
            };
            const fmtWhen = (evt, md, isLive) => {
                if (isLive) return '<span class="spc-live"><i></i>LIVE</span>';
                const abStart = asianBaseballStart(evt);
                if (abStart > 0) return esc(fmtStartEpoch(abStart));
                const nfl = nflWhen(evt);
                if (nfl) return esc(nfl);
                const ten = tennisWhen(evt, md);
                if (ten) return esc(ten);
                let when = evt.game_time || md.game_time || md.start_label || evt.start_time || '';
                when = String(when).replace(/\s*@\s*/, ' · ').trim();
                if (evt.is_today && when) when = 'Today · ' + when.replace(/^[A-Z][a-z]{2}\s+\d{1,2}\s*·\s*/, '');
                return esc(when || 'Upcoming');
            };
            // Same start label as the card, for the "Market & Prediction Intel" popup.
            window.__sportsStartLabel = (evt) => {
                try {
                    if (!evt) return '';
                    const ab = asianBaseballStart(evt);
                    if (ab > 0) return fmtStartEpoch(ab);
                    return nflWhen(evt) || tennisWhen(evt, evt.metadata || {}) || '';
                } catch (e) { return ''; }
            };

            // ── build view models ────────────────────────────────────────────
            const cards = list.map(evt => {
                const md = evt.metadata || {};
                const sport = String(evt.sport || '').toUpperCase();
                const league = String(evt.league || md.league || sport).toUpperCase();
                const icon = SPORT_ICONS[sport] || SPORT_ICONS[league] || '🏟️';
                const startEpoch = parseFloat(evt.start_epoch) || 0;
                const isLive = startEpoch > 0 && startEpoch < nowSec && !/KX(?:NFL|NBA|MLB|NHL)WINS|TOTAL WINS|WINS-\d/i.test(String(evt.event_ticker||evt.ticker||'')+' '+String(evt.title||''));

                const rawMatchup = evt.matchup || md.matchup || evt.opponent || md.name || 'Sports Matchup';
                let matchup = expandMatchupNames(String(rawMatchup).replace(/:\s*(Spread|Total\s*Runs?|Totals?|Game|Moneyline).*$/i, '').trim() || rawMatchup, sport || league);

                let propType = evt.prop_type || md.prop_type || evt.market_type || md.market_type_label || '';
                if (!propType || /vs/i.test(propType) || propType.length > 20) {
                    const tk = String(evt.event_ticker || '').toUpperCase();
                    if (['KXNHLGOAL', 'KXNHLSHOT', 'KXMLBHRR', 'KXMLBHIT', 'KXMLBHR', 'KXMLBKS', 'KXNFLTD', 'PROP', 'GOAL', 'SHOT', 'HRR'].some(k => tk.includes(k))) propType = 'Player Prop';
                    else if (tk.includes('SPREAD')) propType = 'Spread';
                    else if (tk.includes('TOTAL')) propType = 'Total (O/U)';
                    else propType = 'Moneyline';
                }
                const markets = Array.isArray(evt.markets) ? evt.markets.filter(m => m && m.ticker) : [];
                const strike = evt.strike_details || md.strike_details || '';

                // Period / innings / half markets and futures are not game moneylines. The server
                // used to label them "Moneyline" and attach the full-game AI pick, so a 1st-period
                // card read "AI: Anaheim 58% to win". Detect them (also from the ticker, so this
                // works before the server is restarted) and show the game pick only as a lean.
                const tkU = [evt.event_ticker, evt.ticker, evt.series_ticker, md.series_ticker].map(x => String(x || '').toUpperCase()).join(' ');
                const segText = [strike, evt.title, evt.sub_title, markets[0] && markets[0].title, markets[0] && markets[0].yes_sub_title].map(x => String(x || '')).join(' ').toLowerCase();
                let segment = evt.segment || md.segment || '';
                if (!segment) {
                    if (/KXNHL1P/.test(tkU) || /\b(1st|first) period\b/.test(segText)) segment = '1st Period';
                    else if (/KXNHL2P/.test(tkU) || /\b(2nd|second) period\b/.test(segText)) segment = '2nd Period';
                    else if (/KXNHL3P/.test(tkU) || /\b(3rd|third) period\b/.test(segText)) segment = '3rd Period';
                    else if (/KXMLBF5/.test(tkU) || /\bfirst (5|five) innings?\b/.test(segText)) segment = 'First 5 Inn';
                    else if (/\b(1st|first) half\b/.test(segText)) segment = '1st Half';
                    else if (/\b(2nd|second) half\b/.test(segText)) segment = '2nd Half';
                    else if (/\b(1st|first) quarter\b/.test(segText)) segment = '1st Quarter';
                }
                if (segment && (propType === 'Moneyline' || propType === 'Period')) propType = 'Period';
                const looksFutures = /(^|\s)(KXNFLWINS|KXWC)(-|\s|$)/.test(tkU) || (propType === 'Moneyline' && markets.length > 3);
                if (propType === 'Futures' || looksFutures && propType === 'Moneyline') propType = 'Futures';
                const isPeriod = propType === 'Period';
                const isFutures = propType === 'Futures';

                const isML = propType === 'Moneyline';
                const isProp = propType === 'Player Prop';
                const isSeason = /KX(?:NFL|NBA|MLB|NHL)WINS|TOTAL WINS|WINS-\d/i.test(tkU + ' ' + String(evt.title || ''));
                const isTotal = /total|o\/u/i.test(propType) && !isSeason;
                const line = evt.line || md.line || '';
                const spreadAmount = evt.spread_amount || md.spread_amount || '';
                const ouAmount = evt.over_under_amount || md.over_under_amount || '';

                let conf = parseFloat(evt.confidence_pct) || 0;
                const srvEdge = parseFloat(evt.edge_pct) || 0;
                const rawPick = evt.ai_pick || (evt.has_ai_prediction ? evt.predicted_team : '') || '';
                const rawHasPick = !!(conf > 0 && rawPick && !/ vs /i.test(rawPick) && rawPick.toLowerCase() !== matchup.toLowerCase()) && !(window.sportsGameLevelPickOnProp && window.sportsGameLevelPickOnProp(evt, null));
                // A full-game pick on a period / futures card is only a lean, never "the" pick.
                const leanTeam = evt.ai_lean_team || ((isPeriod || isFutures) && rawHasPick ? rawPick : null);
                const leanPct = parseFloat(evt.ai_lean_pct) || ((isPeriod || isFutures) && rawHasPick ? conf : 0);
                const hasPick = rawHasPick && !isPeriod && !isFutures;
                const pick = hasPick ? rawPick : null;
                const ticker = evt.ticker || evt.event_ticker || md.name || '';
                const extra = `{prop_type:'${jsq(propType)}', line:'${jsq(line)}', spread_amount:'${jsq(spreadAmount)}', over_under_amount:'${jsq(ouAmount)}', strike_details:'${jsq(strike)}', sport:'${jsq(sport || league)}', matchup:'${jsq(matchup)}'}`;

                // Buttons. Moneyline: one button per team market, each priced from its own
                // market (the old card showed the first market's price next to the AI pick,
                // which was often the other team's price).
                let buttons = [];
                let pickPrice = null;
                if ((isML || isPeriod || isFutures) && markets.length >= 2) {
                    const shown = isFutures ? [...markets].sort((a, b) => (cents(b, 'yes') || 0) - (cents(a, 'yes') || 0)).slice(0, 3) : markets.slice(0, 3);
                    shown.forEach(m => {
                        const name = mktName(m);
                        const price = cents(m, 'yes');
                        const isPickSide = hasPick && teamMatches(pick, m);
                        if (isPickSide && tradable(price)) pickPrice = price;
                        buttons.push({
                            cls: isPickSide ? 'spc-btn spc-btn-pick' : 'spc-btn',
                            k: name, p: tradable(price) ? price + '¢' : '—',
                            onclick: `addPredictionToSlip('${jsq(ticker)}', '${jsq(name)} (YES)', '${isPickSide ? conf.toFixed(1) : 'N/A'}', '${isPickSide && pickPrice != null ? (conf - pickPrice).toFixed(1) : 'N/A'}', 'YES', ${extra})`
                        });
                    });
                } else {
                    // Binary market (spread, total, prop, or a moneyline with one market).
                    const m0 = markets[0] || null;
                    const yesC = m0 ? cents(m0, 'yes') : (evt.yes_ask != null ? Math.round(evt.yes_ask * 100) : null);
                    let noC = m0 ? cents(m0, 'no') : (evt.no_ask != null ? Math.round(evt.no_ask * 100) : null);
                    if (noC == null && yesC != null) noC = 100 - yesC;
                    const parts = matchup.split(/\s+(?:vs\.?|@|v)\s+/i).map(s => s.trim()).filter(Boolean);
                    const yesTeam = m0 ? mktName(m0) : (pick || parts[0] || 'YES');
                    let yesSub = yesTeam, noSub = 'Not ' + yesTeam;
                    if (propType === 'Spread' && spreadAmount) yesSub = spreadAmount;
                    if (isTotal && ouAmount) { yesSub = 'Over ' + ouAmount; noSub = 'Under ' + ouAmount; }
                    if (isSeason) { const wm = segText.match(/\d+\+\s*wins?/i); yesSub = wm ? wm[0] : 'Yes'; noSub = 'Fewer'; }
                    if (propType === 'Spread') noSub = '';
                    if (isProp) { yesSub = line || 'Yes'; noSub = ''; }
                    if (isML && hasPick && m0) pickPrice = teamMatches(pick, m0) ? yesC : noC;
                    const yesLabel = (isProp ? (pick || yesTeam) : (isTotal && ouAmount ? `${matchup} — Over ${ouAmount}` : yesTeam)) + ' (YES)';
                    const noLabel = (isProp ? (pick || yesTeam) : (isTotal && ouAmount ? `${matchup} — Under ${ouAmount}` : yesTeam)) + ' (NO)';
                    const btnTicker = (isTotal && m0 && m0.ticker) ? m0.ticker : ticker;
                    buttons.push({
                        cls: 'spc-btn spc-btn-yes', k: 'YES', p: tradable(yesC) ? yesC + '¢' : '—',
                        onclick: `addPredictionToSlip('${jsq(btnTicker)}', '${jsq(yesLabel)}', '${hasPick ? conf.toFixed(1) : 'N/A'}', '${hasPick ? srvEdge.toFixed(1) : 'N/A'}', 'YES', ${extra})`
                    });
                    buttons.push({
                        cls: 'spc-btn spc-btn-no', k: 'NO', p: tradable(noC) ? noC + '¢' : '—',
                        onclick: `addPredictionToSlip('${jsq(btnTicker)}', '${jsq(noLabel)}', 'N/A', 'N/A', 'NO', ${extra})`
                    });
                }

                // AI line. Edge is model probability minus the price you would pay, so it is
                // only shown where the price belongs to the picked side (moneyline).
                let edgeVal = null;
                if (hasPick && isML && pickPrice != null) edgeVal = conf - pickPrice;

                // Extract Master Capper conviction evaluation & H2H indicators
                const capperObj = (evt.ai_prediction && evt.ai_prediction.metadata && evt.ai_prediction.metadata.capper)
                    || (evt.ai_prediction && evt.ai_prediction.capper)
                    || (evt.metadata && evt.metadata.capper)
                    || evt.capper;
                const cGrade = (capperObj && capperObj.grade) || evt.capper_grade || '';
                const cStars = (capperObj && capperObj.stars) || evt.capper_stars || '';
                const cTier = (capperObj && capperObj.tier_label) || evt.capper_tier || '';
                const cNetEv = (capperObj && capperObj.net_ev_pct != null) ? capperObj.net_ev_pct : evt.net_ev_pct;

                // Editorial Consensus & Tactical Intelligence badge
                const edConsensus = evt.editorial_consensus || (evt.metadata && evt.metadata.editorial_consensus) || (evt.ai_prediction && evt.ai_prediction.metadata && evt.ai_prediction.metadata.editorial_consensus) || (evt.tactical_intel && evt.tactical_intel.alignment);
                const edSource = evt.editorial_source || (evt.metadata && evt.metadata.editorial_source) || (evt.tactical_intel && evt.tactical_intel.source) || 'Editorial';
                let consensusBadge = '';
                if (edConsensus === 'AGREES') {
                    consensusBadge = `<span class="spc-tag spc-tag-sharp" style="background:rgba(16,185,129,0.18);border-color:rgba(16,185,129,0.4);color:#34d399;" title="${esc(edSource)} editorial analysis agrees with AI model pick">🟢 ${esc(edSource.replace(' Match Preview','').replace(' / PFF',''))}: Agrees</span>`;
                } else if (edConsensus === 'DIVERGES') {
                    consensusBadge = `<span class="spc-tag spc-tag-lean" style="background:rgba(245,158,11,0.18);border-color:rgba(245,158,11,0.4);color:#fbbf24;" title="${esc(edSource)} editorial analysis diverges from AI model pick">🟠 ${esc(edSource.replace(' Match Preview','').replace(' / PFF',''))}: Diverges</span>`;
                } else if (edConsensus === 'CONFIRMED_DATA') {
                    consensusBadge = `<span class="spc-tag spc-tag-edge" style="background:rgba(59,130,246,0.18);border-color:rgba(59,130,246,0.4);color:#60a5fa;" title="Verified tactical intel & starting lineup/goalie data active">🛡️ Intel Active</span>`;
                }

                let capperBadge = '';
                if (cGrade) {
                    const cCls = cGrade === 'A+' ? 'spc-tag-lock' : cGrade === 'A' ? 'spc-tag-sharp' : 'spc-tag-edge';
                    capperBadge = `<span class="spc-tag spc-tag-capper ${cCls}" title="Master Capper Grade: ${esc(cGrade)} ${esc(cStars)} (${esc(cTier)})">${esc(cGrade)} ${esc(cStars)}</span>`;
                }
                const h2hNote = (capperObj && Array.isArray(capperObj.capper_notes)) ? capperObj.capper_notes.find(n => /h2h|series|rivalry|head-to-head/i.test(n)) : null;
                const h2hBadge = h2hNote ? `<span class="spc-tag spc-tag-h2h" title="${esc(h2hNote)}">⚔️ H2H</span>` : '';
                const netEvHtml = (cNetEv != null && cNetEv > 0)
                    ? `<span class="spc-edge spc-edge-ev" title="Net Expected Value after Kalshi fees">+${Number(cNetEv).toFixed(1)}% EV</span>`
                    : '';

                let stratBadge = '';
                const evtStrat = evt.strategy_tag || '';
                if (evtStrat === 'FLOOR_TOTALS') {
                    stratBadge = `<span class="spc-tag" style="background:rgba(16,185,129,0.2);border-color:rgba(16,185,129,0.4);color:#34d399;" title="Floor Anchor Alternate Total (~87% historical hit rate)">🔥 Floor Anchor</span>`;
                } else if (evtStrat === 'MILESTONE_PROPS') {
                    stratBadge = `<span class="spc-tag" style="background:rgba(6,182,212,0.2);border-color:rgba(6,182,212,0.4);color:#22d3ee;" title="Milestone Contact Prop (~75% historical hit rate)">🎯 Milestone</span>`;
                }

                let ai;
                if (isPeriod || isFutures || (!hasPick && leanTeam)) {
                    const what = isFutures ? 'futures' : isPeriod ? String(segment || 'period').toLowerCase() : isTotal ? 'totals' : String(propType).toLowerCase();
                    ai = leanTeam
                        ? `<span class="spc-tag spc-tag-lean" title="The AI predicts full games only. This is its full-game pick, not a ${esc(what)} prediction.">GAME LEAN</span>${stratBadge}${consensusBadge}${capperBadge}${h2hBadge}<span class="spc-ai-pick">${esc(leanTeam)}</span><span class="spc-ai-num">${leanPct.toFixed(0)}% full game</span>${netEvHtml}<span class="spc-ai-go">›</span>`
                        : `<span class="spc-ai-none">No AI model for ${esc(what)} markets</span><span class="spc-ai-go">Analyze ⚡</span>`;
                } else if (!hasPick) {
                    ai = `<span class="spc-ai-none">${isProp ? 'No AI model for player props yet' : 'No AI pick yet'}</span><span class="spc-ai-go">Analyze ⚡</span>`;
                } else if (isProp) {
                    ai = `<span class="spc-tag spc-tag-est" title="Not a model prediction: based on the market price">EST</span>${stratBadge}${consensusBadge}${capperBadge}<span class="spc-ai-pick">${esc(pick)}</span><span class="spc-ai-num">${conf.toFixed(0)}%</span>${netEvHtml}<span class="spc-ai-go">›</span>`;
                } else if (isML) {
                    const edgeHtml = edgeVal == null ? ''
                        : edgeVal >= 0.5 ? `<span class="spc-edge spc-edge-pos">+${edgeVal.toFixed(0)} edge</span>`
                        : `<span class="spc-edge spc-edge-neg">${edgeVal.toFixed(0)} edge</span>`;
                    ai = `<span class="spc-tag">AI</span>${stratBadge}${consensusBadge}${capperBadge}${h2hBadge}<span class="spc-ai-pick">${esc(pick)}</span><span class="spc-ai-num ${conf >= 65 ? 'spc-hi' : ''}">${conf.toFixed(0)}% to win</span>${edgeHtml}${netEvHtml}<span class="spc-ai-go">›</span>`;
                } else {
                    // Spread / total cards are matched to the game's moneyline pick; the % is a
                    // win probability, not the chance this spread or total hits.
                    ai = `<span class="spc-tag spc-tag-lean">AI LEAN</span>${stratBadge}${consensusBadge}${capperBadge}${h2hBadge}<span class="spc-ai-pick">${esc(pick)}</span><span class="spc-ai-num">${conf.toFixed(0)}% to win</span>${netEvHtml}<span class="spc-ai-go">›</span>`;
                }

                // Detail line under the matchup (prop / spread / total specifics).
                // Multi-market cards (moneyline / period winner) show every side as a button, so the
                // first market's text ("Anaheim wins the 1st period") would only describe one side
                // and read like a pick. Show it only on single-market cards.
                let detail = '';
                const multiSide = (isML || isPeriod || isFutures) && markets.length >= 2;
                if (!isML && !multiSide && strike && strike.toLowerCase() !== matchup.toLowerCase()) {
                    detail = strike;
                }

                const typeCls = (isPeriod || isFutures || isSeason) ? 'spc-type-period' : isProp ? 'spc-type-prop' : propType === 'Spread' ? 'spc-type-spread' : isTotal ? 'spc-type-total' : 'spc-type-ml';
                const typeLabel = isSeason ? 'Season' : isPeriod ? (segment || 'Period') : isTotal ? 'Total' : propType;
                const linePill = (!isSeason && line && line !== 'Moneyline' && line !== propType && line !== segment && line !== 'Futures' && !detail.includes(line)) ? `<span class="spc-line">${esc(line)}</span>` : '';

                // Rank: when Floor/Combo/Mega Parlay strategy is active, prioritize Floor Anchor Totals & Milestone Props first.
                const isComboOrFloorStrat = ['FLOOR_TOTALS', 'MILESTONE_PROPS', 'POWER_COMBO', 'ULTRA_COMBO', 'MEGA_PARLAY'].includes(currentStrat);
                const isFloorOrMilestoneCard = (evtStrat === 'FLOOR_TOTALS' || evtStrat === 'MILESTONE_PROPS');
                const tier = (isComboOrFloorStrat && isFloorOrMilestoneCard) ? -1 : ((hasPick && isML && edgeVal != null && edgeVal >= 0.5) ? 0 : (hasPick && !isProp) ? 1 : (hasPick ? 2 : 3));
                const score = tier === 0 ? edgeVal : conf;

                const html = `
                    <div class="spc-main">
                        <div class="spc-meta">
                            <span class="spc-lg">${icon} ${esc(league)}</span>
                            <span class="spc-type ${typeCls}">${esc(typeLabel)}</span>${linePill}
                            <span class="spc-when">${fmtWhen(evt, md, isLive)}</span>
                        </div>
                        <div class="spc-match" data-ai="1">
                            <div class="spc-title">${esc(matchup)}</div>
                            ${detail ? `<div class="spc-detail">${esc(detail)}</div>` : ''}
                        </div>
                        <div class="spc-ai" data-ai="1">${ai}</div>
                    </div>
                    <div class="spc-btns spc-n${buttons.length}">
                        ${buttons.map(b => `<button type="button" class="${b.cls}" onclick="event.stopPropagation(); ${b.onclick}"><span class="spc-k">${esc(b.k)}</span><span class="spc-p">${esc(b.p)}</span></button>`).join('')}
                    </div>`;
                // Sort by the same start time the card displays (backend start_epoch is off for some sports).
                const shownStart = asianBaseballStart(evt) || ruleStartEpoch(evt) || tennisStartEpoch(evt, md) || startEpoch;
                return { evt, ticker, html, tier, score, start: shownStart || 9e12, isLive };
            });

            cards.sort((a, b) => (a.tier - b.tier) || (a.start - b.start) || (b.score - a.score));

            container.innerHTML = '';
            const frag = document.createDocumentFragment();
            cards.forEach(c => {
                const el = document.createElement('div');
                el.className = 'spc-card' + (c.isLive ? ' spc-is-live' : '') + (c.tier === 0 ? ' spc-is-best' : '');
                el.innerHTML = c.html;
                el.querySelectorAll('[data-ai]').forEach(n => n.addEventListener('click', () => querySportsAI(c.ticker, c.evt)));
                frag.appendChild(el);
            });
            container.appendChild(frag);
        }

        // =========================================================================
        // SPORTS BETTING STRATEGY HUB & COMBOS
        // =========================================================================
        window.currentSportsStrategy = 'STANDARD';

        const SPORTS_STRATEGIES = {
            'STANDARD': {
                name: 'Standard Value AI',
                badge: 'Standard Value AI',
                stat: 'Classic EV',
                summary: 'Mainline moneylines and spreads with AI model edge',
                color: 'amber'
            },
            'FLOOR_TOTALS': {
                name: 'Floor Anchor Totals',
                badge: 'Floor Anchor Totals',
                stat: '~90% Win Rate',
                summary: 'Lower alternate lines: SOC Over 0.5, NHL Over 2.5/3.5, MLB Over 5.5, NFL Over 31.5',
                color: 'emerald'
            },
            'MILESTONE_PROPS': {
                name: 'Milestone Props',
                badge: 'Milestone Props',
                stat: '~75% Win Rate',
                summary: 'Floor player milestones: MLB 1+ HRR (0.5), NBA 15+ Pts',
                color: 'cyan'
            },
            'POWER_COMBO': {
                name: 'Power-2 Combos',
                badge: 'Power-2 Combos',
                stat: '~72% Win Rate (+40% ROI)',
                summary: 'Bundles top 2 floor anchor legs into high-probability parlays',
                color: 'purple'
            },
            'ULTRA_COMBO': {
                name: 'Ultra-Floor Mega Parlay (15-20 Legs)',
                badge: 'Ultra-Floor Mega Parlay',
                stat: '15-20 Legs (~95% ea)',
                summary: 'Bundles 15–20 deep floor lines across all sports (SOC O0.5, NHL O2.5, NFL O28.5)',
                color: 'rose'
            },
            'ALL_ACTIVE': {
                name: 'All Strategies Active',
                badge: 'All Strategies Active',
                stat: 'Full Coverage',
                summary: 'Trades across standard lines, floor anchors, and player props',
                color: 'blue'
            }
        };

        function toggleSportsStrategyMenu() {
            const opts = document.getElementById('sports-strategy-options');
            const chev = document.getElementById('sports-strategy-chevron');
            if (!opts) return;
            const isHidden = opts.classList.contains('hidden');
            opts.classList.toggle('hidden', !isHidden);
            if (chev) chev.style.transform = isHidden ? 'rotate(180deg)' : '';
        }
        window.toggleSportsStrategyMenu = toggleSportsStrategyMenu;

        function getCurrentSportsTradeSize() {
            const el = document.getElementById('sports-trade-size-dollars') || document.getElementById('sports-wager-dollars');
            const raw = el && el.value ? parseFloat(el.value) : (window.lastDashboardStats?.sports_trade_size_dollars || window.lastDashboardStats?.sports_max_wager || 10.0);
            return (!isNaN(raw) && raw > 0) ? raw : 10.0;
        }
        window.getCurrentSportsTradeSize = getCurrentSportsTradeSize;

        function getSelectedParlayLegs(forStrat) {
            if (forStrat === 'POWER_COMBO') {
                const pEl = document.getElementById('strat-card-power-legs');
                if (pEl && pEl.value) {
                    const v = parseInt(pEl.value);
                    if (!isNaN(v) && v >= 2) return Math.min(30, v);
                }
            } else if (forStrat === 'ULTRA_COMBO') {
                const uEl = document.getElementById('strat-card-ultra-legs');
                if (uEl && uEl.value) {
                    const v = parseInt(uEl.value);
                    if (!isNaN(v) && v >= 2) return Math.min(30, v);
                }
            }
            const hubEl = document.getElementById('sports-parlay-legs-input') || document.getElementById('sports-max-parlay-legs');
            const val = parseInt(hubEl && hubEl.value ? hubEl.value : (window.lastDashboardStats?.sports_max_parlay_legs || 2));
            return (!isNaN(val) && val >= 2) ? Math.min(30, val) : 2;
        }
        window.getSelectedParlayLegs = getSelectedParlayLegs;

        function computeComboMetrics(legsOrCount, customWager, isUltraHint) {
            const wager = (customWager !== undefined && customWager > 0) ? customWager : getCurrentSportsTradeSize();
            let multiplier = 1.0;
            let jointProb = 1.0;
            let count = 2;

            if (Array.isArray(legsOrCount) && legsOrCount.length >= 1) {
                count = legsOrCount.length;
                legsOrCount.forEach(l => {
                    let p = parseFloat(l.price || (l.price_cents ? l.price_cents / 100 : 0.85));
                    if (isNaN(p) || p <= 0.04) p = 0.85;
                    if (p >= 0.99) p = 0.95;
                    multiplier *= (1.0 / p);
                    let c = parseFloat(l.conf !== undefined ? l.conf : (l.confidence !== undefined ? l.confidence : 88.0));
                    if (isNaN(c) || c <= 0) c = 88.0;
                    jointProb *= Math.min(0.99, Math.max(0.10, c / 100.0));
                });
            } else {
                count = Math.max(2, Math.min(30, parseInt(legsOrCount) || 2));
                const isUltra = isUltraHint !== undefined ? isUltraHint : (count >= 10 || window.currentSportsStrategy === 'ULTRA_COMBO');
                const cache = Array.isArray(window.__sportsEventsCache) ? window.__sportsEventsCache : [];
                const floorPool = cache.filter(e => {
                    const ask = parseFloat(e.yes_ask || 0);
                    return ask >= 0.35 && ask <= 0.97 && (e.strategy_tag === 'FLOOR_TOTALS' || e.strategy_tag === 'MILESTONE_PROPS' || parseFloat(e.confidence_pct || 0) >= 65);
                }).sort((a, b) => parseFloat(b.confidence_pct || 0) - parseFloat(a.confidence_pct || 0));

                for (let i = 0; i < count; i++) {
                    if (i < floorPool.length) {
                        let p = parseFloat(floorPool[i].yes_ask || (isUltra ? 0.91 : 0.84));
                        if (p <= 0.10 || p >= 0.99) p = isUltra ? 0.91 : 0.84;
                        let c = parseFloat(floorPool[i].confidence_pct || (isUltra ? 94.0 : 88.0));
                        multiplier *= (1.0 / p);
                        jointProb *= Math.min(0.985, Math.max(0.50, c / 100.0));
                    } else {
                        const fallbackPrice = isUltra ? 0.915 : 0.84;
                        const fallbackConf = isUltra ? 0.945 : 0.885;
                        multiplier *= (1.0 / fallbackPrice);
                        jointProb *= fallbackConf;
                    }
                }
            }

            const payout = Math.round(wager * multiplier * 100) / 100;
            const profit = Math.round((payout - wager) * 100) / 100;
            const roiPct = Math.round((multiplier - 1.0) * 1000) / 10;
            const jointWinPct = Math.round(jointProb * 1000) / 10;

            return { count, wager, multiplier, payout, profit, roiPct, jointWinPct };
        }
        window.computeComboMetrics = computeComboMetrics;

        function updateParlayPayoutPreviews() {
            const wager = getCurrentSportsTradeSize();
            const fmtMoney = (v) => v >= 1000 ? v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : v.toFixed(2);
            const fmtWager = Number.isInteger(wager) ? wager.toString() : wager.toFixed(2);

            // 1. Update Power Combo Card
            const powerLegs = getSelectedParlayLegs('POWER_COMBO');
            const pMetrics = computeComboMetrics(powerLegs, wager, false);
            const pPayoutEl = document.getElementById('strat-card-power-payout');
            if (pPayoutEl) pPayoutEl.textContent = `$${fmtWager} → Pays $${fmtMoney(pMetrics.payout)} (+$${fmtMoney(pMetrics.profit)})`;
            const pWinEl = document.getElementById('strat-card-power-win');
            if (pWinEl) pWinEl.textContent = `~${pMetrics.jointWinPct}% Win`;
            const pRoiEl = document.getElementById('strat-card-power-roi');
            if (pRoiEl) pRoiEl.textContent = `+${Math.round(pMetrics.roiPct)}% ROI`;
            const pTitleEl = document.getElementById('strat-card-power-title');
            if (pTitleEl) pTitleEl.textContent = `⚡ Power-${powerLegs} Combo`;

            // 2. Update Ultra Mega Parlay Card
            const ultraLegs = getSelectedParlayLegs('ULTRA_COMBO');
            const uMetrics = computeComboMetrics(ultraLegs, wager, true);
            const uPayoutEl = document.getElementById('strat-card-ultra-payout');
            if (uPayoutEl) uPayoutEl.textContent = `$${fmtWager} → Pays $${fmtMoney(uMetrics.payout)} (+$${fmtMoney(uMetrics.profit)})`;
            const uWinEl = document.getElementById('strat-card-ultra-win');
            if (uWinEl) uWinEl.textContent = `~${uMetrics.jointWinPct}% Joint`;
            const uRoiEl = document.getElementById('strat-card-ultra-roi');
            if (uRoiEl) uRoiEl.textContent = `+${Math.round(uMetrics.roiPct)}% ROI`;
            const uTitleEl = document.getElementById('strat-card-ultra-title');
            if (uTitleEl) uTitleEl.textContent = `🎰 Mega Parlay (${ultraLegs} Legs)`;

            // 3. Update Strategy Hub Bar Pill & Build Button
            const activeLegs = getSelectedParlayLegs();
            const hasActiveComboSlip = Array.isArray(window.sportsTradeSlip) && window.sportsTradeSlip.length >= 2 && window.sportsTradeSlipMode === 'combo';
            const barMetrics = hasActiveComboSlip
                ? computeComboMetrics(window.sportsTradeSlip, wager)
                : computeComboMetrics(activeLegs, wager, activeLegs >= 10 || window.currentSportsStrategy === 'ULTRA_COMBO');

            const barPayoutPill = document.getElementById('sports-strategy-payout-pill');
            if (barPayoutPill) {
                barPayoutPill.textContent = `$${fmtWager} → $${fmtMoney(barMetrics.payout)} (+$${fmtMoney(barMetrics.profit)})`;
            }

            const buildBtn = document.getElementById('btn-build-power-slip');
            if (buildBtn && !buildBtn.disabled) {
                const isUltra = (window.currentSportsStrategy === 'ULTRA_COMBO' || activeLegs >= 10);
                const btnMetrics = computeComboMetrics(activeLegs, wager, isUltra);
                buildBtn.innerHTML = `<span>⚡</span> Build ${activeLegs}-Leg Slip (+$${fmtMoney(btnMetrics.profit)})`;
                if (isUltra) {
                    buildBtn.className = 'inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 text-[10px] font-bold transition-all shadow-sm cursor-pointer';
                } else {
                    buildBtn.className = 'inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 text-[10px] font-bold transition-all shadow-sm cursor-pointer';
                }
            }

            // 4. Update Settings Drawer Parlay Preview
            const drawerPreview = document.getElementById('sports-drawer-parlay-preview');
            if (drawerPreview) {
                const dMetrics = computeComboMetrics(activeLegs, wager, activeLegs >= 10);
                drawerPreview.textContent = `$${fmtWager} Trade Size × ${activeLegs} Legs (${dMetrics.multiplier.toFixed(2)}×) → Pays $${fmtMoney(dMetrics.payout)} (+$${fmtMoney(dMetrics.profit)})`;
            }
        }
        window.updateParlayPayoutPreviews = updateParlayPayoutPreviews;

        function onParlayLegsInput(val, commitAndRebuild = false) {
            let n = parseInt(val);
            if (isNaN(n)) {
                if (!commitAndRebuild) return;
                n = 2;
            }
            n = Math.max(2, Math.min(30, n));

            const ids = ['sports-parlay-legs-input', 'sports-max-parlay-legs', 'slip-parlay-legs-input'];
            ids.forEach(id => {
                const el = document.getElementById(id);
                if (el && (commitAndRebuild || document.activeElement !== el)) {
                    el.value = String(n);
                }
            });

            if (n < 10) {
                const pEl = document.getElementById('strat-card-power-legs');
                if (pEl && document.activeElement !== pEl) pEl.value = String(n);
            } else {
                const uEl = document.getElementById('strat-card-ultra-legs');
                if (uEl && document.activeElement !== uEl) uEl.value = String(n);
            }

            updateParlayPayoutPreviews();

            if (commitAndRebuild) {
                if (typeof saveUserConfig === 'function') saveUserConfig();
                if (window.sportsTradeSlipMode === 'combo' && window.sportsTradeSlip && window.sportsTradeSlip.length > 0) {
                    buildPowerComboSlip(n);
                }
            }
        }
        window.onParlayLegsInput = onParlayLegsInput;

        function adjustParlayLegs(delta, rebuildIfCombo = false) {
            const cur = getSelectedParlayLegs();
            const next = Math.max(2, Math.min(30, cur + delta));
            const hubEl = document.getElementById('sports-parlay-legs-input');
            if (hubEl) hubEl.value = String(next);
            onParlayLegsInput(next, rebuildIfCombo);
        }
        window.adjustParlayLegs = adjustParlayLegs;

        function setParlayLegsFromCard(stratKey, val, isTyping = false) {
            let n = parseInt(val);
            if (isNaN(n)) return;
            n = Math.max(2, Math.min(30, n));

            if (stratKey === 'POWER_COMBO' && document.getElementById('strat-card-power-legs') && !isTyping) {
                document.getElementById('strat-card-power-legs').value = String(n);
            }
            if (stratKey === 'ULTRA_COMBO' && document.getElementById('strat-card-ultra-legs') && !isTyping) {
                document.getElementById('strat-card-ultra-legs').value = String(n);
            }
            const hubEl = document.getElementById('sports-parlay-legs-input');
            if (hubEl) hubEl.value = String(n);
            const drawerEl = document.getElementById('sports-max-parlay-legs');
            if (drawerEl) drawerEl.value = String(n);

            updateParlayPayoutPreviews();
            if (!isTyping) {
                selectSportsStrategy(stratKey, n);
            }
        }
        window.setParlayLegsFromCard = setParlayLegsFromCard;

        function onSportsTradeSizeInput(val, commitSave = false) {
            const num = parseFloat(val);
            if (!isNaN(num) && num > 0) {
                const mainInput = document.getElementById('sports-trade-size-dollars');
                if (mainInput && document.activeElement !== mainInput) mainInput.value = String(num);
                const hiddenInput = document.getElementById('sports-wager-dollars');
                if (hiddenInput) hiddenInput.value = String(num);
                const slipInput = document.getElementById('slip-wager-dollars-input');
                if (slipInput && document.activeElement !== slipInput) slipInput.value = String(num);
                if (window.lastDashboardStats) {
                    window.lastDashboardStats.sports_trade_size_dollars = num;
                    window.lastDashboardStats.sports_max_wager = num;
                }
            }
            updateParlayPayoutPreviews();
            updateSlipPayoutLive();
            updateExecuteBtnText();
            if (commitSave && typeof saveUserConfig === 'function') {
                saveUserConfig();
            }
        }
        window.onSportsTradeSizeInput = onSportsTradeSizeInput;

        function applySportsStrategyUI(stratKey) {
            stratKey = (stratKey || 'STANDARD').toUpperCase();
            if (!SPORTS_STRATEGIES[stratKey]) stratKey = 'STANDARD';
            window.currentSportsStrategy = stratKey;

            const def = SPORTS_STRATEGIES[stratKey];
            const badge = document.getElementById('sports-active-strategy-badge');
            const statPill = document.getElementById('sports-strategy-stat-pill');
            const summary = document.getElementById('sports-strategy-summary-text');
            const drawerBadge = document.getElementById('sports-drawer-strategy-badge');

            if (badge) badge.innerText = def.badge;
            if (statPill) statPill.innerText = def.stat;
            if (summary) summary.innerText = def.summary;
            if (drawerBadge) drawerBadge.innerText = def.name;

            updateParlayPayoutPreviews();

            // Highlight cards in dropdown
            document.querySelectorAll('.sports-strat-card').forEach(card => {
                const s = card.getAttribute('data-strat');
                const isSelected = (s === stratKey);
                const dot = card.querySelector('.strat-radio span');
                if (isSelected) {
                    card.classList.remove('border-white/10', 'bg-black/40');
                    card.classList.add('border-amber-500/50', 'bg-amber-500/10');
                    if (dot) dot.classList.remove('hidden');
                } else {
                    card.classList.add('border-white/10', 'bg-black/40');
                    card.classList.remove('border-amber-500/50', 'bg-amber-500/10');
                    if (dot) dot.classList.add('hidden');
                }
            });

            // Highlight pills in settings drawer
            const pillMap = {
                'STANDARD': 'sports-pill-strat-standard',
                'FLOOR_TOTALS': 'sports-pill-strat-floor',
                'MILESTONE_PROPS': 'sports-pill-strat-props',
                'POWER_COMBO': 'sports-pill-strat-combo',
                'ULTRA_COMBO': 'sports-pill-strat-ultra'
            };
            Object.keys(pillMap).forEach(k => {
                const btn = document.getElementById(pillMap[k]);
                if (btn) {
                    if (k === stratKey) {
                        btn.className = 'p-2 rounded-xl border border-amber-500/40 bg-amber-500/20 text-white text-[10px] font-bold flex flex-col items-center gap-0.5 transition-all cursor-pointer';
                    } else {
                        btn.className = 'p-2 rounded-xl border border-white/10 bg-black/40 text-gray-400 hover:text-white hover:bg-white/5 text-[10px] font-bold flex flex-col items-center gap-0.5 transition-all cursor-pointer';
                    }
                }
            });
        }
        window.applySportsStrategyUI = applySportsStrategyUI;

        async function selectSportsStrategy(stratKey, explicitLegs) {
            if (explicitLegs !== undefined) {
                onParlayLegsInput(explicitLegs, false);
            } else if (stratKey === 'ULTRA_COMBO' && getSelectedParlayLegs() < 10) {
                const uLegs = getSelectedParlayLegs('ULTRA_COMBO') || 15;
                onParlayLegsInput(uLegs >= 10 ? uLegs : 15, false);
            } else if (stratKey === 'POWER_COMBO' && getSelectedParlayLegs() >= 10) {
                const pLegs = getSelectedParlayLegs('POWER_COMBO') || 2;
                onParlayLegsInput(pLegs < 10 ? pLegs : 2, false);
            }
            applySportsStrategyUI(stratKey);
            // Close options drawer
            const opts = document.getElementById('sports-strategy-options');
            if (opts && !opts.classList.contains('hidden')) {
                toggleSportsStrategyMenu();
            }
            // Ensure we are on the SPORTS universe view when interacting with sports strategies
            if (window.currentUniverse !== 'SPORTS' && typeof window.selectUniverse === 'function') {
                window.selectUniverse('SPORTS');
            }
            // Save config to server (non-blocking)
            if (typeof saveUserConfig === 'function') {
                saveUserConfig();
            }
            // Re-fetch and re-render sports events according to the newly active strategy
            if (typeof loadSportsEvents === 'function') {
                loadSportsEvents();
            } else if (typeof renderSportsEvents === 'function') {
                renderSportsEvents();
            }
            // Automatically build the combo slip when user selects Mega Parlay or Power Combos
            if (stratKey === 'ULTRA_COMBO' || stratKey === 'MEGA_PARLAY') {
                buildPowerComboSlip(explicitLegs || getSelectedParlayLegs('ULTRA_COMBO') || 15);
            } else if (stratKey === 'POWER_COMBO') {
                buildPowerComboSlip(explicitLegs || getSelectedParlayLegs('POWER_COMBO') || 2);
            } else {
                showToast(`Active Strategy set to: ${SPORTS_STRATEGIES[stratKey].name}`, 'success');
            }
        }
        window.selectSportsStrategy = selectSportsStrategy;

        async function buildPowerComboSlip(requestedCount) {
            const strat = window.currentSportsStrategy || 'POWER_COMBO';
            const customLegs = requestedCount !== undefined ? parseInt(requestedCount) : getSelectedParlayLegs();
            const count = Math.max(2, Math.min(30, !isNaN(customLegs) ? customLegs : (strat === 'ULTRA_COMBO' ? 15 : 2)));
            const isUltra = (strat === 'ULTRA_COMBO' || strat === 'MEGA_PARLAY' || count >= 10);
            const wager = getCurrentSportsTradeSize();

            // Sync leg count inputs
            ['sports-parlay-legs-input', 'sports-max-parlay-legs', 'slip-parlay-legs-input'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = String(count);
            });

            const btn = document.getElementById('btn-build-power-slip');
            const origHtml = btn ? btn.innerHTML : null;
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = `<span>⏳</span> Building ${count}-Leg Slip...`;
            }
            
            showToast(`Scanning sports slate for top ${count} floor anchor lines ($${wager} trade size)...`, 'info');
            try {
                const token = localStorage.getItem('saas_token') || localStorage.getItem('app_api_token') || '';
                const headers = token ? { 'Authorization': 'Bearer ' + token } : {};
                let comboData = null;
                try {
                    const targetStrat = isUltra ? 'ULTRA_COMBO' : strat;
                    const endpoint = `/api/engine/sports/combo/recommend?count=${count}&strategy=${encodeURIComponent(targetStrat)}&trade_size=${encodeURIComponent(wager)}`;
                    const res = await fetch((window.API_BASE_URL || '') + endpoint, { headers });
                    if (res.ok) comboData = await res.json();
                } catch(e) {}

                let legs = comboData && comboData.legs && comboData.legs.length >= 2 ? comboData.legs : null;

                // Fallback: build from client cache if recommend endpoint had fewer than 2 legs
                if ((!legs || legs.length < Math.min(count, 2)) && window.__sportsEventsCache && window.__sportsEventsCache.length > 0) {
                    const pool = [...window.__sportsEventsCache]
                        .filter(e => e.ai_pick && parseFloat(e.confidence_pct || 0) >= 50.0 && parseFloat(e.yes_ask || 0.85) <= 0.98)
                        .sort((a, b) => {
                            const aDay = a.is_today ? 100 : 0;
                            const bDay = b.is_today ? 100 : 0;
                            const aBonus = (a.strategy_tag === 'FLOOR_TOTALS' ? 25 : (a.strategy_tag === 'MILESTONE_PROPS' ? 15 : 0));
                            const bBonus = (b.strategy_tag === 'FLOOR_TOTALS' ? 25 : (b.strategy_tag === 'MILESTONE_PROPS' ? 15 : 0));
                            return (bDay + parseFloat(b.confidence_pct || 0) + bBonus) - (aDay + parseFloat(a.confidence_pct || 0) + aBonus);
                        });
                    if (pool.length >= 2) {
                        legs = pool.slice(0, count).map(e => ({
                            ticker: (e.markets && e.markets[0] ? e.markets[0].ticker : e.ticker),
                            team: e.ai_pick || e.predicted_team || 'Over 2.5 Goals',
                            side: e.pick_side || 'YES',
                            price: parseFloat(e.yes_ask || 0.85),
                            confidence: parseFloat(e.confidence_pct || 88.0),
                            edge: parseFloat(e.edge_pct || 5.0),
                            prop_type: e.market_type || 'Total',
                            line: e.strike_details || (e.strategy_tag === 'FLOOR_TOTALS' ? 'Floor Line' : 'Moneyline'),
                            sport: e.sport || 'SPORTS',
                            matchup: e.matchup || e.title
                        }));
                    }
                }

                if (!legs || legs.length < 2) {
                    showToast('No active floor anchor lines currently on slate. Try again closer to game time!', 'warning');
                    return;
                }

                // Ensure SPORTS universe is active so the Trade Slip panel is visible
                window.currentUniverse = 'SPORTS';
                document.body.classList.add('universe-sports');

                // Populate window.sportsTradeSlip
                window.sportsTradeSlip = legs.map(l => ({
                    ticker: l.ticker,
                    team: l.team,
                    type: l.prop_type || 'Floor Total',
                    prop_type: l.prop_type || 'Total',
                    line: l.line || 'Floor Line',
                    side: l.side || 'YES',
                    conf: l.confidence || 90,
                    edge: l.edge || 5,
                    price: l.price || (l.price_cents ? l.price_cents / 100 : 0.5),
                    sport: l.sport || 'SPORTS',
                    matchup: l.matchup || l.team
                }));
                window.sportsTradeSlipMode = 'combo';
                if (typeof renderTradeSlip === 'function') {
                    renderTradeSlip();
                }
                updateParlayPayoutPreviews();
                const panel = document.getElementById('sports-trade-slip-panel');
                if (panel) {
                    panel.classList.remove('sp-collapsed', 'hidden');
                    panel.classList.add('flex');
                    try { panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); } catch(_) {}
                }
                const metrics = computeComboMetrics(window.sportsTradeSlip, wager);
                showToast(`⚡ ${legs.length}-Leg Parlay built! $${wager.toFixed(2)} Wager → Pays $${metrics.payout.toFixed(2)} (+$${metrics.profit.toFixed(2)} / +${metrics.roiPct}% ROI)`, 'success');
            } catch (err) {
                console.error('[buildPowerComboSlip] Error:', err);
                showToast('Failed to build combo slip. Please select picks manually.', 'error');
            } finally {
                if (btn && origHtml) {
                    btn.disabled = false;
                    applySportsStrategyUI(window.currentSportsStrategy || 'POWER_COMBO');
                }
            }
        }
        window.buildPowerComboSlip = buildPowerComboSlip;

        // Global Trade Slip state
        window.sportsTradeSlip = [];
        document.addEventListener('DOMContentLoaded', () => {
            renderTradeSlip();
            updateParlayPayoutPreviews();
        });

        function updateSlipPayoutLive() {
            const box = document.getElementById('sp-slip-payout-summary');
            if (!box || !window.sportsTradeSlip || window.sportsTradeSlip.length === 0) return;
            const currentMode = window.sportsTradeSlipMode || 'single';
            const wager = getCurrentSportsTradeSize();
            const fmt = (v) => v >= 1000 ? v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : v.toFixed(2);

            if (currentMode === 'combo') {
                const m = computeComboMetrics(window.sportsTradeSlip, wager);
                box.innerHTML = `
                    <div class="flex items-center justify-between text-[10px] font-mono mb-1">
                        <span class="text-purple-300 font-bold uppercase tracking-wider">⚡ ${m.count}-Leg Parlay Payout</span>
                        <span class="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/40 font-black">${m.multiplier.toFixed(2)}× Multiplier</span>
                    </div>
                    <div class="grid grid-cols-3 gap-1.5 text-center font-mono bg-black/50 p-1.5 rounded-lg border border-white/5">
                        <div>
                            <div class="text-[8px] text-gray-400 uppercase">Trade Size</div>
                            <div class="text-[11px] font-black text-white">$${fmt(m.wager)}</div>
                        </div>
                        <div>
                            <div class="text-[8px] text-gray-400 uppercase">Total Payout</div>
                            <div class="text-[11px] font-black text-cyan-300">$${fmt(m.payout)}</div>
                        </div>
                        <div>
                            <div class="text-[8px] text-gray-400 uppercase">Net Profit</div>
                            <div class="text-[11px] font-black text-emerald-400">+$${fmt(m.profit)}</div>
                        </div>
                    </div>
                    <div class="flex items-center justify-between text-[9px] font-mono text-gray-400 mt-1 px-0.5">
                        <span>Joint Win Prob: <strong class="text-amber-300">${m.jointWinPct}%</strong></span>
                        <span class="text-emerald-400 font-bold">+${m.roiPct}% Projected ROI</span>
                    </div>
                `;
            } else {
                const n = window.sportsTradeSlip.length;
                const totalOutlay = n * wager;
                let totalSingleProfit = 0;
                window.sportsTradeSlip.forEach(item => {
                    const p = Math.max(0.05, Math.min(0.98, parseFloat(item.price || 0.5)));
                    totalSingleProfit += wager * ((1.0 / p) - 1.0);
                });
                box.innerHTML = `
                    <div class="flex items-center justify-between text-[10px] font-mono">
                        <span class="text-cyan-300 font-bold">${n} Single Trade${n > 1 ? 's' : ''} × $${fmt(wager)}</span>
                        <span class="text-white font-black">Outlay: $${fmt(totalOutlay)}</span>
                    </div>
                    <div class="flex items-center justify-between text-[9px] font-mono text-gray-400 mt-0.5">
                        <span>Est. Total Profit if all hit:</span>
                        <span class="text-emerald-400 font-bold">+$${fmt(totalSingleProfit)}</span>
                    </div>
                `;
            }
        }
        window.updateSlipPayoutLive = updateSlipPayoutLive;

        function renderTradeSlip() {
            let panel = document.getElementById('sports-trade-slip-panel');
            if (!panel) return;
            
            if (!window.sportsTradeSlip || window.sportsTradeSlip.length === 0 || (window.currentUniverse && window.currentUniverse !== 'SPORTS')) {
                panel.classList.add('hidden');
                panel.classList.remove('flex');
                panel.innerHTML = '';
                return;
            }

            panel.classList.remove('hidden');
            panel.classList.add('flex');
            
            const currentMode = window.sportsTradeSlipMode || 'single';
            const sportsTradeSize = getCurrentSportsTradeSize();
            const slipLegsCount = window.sportsTradeSlip.length;
            let html = `
                <div class="sp-slip-head p-3 border-b border-white/10 bg-gradient-to-r from-cyan-900/30 to-transparent flex justify-between items-center rounded-t-xl">
                    <button type="button" onclick="document.getElementById('sports-trade-slip-panel').classList.toggle('sp-collapsed')" class="sp-slip-title text-xs font-black text-cyan-300 uppercase tracking-wider flex items-center gap-1.5">🧾 Trade Slip (${slipLegsCount} Legs)<span class="sp-slip-chevron">▾</span></button>
                    <button onclick="window.sportsTradeSlip=[]; renderTradeSlip(); updateParlayPayoutPreviews();" class="sp-slip-clear text-gray-400 hover:text-white" aria-label="Clear slip">✖</button>
                </div>
                <!-- Custom Legs & Trade Size Quick Toolbar -->
                <div class="px-3 py-2 bg-black/60 border-b border-white/10 flex items-center justify-between gap-2 text-[10px] font-mono">
                    <div class="flex items-center gap-1">
                        <span class="text-gray-400 font-bold uppercase text-[9px]">Legs:</span>
                        <button type="button" onclick="adjustParlayLegs(-1, true)" class="w-4 h-4 rounded bg-white/10 hover:bg-white/20 text-white font-black flex items-center justify-center cursor-pointer">−</button>
                        <input type="number" id="slip-parlay-legs-input" min="2" max="30" value="${slipLegsCount}" onchange="buildPowerComboSlip(this.value)" class="w-8 bg-[#0b101a] border border-cyan-500/40 rounded text-center font-bold text-amber-300 py-0.5 outline-none">
                        <button type="button" onclick="adjustParlayLegs(1, true)" class="w-4 h-4 rounded bg-white/10 hover:bg-white/20 text-white font-black flex items-center justify-center cursor-pointer">+</button>
                        <button type="button" onclick="buildPowerComboSlip(document.getElementById('slip-parlay-legs-input')?.value || ${slipLegsCount})" class="ml-0.5 px-1.5 py-0.5 rounded bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/35 text-[8.5px] font-bold cursor-pointer" title="Rebuild combo with this many legs">↻ Auto-Fill</button>
                    </div>
                    <div class="flex items-center gap-1">
                        <span class="text-gray-400 font-bold uppercase text-[9px]">Wager $:</span>
                        <input type="number" id="slip-wager-dollars-input" min="1" max="1000" value="${sportsTradeSize}" oninput="onSportsTradeSizeInput(this.value, false)" onchange="onSportsTradeSizeInput(this.value, true)" class="w-12 bg-[#0b101a] border border-amber-500/40 rounded text-right px-1 py-0.5 font-bold text-white outline-none">
                    </div>
                </div>
                <div class="sp-slip-list p-3 space-y-2 max-h-56 overflow-y-auto">
            `;
            window.sportsTradeSlip.forEach((item, index) => {
                const sportIcons = {
                    'NHL': '🏒', 'NFL': '🏈', 'MLB': '⚾', 'NBA': '🏀', 'SOC': '⚽', 'SOCCER': '⚽',
                    'UFC': '🥊', 'MMA': '🥊', 'TEN': '🎾', 'TENNIS': '🎾', 'NCAAF': '🏈', 'NCAAB': '🏀',
                    'NPB': '⚾', 'KBO': '⚾'
                };
                const rawSport = (item.sport || '').toUpperCase();
                const icon = sportIcons[rawSport] || (rawSport.includes('NHL') ? '🏒' : rawSport.includes('NFL') ? '🏈' : rawSport.includes('TEN') ? '🎾' : '🏆');
                const sportLabel = rawSport ? (rawSport.replace('SOCCER', 'SOC').replace('TENNIS', 'TEN')) : 'SPORTS';

                const propType = item.prop_type || 'Pick';
                let propBadgeClass = 'bg-blue-500/20 text-blue-300 border-blue-500/35';
                if (propType === 'Spread') propBadgeClass = 'bg-purple-500/20 text-purple-300 border-purple-500/35';
                else if (propType.includes('Total') || propType.includes('O/U')) propBadgeClass = 'bg-amber-500/20 text-amber-300 border-amber-500/35';
                else if (propType === 'Player Prop') propBadgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/35';

                // Clean matchup headline
                let matchupDisplay = item.matchup || '';
                if (!matchupDisplay || matchupDisplay.toLowerCase().includes('over') || matchupDisplay.toLowerCase().includes('under') || matchupDisplay.length < 5) {
                    matchupDisplay = item.team || item.ticker;
                }
                matchupDisplay = matchupDisplay.replace(/:\s*(Total|Spread|Game).*$/i, '').trim();

                // Clean Target Line detail
                let lineDisplay = item.line || '';
                if (!lineDisplay || lineDisplay === 'Moneyline' || lineDisplay === 'Floor Line') {
                    if (item.strike_details && item.strike_details !== 'Moneyline') lineDisplay = item.strike_details;
                    else if (propType.includes('Total') && item.team && (item.team.includes('Over') || item.team.includes('Under'))) lineDisplay = item.team;
                    else lineDisplay = item.team;
                }
                // Strip redundant "Full Game:" prefixes
                lineDisplay = lineDisplay.replace(/^Full Game:\s*/i, '').trim();

                const sideColor = (item.side || 'YES').toUpperCase() === 'YES' ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' : 'text-rose-400 bg-rose-500/10 border-rose-500/30';
                const priceCents = item.price ? Math.round(item.price * 100) : (item.price_cents || null);
                const priceTag = priceCents ? `<span class="px-1.5 py-0.5 rounded font-mono text-[9px] font-bold bg-white/5 border border-white/10 text-cyan-300">@ ${priceCents}¢</span>` : '';

                html += `
                    <div class="p-2.5 bg-black/50 border border-white/10 hover:border-cyan-500/30 rounded-xl relative group transition-all">
                        <button onclick="window.sportsTradeSlip.splice(${index}, 1); renderTradeSlip(); updateParlayPayoutPreviews();" aria-label="Remove pick" class="sp-slip-remove absolute top-2 right-2 text-gray-500 hover:text-rose-400 cursor-pointer p-0.5 transition-colors">✖</button>
                        
                        <!-- Top Row: League & Matchup -->
                        <div class="flex items-center gap-1.5 mb-1.5 pr-6">
                            <span class="px-1.5 py-0.5 rounded font-bold text-[8.5px] uppercase bg-cyan-950/60 text-cyan-300 border border-cyan-800/40">${icon} ${sportLabel}</span>
                            <span class="text-[11px] font-bold text-gray-200 truncate" title="${matchupDisplay}">${matchupDisplay}</span>
                        </div>
                        
                        <!-- Middle Row: Target Line & Side & Price -->
                        <div class="flex items-center justify-between gap-1.5 mb-1 bg-white/5 p-1.5 rounded-lg border border-white/5">
                            <div class="flex items-center gap-1.5 truncate">
                                <span class="px-1.5 py-0.5 rounded font-black text-[9px] uppercase border ${sideColor}">${item.side || 'YES'}</span>
                                <span class="text-[11px] font-bold text-white truncate">${lineDisplay}</span>
                            </div>
                            <div class="flex items-center gap-1 shrink-0">
                                ${priceTag}
                            </div>
                        </div>
                        
                        <!-- Bottom Row: AI Model Stats & Ticker Suffix -->
                        <div class="flex items-center justify-between text-[9px] font-mono text-gray-400 pt-0.5">
                            <span class="text-emerald-400 font-bold">${item.conf !== 'N/A' && item.conf ? `AI Conf: ${item.conf}% · Edge: +${item.edge || 0}%` : 'Selected Pick'}</span>
                            <span class="text-[8.5px] text-gray-500 font-mono truncate max-w-[110px]">${item.ticker ? item.ticker.split('-').slice(-1)[0] : ''}</span>
                        </div>
                    </div>
                `;
            });
            html += `
                </div>
                <div class="sp-slip-foot p-3 border-t border-white/10 space-y-2">
                    <!-- Dynamic Payout & Profit Breakdown Box -->
                    <div id="sp-slip-payout-summary" class="p-2 rounded-xl bg-gradient-to-br from-purple-950/35 via-[#0d1424] to-black border border-purple-500/30"></div>
                    <div class="sp-slip-type flex justify-center gap-4 text-xs font-bold text-gray-300">
                        <label class="flex items-center gap-1 cursor-pointer">
                            <input type="radio" name="trade_type" value="single" ${currentMode === 'single' ? 'checked' : ''} onchange="window.sportsTradeSlipMode='single'; updateSlipPayoutLive(); updateExecuteBtnText(); updateParlayPayoutPreviews();" class="accent-cyan-500">
                            Single Trades
                        </label>
                        <label class="flex items-center gap-1 cursor-pointer">
                            <input type="radio" name="trade_type" value="combo" ${currentMode === 'combo' ? 'checked' : ''} onchange="window.sportsTradeSlipMode='combo'; updateSlipPayoutLive(); updateExecuteBtnText(); updateParlayPayoutPreviews();" class="accent-cyan-500">
                            Combo (Parlay)
                        </label>
                    </div>
                    <button onclick="executeTradeSlip()" class="w-full py-2 bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs uppercase tracking-wider rounded transition-colors cursor-pointer" id="btn-execute-slip"></button>
                </div>
            `;
            panel.innerHTML = html;
            updateSlipPayoutLive();
            updateExecuteBtnText();
        }

        function updateExecuteBtnText() {
            const btn = document.getElementById('btn-execute-slip');
            if (!btn || btn.disabled) return;
            const sportsTradeSize = getCurrentSportsTradeSize();
            const isCombo = (window.sportsTradeSlipMode === 'combo');
            if (isCombo && window.sportsTradeSlip && window.sportsTradeSlip.length >= 2) {
                const m = computeComboMetrics(window.sportsTradeSlip, sportsTradeSize);
                btn.textContent = `Execute ${m.count}-Leg Combo ($${sportsTradeSize} → Pays $${m.payout.toFixed(2)} / +$${m.profit.toFixed(2)})`;
            } else {
                btn.textContent = isCombo ? `Approve & Execute Combo ($${sportsTradeSize})` : `Approve & Execute ${window.sportsTradeSlip?.length || ''} Trade${(window.sportsTradeSlip?.length || 1) > 1 ? 's' : ''} ($${sportsTradeSize} ea)`;
            }
        }
        window.updateExecuteBtnText = updateExecuteBtnText;

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
            
            let isCombo = (window.sportsTradeSlipMode === 'combo');
            const typeEls = document.getElementsByName('trade_type');
            for (let i = 0; i < typeEls.length; i++) {
                if (typeEls[i].checked) {
                    isCombo = (typeEls[i].value === 'combo');
                    window.sportsTradeSlipMode = typeEls[i].value;
                }
            }
            
            const sportsTradeSize = parseFloat(document.getElementById('sports-trade-size-dollars')?.value || document.getElementById('sports-wager-dollars')?.value || 10.0) || 10.0;
            
            if (isCombo && (!window.sportsTradeSlip || window.sportsTradeSlip.length < 2)) {
                showToast('Combo (Parlay) requires at least 2 picks in your trade slip. Add another pick or select Single Trades.', 'warning');
                if (btn) {
                    btn.disabled = false;
                    updateExecuteBtnText();
                }
                return;
            }

            // Orders are always placed for the logged-in account: the server reads the user
            // from the login token. Never guess an account id here.
            const slipToken = localStorage.getItem('saas_token');
            const sessionExpired = () => {
                showToast('Session expired. Please log in again to place trades.', 'error');
            };
            if (!slipToken || slipToken === 'null' || slipToken === 'undefined') {
                sessionExpired();
                if (btn) {
                    btn.disabled = false;
                    updateExecuteBtnText();
                }
                return;
            }
            const slipHeaders = { 'Authorization': 'Bearer ' + slipToken };

            try {
                if (isCombo) {
                    try {
                        const tickers = window.sportsTradeSlip.map(i => i.ticker).join(',');
                        const teams = window.sportsTradeSlip.map(i => i.team).join(',');
                        const sides = window.sportsTradeSlip.map(i => i.side || (i.team && i.team.includes('(NO)') ? 'NO' : 'YES')).join(',');
                        const authH = slipHeaders;
                        const comboUrl = (window.API_BASE_URL || '') + '/api/engine/sports/combo?event_tickers=' + encodeURIComponent(tickers) + '&teams=' + encodeURIComponent(teams) + '&sides=' + encodeURIComponent(sides) + '&trade_size=' + encodeURIComponent(sportsTradeSize);
                        const res = await fetch(comboUrl, { method: 'POST', headers: authH });
                        if (res.status === 401) { sessionExpired(); return; }
                        const data = await res.json();
                        if (res.ok && data.combo_executed) {
                            if (data.is_single_kalshi_combo) {
                                showToast(`⚡ Single Kalshi Combo Ticket Placed! (${data.total_requested} legs on ${data.kalshi_market_ticker})`, 'success');
                            } else {
                                showToast(`Combo trade executed (${data.trades.length} legs)`, 'success');
                            }
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
                            const url = (window.API_BASE_URL || '') + '/api/engine/sports/execute?event_ticker=' + encodeURIComponent(item.ticker) + '&manual_team=' + encodeURIComponent(team) + '&trade_size=' + encodeURIComponent(sportsTradeSize) + sideParam;
                            const authH = slipHeaders;
                            const res = await fetch(url, { method: 'POST', headers: authH });
                            if (res.status === 401) { sessionExpired(); return; }
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
                    updateExecuteBtnText();
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
            const esc = (v) => String(v == null ? '' : v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
            
            closeSportsAIPopup();
            
            const fullEvt = evt || (window.__sportsEventsCache ? window.__sportsEventsCache.find(x => x.event_ticker === ticker) : {}) || {};
            const md = fullEvt.metadata || {};
            const sport = String(fullEvt.sport || md.sport || 'SPORTS').toUpperCase();
            const league = String(fullEvt.league || md.league || sport).toUpperCase();
            const icon = (typeof SPORT_ICONS !== 'undefined' && (SPORT_ICONS[sport] || SPORT_ICONS[league])) ? (SPORT_ICONS[sport] || SPORT_ICONS[league]) : '🏟️';
            const rawMatchup = fullEvt.matchup || md.matchup || ticker;
            const cleanMatchup = expandMatchupNames(rawMatchup.replace(/:\s*(Spread|Total\s*Runs?|Totals?|Game|Moneyline).*$/i, '').trim() || rawMatchup, sport || league);
            const shownStart = (typeof window.__sportsStartLabel === 'function') ? window.__sportsStartLabel(fullEvt) : '';
            const gameTime = String(shownStart || fullEvt.game_time || md.game_time || 'Upcoming / Today').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            
            const popup = document.createElement('div');
            popup.id = 'sports-ai-popup';
            popup.className = 'sp-ai-popup fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[92%] max-w-md bg-[#0c0c10]/95 backdrop-blur-3xl border border-cyan-500/50 rounded-2xl shadow-[0_20px_70px_rgba(0,200,255,0.15)] z-[9999] overflow-hidden flex flex-col';
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
                const titleText = (fullEvt && (fullEvt.title || fullEvt.matchup || md.matchup || fullEvt.predicted_team || md.name)) || '';
                const titleParam = titleText ? '&title=' + encodeURIComponent(titleText) : '';
                const sportParam = fullEvt && (fullEvt.sport || fullEvt.league) ? '&sport=' + encodeURIComponent(fullEvt.sport || fullEvt.league) : '';
                
                const token = localStorage.getItem('saas_token') || localStorage.getItem('app_api_token') || '';
                const fetchOpts = {
                    headers: token ? { 'Authorization': `Bearer ${token}` } : {}
                };
                
                const res = await fetch((window.API_BASE_URL || '') + '/api/engine/sports/predict?event_ticker=' + encodeURIComponent(ticker) + '&execute=false' + titleParam + sportParam, fetchOpts);
                if (!res.ok) throw new Error('HTTP ' + res.status);
                const data = await res.json();
                // Keep the popup on the same pick as the card. /predict can fall back to a fresh on-demand
                // simulation that disagrees with the model pick shown in the list (it also re-rolls each
                // time), so when the feed already has a pick for this event, the popup shows that one.
                try {
                    const fp = fullEvt.ai_prediction || null;
                    const feedTeam = fullEvt.has_ai_prediction ? (fullEvt.ai_pick || (fp && fp.predicted_team) || '') : '';
                    const p0 = data.prediction || {};
                    const nrm = (v) => String(v || '').toLowerCase().replace(/[^a-z0-9]/g, '');
                    if (feedTeam && fp && parseFloat(fullEvt.confidence_pct || fp.confidence_pct) > 0 && nrm(p0.predicted_team) !== nrm(feedTeam)) {
                        data.prediction = Object.assign({}, p0, {
                            predicted_team: feedTeam,
                            confidence_pct: fp.confidence_pct != null ? fp.confidence_pct : fullEvt.confidence_pct,
                            edge_pct: fullEvt.edge_pct != null ? fullEvt.edge_pct : fp.edge_pct,
                            opponent: fp.opponent || p0.opponent,
                            market_type: fp.market_type || p0.market_type,
                            metadata: Object.assign({}, fp.metadata || {})
                        });
                    }
                } catch (e) { /* keep /predict's answer */ }
                
                const pred = data.prediction || {};
                const details = data.event_details || {};
                const propType = details.prop_type || pred.prop_type || fullEvt.prop_type || md.prop_type || 'Moneyline';
                const line = details.line || pred.line || fullEvt.line || md.line || (propType === 'Moneyline' ? 'Moneyline' : '');
                const spreadAmount = details.spread_amount || pred.spread_amount || fullEvt.spread_amount || md.spread_amount || '';
                const overUnderAmount = details.over_under_amount || pred.over_under_amount || fullEvt.over_under_amount || md.over_under_amount || '';
                const strikeDetails = details.strike_details || pred.strike_details || fullEvt.strike_details || md.strike_details || '';

                const team = pred.predicted_team || fullEvt.predicted_team || ticker;
                // No invented fallbacks (this used to show 55% / +5% when the AI had nothing).
                const conf = pred.confidence_pct != null ? parseFloat(pred.confidence_pct).toFixed(1) : (fullEvt.confidence_pct ? parseFloat(fullEvt.confidence_pct).toFixed(1) : 'N/A');
                const edge = pred.edge_pct != null ? parseFloat(pred.edge_pct).toFixed(1) : (fullEvt.edge_pct ? parseFloat(fullEvt.edge_pct).toFixed(1) : 'N/A');
                const hasAiPickNow = parseFloat(pred.confidence_pct) > 0 && !!pred.predicted_team && !(window.sportsGameLevelPickOnProp && window.sportsGameLevelPickOnProp(fullEvt, pred));
                
                const yesPriceVal = fullEvt.yes_ask != null ? Math.round(fullEvt.yes_ask * 100) : (md.yes_ask != null ? Math.round(md.yes_ask * 100) : null);
                const noPriceVal = fullEvt.no_ask != null ? Math.round(fullEvt.no_ask * 100) : (md.no_ask != null ? Math.round(md.no_ask * 100) : (yesPriceVal != null ? (100 - yesPriceVal) : null));
                
                let propBadgeClass = 'bg-blue-500/20 text-blue-300 border-blue-500/40';
                if (propType === 'Spread') propBadgeClass = 'bg-purple-500/20 text-purple-300 border-purple-500/40';
                else if (propType.includes('Total') || propType.includes('O/U')) propBadgeClass = 'bg-amber-500/20 text-amber-300 border-amber-500/40';
                else if (propType === 'Player Prop') propBadgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';

                // Extract Master Capper Intelligence
                const capper = (pred && pred.metadata && pred.metadata.capper)
                    || (pred && pred.capper)
                    || (fullEvt && fullEvt.ai_prediction && fullEvt.ai_prediction.metadata && fullEvt.ai_prediction.metadata.capper)
                    || (fullEvt && fullEvt.metadata && fullEvt.metadata.capper)
                    || (fullEvt && fullEvt.capper);

                const content = document.getElementById('sports-ai-popup-content');
                if (content) {
                    content.innerHTML = `
                        <div class="space-y-3 text-left">
                            <!-- Event Matchup & League Details -->
                            <div class="bg-black/50 p-3 rounded-xl border border-white/10">
                                <div class="flex items-center justify-between gap-2 mb-1.5 flex-wrap">
                                    <div class="flex items-center gap-1.5 flex-wrap">
                                        <span class="px-1.5 py-0.5 rounded font-black text-[9px] uppercase ${propBadgeClass}">${propType}</span>
                                        ${line && line !== 'Moneyline' && String(line).toLowerCase() !== String(propType).toLowerCase() ? `<span class="px-1.5 py-0.5 rounded font-black text-[9px] bg-cyan-950/80 text-cyan-200 border border-cyan-500/30 font-mono">${line}</span>` : ''}
                                    </div>
                                    <span class="text-[9.5px] font-mono text-gray-400">${gameTime}</span>
                                </div>
                                <div class="text-[14px] sm:text-[15px] font-black text-white leading-snug">${cleanMatchup}</div>
                                ${strikeDetails && propType !== 'Moneyline' && strikeDetails.toLowerCase() !== cleanMatchup.toLowerCase() ? `
                                    <div class="text-[10px] text-gray-300 font-mono mt-1.5 pt-1.5 border-t border-white/5 flex items-center gap-1.5">
                                        <span class="text-cyan-400 shrink-0">🎯</span>
                                        <span>${strikeDetails}</span>
                                    </div>
                                ` : ''}
                            </div>

                            <!-- Master Sports Capper Quantitative Conviction Box -->
                            ${capper && capper.grade ? `
                                <div class="bg-gradient-to-br from-[#0a1120] via-[#0b162c] to-[#050b16] p-3.5 rounded-xl border border-amber-500/40 shadow-[0_0_20px_rgba(245,158,11,0.12)] space-y-2.5">
                                    <div class="flex items-center justify-between flex-wrap gap-2">
                                        <div class="flex items-center gap-2">
                                            <span class="px-2.5 py-0.5 rounded font-black text-[11px] tracking-wide ${capper.grade === 'A+' ? 'bg-emerald-500/25 text-emerald-300 border border-emerald-500/60 shadow-[0_0_10px_rgba(16,185,129,0.3)]' : capper.grade === 'A' ? 'bg-amber-500/25 text-amber-300 border border-amber-500/60' : 'bg-cyan-500/25 text-cyan-300 border border-cyan-500/50'}">
                                                ${esc(capper.grade)} ${esc(capper.stars)}
                                            </span>
                                            <span class="text-[10.5px] font-mono font-bold tracking-wider uppercase text-amber-400">
                                                ${esc(capper.tier_label || 'MASTER CAPPER')}
                                            </span>
                                        </div>
                                        <div class="text-right">
                                            <span class="text-[9px] font-mono text-gray-400 uppercase tracking-widest block">Quarter-Kelly</span>
                                            <span class="text-[11px] font-black text-cyan-300 font-mono">${capper.kelly_bankroll_pct != null ? Number(capper.kelly_bankroll_pct).toFixed(1) + '% Kelly' : 'Conservative'}</span>
                                        </div>
                                    </div>

                                    ${capper.conviction_desc ? `<div class="text-[11px] text-gray-300 leading-snug">${esc(capper.conviction_desc)}</div>` : ''}

                                    <!-- Quantitative Edge Matrix Grid -->
                                    <div class="grid grid-cols-3 gap-1.5 pt-1.5 border-t border-white/10 text-center font-mono">
                                        <div class="bg-black/50 p-2 rounded-lg border border-white/5">
                                            <div class="text-[8.5px] uppercase text-gray-400 font-bold">Model Win</div>
                                            <div class="text-[12px] font-black text-emerald-400 mt-0.5">${capper.model_win_pct != null ? Number(capper.model_win_pct).toFixed(1) + '%' : conf + '%'}</div>
                                        </div>
                                        <div class="bg-black/50 p-2 rounded-lg border border-white/5">
                                            <div class="text-[8.5px] uppercase text-gray-400 font-bold">Net EV (Post-Fee)</div>
                                            <div class="text-[12px] font-black ${capper.net_ev_pct >= 5 ? 'text-emerald-400' : capper.net_ev_pct > 0 ? 'text-amber-300' : 'text-gray-400'} mt-0.5">
                                                ${capper.net_ev_pct != null ? (capper.net_ev_pct > 0 ? '+' : '') + Number(capper.net_ev_pct).toFixed(1) + '%' : '—'}
                                            </div>
                                        </div>
                                        <div class="bg-black/50 p-2 rounded-lg border border-white/5">
                                            <div class="text-[8.5px] uppercase text-gray-400 font-bold">Kelly Rec ($1k)</div>
                                            <div class="text-[12px] font-black text-cyan-300 mt-0.5">$${capper.recommended_wager != null ? Number(capper.recommended_wager).toFixed(2) : (capper.kelly_bankroll_pct != null ? (Number(capper.kelly_bankroll_pct) * 10).toFixed(2) : '10.00')}</div>
                                        </div>
                                    </div>

                                    <!-- H2H Matchup & Situational Notes -->
                                    ${(capper.capper_notes && capper.capper_notes.length) ? `
                                        <div class="pt-1.5 border-t border-white/10 space-y-1">
                                            <div class="text-[9px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1">
                                                <span>⚔️ Head-to-Head & Situational Dynamics</span>
                                            </div>
                                            <div class="space-y-1">
                                                ${capper.capper_notes.map(note => `
                                                    <div class="text-[10px] text-gray-200 bg-white/5 p-1.5 rounded border border-white/5 flex items-start gap-1.5 leading-snug">
                                                        <span class="text-amber-400 shrink-0 font-bold">▸</span>
                                                        <span>${esc(note)}</span>
                                                    </div>
                                                `).join('')}
                                            </div>
                                        </div>
                                    ` : ''}
                                </div>
                            ` : ''}

                            <!-- Recommended Pick Hero Box -->
                            <div class="bg-gradient-to-br from-emerald-950/40 via-black/70 to-[#0e1626] p-3 rounded-xl border border-emerald-500/40">
                                <div class="flex items-center justify-between mb-0.5">
                                    <span class="text-[9px] font-bold text-emerald-400 uppercase tracking-widest">${(fullEvt.prop_type === 'Period' || fullEvt.segment || /KXNHL[123]P|KXMLBF5/.test(String(fullEvt.event_ticker || ticker).toUpperCase())) ? '✦ AI full-game lean' : '✦ AI Recommended Pick'}</span>
                                    ${spreadAmount ? `<span class="text-[9px] font-mono text-purple-300 font-bold">Spread: ${spreadAmount}</span>` : (overUnderAmount && /\d/.test(String(overUnderAmount)) ? `<span class="text-[9px] font-mono text-amber-300 font-bold">Line: ${overUnderAmount}</span>` : '')}
                                </div>
                                <div class="text-[16px] font-black text-white leading-tight">${hasAiPickNow ? team : 'No AI pick for this market'}</div>
                            </div>

                            <!-- AI analysis: why this pick (js/sports-trade-details.js) -->
                            ${window.renderSportsAIAnalysis ? window.renderSportsAIAnalysis(data, fullEvt) : ''}
                        </div>

                        <!-- Action Buttons -->
                        <div class="flex flex-col gap-2 mt-4 pt-1 border-t border-white/5">
                            <div class="flex gap-2">
                                ${hasAiPickNow ? `<button onclick="addPredictionToSlip('${ticker}', '${team.replace(/'/g, "\\'")}', '${conf}', '${edge}', 'YES', {prop_type:'${propType}', line:'${line.replace(/'/g, "\\'")}', spread_amount:'${spreadAmount}', over_under_amount:'${overUnderAmount}', strike_details:'${strikeDetails.replace(/'/g, "\\'")}'})" class="flex-1 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white font-black text-[10px] uppercase tracking-wider rounded-lg transition-all active:scale-95 shadow-[0_0_15px_rgba(6,182,212,0.4)] cursor-pointer">
                                    + Add AI Pick
                                </button>` : ''}
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
                const stratParam = window.currentSportsStrategy ? '&strategy=' + encodeURIComponent(window.currentSportsStrategy) : '';
                const token = localStorage.getItem('saas_token') || localStorage.getItem('app_api_token') || '';
                const fetchOpts = {
                    cache: 'no-store',
                    headers: token ? { 'Authorization': `Bearer ${token}` } : {}
                };
                const res = await fetch((window.API_BASE_URL || '') + '/api/engine/sports/events?t=' + Date.now() + sportParam + stratParam, fetchOpts);
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
                if (typeof updateParlayPayoutPreviews === 'function') updateParlayPayoutPreviews();
            } catch (e) {
                if (reqId !== window.__sportsReqId) return;
                window.__sportsLoading = false;
                if (!window.__sportsEventsCache || !window.__sportsEventsCache.length) {
                    container.innerHTML = '<div class="col-span-full text-center text-red-400 text-xs py-6">Failed to load picks: ' + e.message + '</div>';
                } else {
                    renderSportsEvents();
                    if (typeof updateParlayPayoutPreviews === 'function') updateParlayPayoutPreviews();
                }
            }
        }
        async function selectDashboardAsset(asset, isTabSwitch = false) {
            asset = (asset || 'BTC').toUpperCase();
            
            const hasExistingChart = Boolean((lwChart || window.lwChart) && document.querySelector('#lw-chart-container canvas'));
            const hasCachedData = Boolean(window.lastCandle || (window.candlesCache && window.candlesCache[asset]));
            const isSameAsset = (window.currentAsset === asset);

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
                const isSelected = (a === asset);
                btn.className = 'asset-btn shrink-0 py-1 px-2.5 rounded-md text-[11px] font-bold transition-all flex items-center justify-center gap-1 border cursor-pointer ' + 
                    (isSelected ? activeStyles[a] : inactiveStyle);
                if (isSelected) {
                    try { btn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' }); } catch(e) {}
                }
            });

            // Immediately resize existing chart if available
            if (hasExistingChart) {
                requestAnimationFrame(() => {
                    const chart = lwChart || window.lwChart;
                    const container = document.getElementById('lw-chart-container');
                    if (chart && container) {
                        const w = container.clientWidth || container.offsetWidth;
                        const h = container.clientHeight || container.offsetHeight;
                        if (w > 0 && h > 0) {
                            try { chart.applyOptions({ width: w, height: h }); } catch(_) {}
                        }
                        try {
                            if (chart.timeScale) chart.timeScale().fitContent();
                        } catch(_) {}
                    }
                });
            }

            // If switching tabs or if cached data exists for this asset, DO NOT blank HUD or show blocking loader
            if (typeof initSpotWebSocket === 'function') initSpotWebSocket();

            const isFxAsset = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'].includes(asset);
            const assetDecimals = asset === 'USDJPY' ? 3 : (isFxAsset ? 5 : (asset === 'DOGE' ? 4 : 2));
            const assetPrefix = isFxAsset ? '' : '$';

            const skipLoaderAndBlanking = isTabSwitch || (isSameAsset && hasExistingChart && hasCachedData);

            if (!skipLoaderAndBlanking) {
                window.lastCandle = null;
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
                        spotEl.textContent = assetPrefix + Number(knownPrice).toLocaleString(undefined, {minimumFractionDigits: assetDecimals, maximumFractionDigits: assetDecimals});
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
                
                showChartLoader();
                try {
                    await Promise.allSettled([
                        fetchChartData(true),
                        fetchKalshiData(true),
                        fetchLiveBids()
                    ]);
                } finally {
                    hideChartLoader();
                }
            } else {
                // Smooth background refresh without blocking spinner or blanking HUD
                const spotEl = document.getElementById('exec-spot');
                if (spotEl) {
                    const knownPrice = window.assetSpotPrices ? window.assetSpotPrices[asset] : null;
                    if (knownPrice && isFinite(knownPrice) && knownPrice > 0) {
                        spotEl.textContent = assetPrefix + Number(knownPrice).toLocaleString(undefined, {minimumFractionDigits: assetDecimals, maximumFractionDigits: assetDecimals});
                    }
                }
                Promise.allSettled([
                    fetchChartData(false),
                    fetchKalshiData(false),
                    fetchLiveBids()
                ]).catch(err => console.warn('[Chart] background refresh warning', err));
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
                    const isFxChart = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'].includes(reqAsset);
                    const chartPrec = reqAsset === 'USDJPY' ? 3 : (isFxChart ? 5 : (reqAsset === 'DOGE' ? 4 : 2));
                    const chartMinMove = Number((1 / Math.pow(10, chartPrec)).toFixed(chartPrec));
                    const pFmt = { type: 'price', precision: chartPrec, minMove: chartMinMove };
                    if (candleSeries) candleSeries.applyOptions({ priceFormat: pFmt });
                    if (lineSeries) lineSeries.applyOptions({ priceFormat: pFmt });

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
                    window.candlesCache = window.candlesCache || {};
                    window.candlesCache[reqAsset] = cleanCandles;

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
            const isInvestment = window.__isInvestmentTrade ? window.__isInvestmentTrade(t) : false;
            let invMeta = t.metadata || {};
            if (typeof invMeta === 'string') {
                try { invMeta = JSON.parse(invMeta); } catch(_) { invMeta = {}; }
            }
            const invVehicle = isInvestment ? String(t.vehicle || invMeta.vehicle || 'STOCK').toUpperCase() : null;
            const invSymbol = isInvestment ? String(t.symbol || invMeta.symbol || String(t.ticker || '').split('_')[0] || 'SPY').toUpperCase() : null;
            const invOptType = isInvestment && invVehicle === 'OPTION' ? String(t.option_type || invMeta.option_type || 'CALL').toUpperCase() : null;

            const side = String(t.side || t.direction || (isInvestment ? "BUY" : "YES")).toUpperCase();
            const isYes = side === "YES" || side === "BUY";
            const sideBadge = document.getElementById('tdm-side-badge');
            if (sideBadge) {
                if (isInvestment) {
                    sideBadge.textContent = invVehicle === 'OPTION' ? `${side} ${invOptType}` : `${side} SHARES`;
                } else {
                    sideBadge.textContent = isYes ? "BID YES" : "BID NO";
                }
                sideBadge.className = isYes
                    ? "px-2.5 py-1 rounded-lg text-xs font-black uppercase tracking-wider bg-emerald-500/20 text-emerald-400 border border-emerald-500/35"
                    : "px-2.5 py-1 rounded-lg text-xs font-black uppercase tracking-wider bg-rose-500/20 text-rose-400 border border-rose-500/35";
            }

            // Ticker & Strike
            const ticker = t.ticker || "KXBTC15M";
            let rawStrike = t.strike || invMeta.strike || t.strike_price || t.target_price || t.target;
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

            const isSport = !isInvestment && window.__isSportTrade ? window.__isSportTrade(t) : false;
            const sInfo = isSport && window.__getSportInfo ? window.__getSportInfo(t) : null;

            const assetType = isInvestment ? `📈 ROBINHOOD ${invVehicle}` : (isSport && sInfo ? sInfo.sport : String(t.asset || (['BTC','ETH','GOLD','EURUSD','GBPUSD','USDJPY','AUDUSD','NDQ','SOL','DOGE'].find(x => ticker.includes(x)) || 'BTC')).toUpperCase());
            const tickerEl = document.getElementById('tdm-ticker');
            if (isSport && sInfo && window.__fetchGameInfo) window.__fetchGameInfo([ticker]);
            if (tickerEl) tickerEl.textContent = isInvestment ? `${assetType} · ${invSymbol}` : (isSport && sInfo ? `${sInfo.icon} ${sInfo.sport} · ${(window.__gameInfo && window.__gameInfo[ticker] && window.__gameInfo[ticker].title) ? window.__gameInfoLabel(ticker) : ticker}` : `${assetType} · ${ticker}`);
            const strikeTitleEl = document.getElementById('tdm-strike-title');
            if (strikeTitleEl) {
                if (isInvestment) {
                    if (invVehicle === 'OPTION') {
                        const expStr = t.expiration || invMeta.expiration || '';
                        strikeTitleEl.textContent = `${invSymbol} $${strikeVal || '--'} ${invOptType}${expStr ? ' · Exp ' + expStr : ''}`;
                    } else {
                        strikeTitleEl.textContent = `${invSymbol} Equity Shares (${side})`;
                    }
                } else if (isSport && sInfo) {
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
            const count = Number(t.count || t.size || 1) || 1;
            const entryPriceNum = parseFloat(t.entry_price || 0.50);
            const exitPriceNum = (!isOpen && t.exit_price !== undefined && t.exit_price !== null) ? parseFloat(t.exit_price) : null;
            const curMarkRaw = t.current_bid ?? t.current_price ?? t.cur_price ?? t.exit_bid;
            const curMarkNum = (curMarkRaw !== undefined && curMarkRaw !== null && isFinite(parseFloat(curMarkRaw))) ? parseFloat(curMarkRaw) : null;
            const multiplier = (isInvestment && invVehicle === 'OPTION') ? 100 : 1;
            const totalCost = count * entryPriceNum * multiplier;
            const fmtCents = (p) => {
                const c = p * 100;
                return (Math.abs(c - Math.round(c)) > 0.04) ? c.toFixed(1) : String(Math.round(c));
            };

            const entryPriceEl = document.getElementById('tdm-entry-price');
            if (entryPriceEl) {
                if (isInvestment) {
                    entryPriceEl.textContent = `$${entryPriceNum.toFixed(2)}${invVehicle === 'OPTION' ? ' / contract' : ' / share'}`;
                } else {
                    entryPriceEl.textContent = `${fmtCents(entryPriceNum)}¢ ($${entryPriceNum.toFixed(entryPriceNum < 0.1 ? 4 : 2)})`;
                }
            }

            const exitPriceEl = document.getElementById('tdm-exit-price');
            if (exitPriceEl) {
                if (isOpen) {
                    if (isInvestment) {
                        exitPriceEl.textContent = curMarkNum !== null ? `Live Mark ($${curMarkNum.toFixed(2)})` : 'Live Mark';
                    } else {
                        exitPriceEl.textContent = curMarkNum !== null ? `Active Mark (${fmtCents(curMarkNum)}¢)` : 'Active Mark';
                    }
                } else if (exitPriceNum !== null) {
                    exitPriceEl.textContent = isInvestment ? `$${exitPriceNum.toFixed(2)}` : `${fmtCents(exitPriceNum)}¢ ($${exitPriceNum.toFixed(exitPriceNum < 0.1 ? 4 : 2)})`;
                } else {
                    exitPriceEl.textContent = 'Settled';
                }
            }

            const contractsEl = document.getElementById('tdm-contracts');
            if (contractsEl) {
                if (isInvestment && invVehicle === 'STOCK') {
                    contractsEl.textContent = `${count} ${count === 1 ? 'Share' : 'Shares'}`;
                } else {
                    contractsEl.textContent = `${count} ${count === 1 ? 'Contract' : 'Contracts'}`;
                }
            }

            const totalCostEl = document.getElementById('tdm-total-cost');
            if (totalCostEl) totalCostEl.textContent = `$${totalCost.toFixed(2)}`;

            // Hero Outcome Card
            const heroCard = document.getElementById('tdm-hero-card');
            if (heroCard) {
                const closeHandler = isInvestment
                    ? `closeInvestmentPosition('${t.id}'); closeTradeDetailsModal();`
                    : `closeTrade('${t.id}', 'MANUAL_CLOSE'); closeTradeDetailsModal();`;
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
                            
                                <button onclick="${closeHandler}" class="mt-2 sm:mt-2.5 px-3 py-1.5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 rounded-xl text-[10px] font-bold uppercase tracking-wider flex items-center justify-center gap-1.5 transition-all active:scale-95 cursor-pointer"><span>✕</span> Close / Take Profit</button></div>
                        </div>
                        <div class="sm:text-right bg-black/40 p-2.5 rounded-xl border border-white/5">
                            <span class="text-[9px] font-bold uppercase tracking-wider text-gray-400 block mb-0.5">Direction Target</span>
                            <span class="text-xs font-black ${isYes ? 'text-emerald-400' : 'text-rose-400'}">${isInvestment ? (invVehicle === 'OPTION' ? `${invSymbol} $${strikeVal} ${invOptType}` : `${side} ${count} sh ${invSymbol}`) : (isSport && sInfo ? (sInfo.strikeDetails ? `${side} · ${sInfo.strikeDetails}` : `${side} (${sInfo.team}${sInfo.line ? ' ' + sInfo.line : ''})`) : (isYes ? (strikeVal ? 'YES (Above $' + strikeVal + ')' : 'YES (Above Target)') : (strikeVal ? 'NO (Below $' + strikeVal + ')' : 'NO (Below Target)')))}</span>
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
                            <span class="text-xs font-black text-emerald-400">${isInvestment ? `Closed at $${exitPriceNum !== null ? exitPriceNum.toFixed(2) : entryPriceNum.toFixed(2)}` : (isSport && sInfo ? (sInfo.strikeDetails ? `Target Met: ${sInfo.strikeDetails}` : `Target Met (${sInfo.team} Won)`) : `Target Met (${isYes ? 'Closed Above' : 'Closed Below'} Strike)`)}</span>
                        </div>
                    `;
                } else if (isLoss) {
                    const lossPct = totalCost > 0 ? (Math.abs(pnlVal) / totalCost) * 100 : 100;
                    heroCard.className = "relative overflow-hidden rounded-2xl p-4 sm:p-5 border border-rose-500/30 bg-gradient-to-br from-rose-950/30 via-[#0d1424] to-black flex flex-col sm:flex-row justify-between sm:items-center gap-3";
                    heroCard.innerHTML = `
                        <div class="flex items-center gap-3.5">
                            <div class="w-12 h-12 rounded-2xl bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-400 text-xl font-black shadow-[0_0_15px_rgba(244,63,94,0.2)]">
                                ✕
                            </div>
                            <div>
                                <div class="text-[10px] font-bold text-rose-400 uppercase tracking-widest">Loss Incurred</div>
                                <div class="text-2xl font-black text-rose-400 tabular-nums">-$${Math.abs(pnlVal).toFixed(2)}</div>
                                <div class="text-[10px] text-rose-300/80 font-mono font-bold">-${lossPct.toFixed(1)}% on Capital Risked ($${totalCost.toFixed(2)})</div>
                            </div>
                        </div>
                        <div class="sm:text-right bg-black/40 p-2.5 rounded-xl border border-white/5">
                            <span class="text-[9px] font-bold uppercase tracking-wider text-gray-400 block mb-0.5">Exit Outcome</span>
                            <span class="text-xs font-black text-rose-400">${t.exit_reason ? t.exit_reason.replace(/_/g, ' ') : 'Closed Position'}</span>
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
                if (isInvestment) {
                    const symLabel = invMeta.symbol || t.symbol || (t.ticker || '').split('_')[0] || 'Equity';
                    const isOpt = invVehicle === 'OPTION';
                    const optDesc = isOpt ? `${symLabel} $${invMeta.strike || t.strike || ''} ${invMeta.option_type || t.option_type || 'CALL'} (${invMeta.expiration || t.expiration || '0DTE/Weekly'})` : `${symLabel} Common Shares`;
                    const qtyUnit = isOpt ? `${count} option contract${count === 1 ? '' : 's'}` : `${count} share${count === 1 ? '' : 's'}`;
                    const tpInfo = (t.tp_price || invMeta.tp_pct) ? ` with Take-Profit (${t.tp_price ? '$' + Number(t.tp_price).toFixed(2) : (invMeta.tp_pct + '%')}) and Stop-Loss (${t.sl_price ? '$' + Number(t.sl_price).toFixed(2) : ((invMeta.sl_pct || 1.0) + '%')}) brackets` : '';
                    if (isManual) {
                        summaryEl.innerHTML = `You manually executed a <strong>${side}</strong> order for <strong>${qtyUnit}</strong> of <strong>${optDesc}</strong> at <strong>$${entryPriceNum.toFixed(2)}</strong> ($${totalCost.toFixed(2)} notional cost)${tpInfo} on Robinhood.`;
                    } else {
                        let outcomePart = '';
                        if (isOpen) {
                            outcomePart = `Position is currently <strong>active</strong> and monitored by the Robinhood Intraday Risk & Bracket Manager.`;
                        } else if (isWin) {
                            outcomePart = `The position closed in profit at <strong>$${exitPriceNum !== null ? exitPriceNum.toFixed(2) : entryPriceNum.toFixed(2)}</strong>, realizing <strong>+$${pnlVal.toFixed(2)}</strong>.`;
                        } else if (isLoss) {
                            outcomePart = `The position exited at <strong>$${exitPriceNum !== null ? exitPriceNum.toFixed(2) : entryPriceNum.toFixed(2)}</strong> (${t.exit_reason || 'Stop-Loss / Risk Guard'}), realizing <strong>-$${Math.abs(pnlVal).toFixed(2)}</strong>.`;
                        } else {
                            outcomePart = `The position closed flat.`;
                        }
                        summaryEl.innerHTML = `The 4-Agent Robinhood Desk executed a <strong>${side}</strong> order for <strong>${qtyUnit}</strong> of <strong>${optDesc}</strong> at <strong>$${entryPriceNum.toFixed(2)}</strong> ($${totalCost.toFixed(2)} total cost)${tpInfo} using the <strong>${rawStyle}</strong> strategy with <strong>${confVal.toFixed(1)}% conviction</strong>. ${outcomePart}`;
                    }
                } else if (isSport && sInfo) {
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

                const flashBadge = document.getElementById('settings-updates-flash-badge');
                if (unreadList.length > 0 && latestUpdate) {
                    if (bellDot) bellDot.classList.remove('hidden');
                    if (bellPulse) bellPulse.classList.remove('hidden');
                    if (settingsBtnDot) settingsBtnDot.classList.remove('hidden');
                    if (flashBadge) flashBadge.classList.remove('hidden');

                    const dismissedKey = 'kalshi_dismissed_update_' + latestUpdate.id;
                    if (localStorage.getItem(dismissedKey) !== 'true') {
                        setTimeout(() => {
                            showUpdateModal(latestUpdate);
                        }, 750);
                    }
                } else {
                    if (bellDot) bellDot.classList.add('hidden');
                    if (bellPulse) bellPulse.classList.add('hidden');
                    if (flashBadge) flashBadge.classList.add('hidden');
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
            const flashBadge = document.getElementById('settings-updates-flash-badge');
            if (flashBadge) flashBadge.classList.add('hidden');

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
                if (typeof loadDashboard === 'function') promises.push(loadDashboard(true));
                if (typeof refreshWalletBalances === 'function') promises.push(refreshWalletBalances());
                if (window.currentUniverse === 'SPORTS') {
                    if (typeof loadSportsEvents === 'function') {
                        promises.push(loadSportsEvents(window.sportsFilter));
                    }
                } else if (window.currentUniverse === 'INVESTMENTS') {
                    if (typeof fetchInvestmentsFeed === 'function') {
                        promises.push(fetchInvestmentsFeed());
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

        // Game / match name + start time for sports positions (replaces the raw Kalshi ticker)
        window.__gameInfo = window.__gameInfo || {};
        window.__gameInfoPending = window.__gameInfoPending || {};

        window.__parseTickerSchedule = function(tk) {
            if (!tk) return null;
            const str = String(tk).toUpperCase();
            const MONTH_MAP = { JAN: 0, FEB: 1, MAR: 2, APR: 3, MAY: 4, JUN: 5, JUL: 6, AUG: 7, SEP: 8, OCT: 9, NOV: 10, DEC: 11 };
            // Example: KXWTAMATCH-26OCT11BOUSHN-SHN or KXNFLGAME-26OCT11CLENYJ
            const m = str.match(/-(\d{2})([A-Z]{3})(\d{2})/i);
            if (m) {
                const yr = 2000 + parseInt(m[1], 10);
                const mo = MONTH_MAP[m[2].toUpperCase()];
                const da = parseInt(m[3], 10);
                if (mo != null && !isNaN(da)) {
                    return new Date(Date.UTC(yr, mo, da, 23, 0, 0));
                }
            }
            return null;
        };

        window.__formatScheduleCountdown = function(dateObj, statusStr) {
            if (!dateObj || isNaN(dateObj.getTime())) return '';
            const now = new Date();
            const tm = new Date(now); tm.setDate(now.getDate() + 1);
            let day = dateObj.toDateString() === now.toDateString() ? 'Today'
                : dateObj.toDateString() === tm.toDateString() ? 'Tomorrow'
                : dateObj.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
            
            const hours = dateObj.getHours();
            const minutes = dateObj.getMinutes();
            const hasExactTime = !(hours === 0 && minutes === 0) && !(hours === 19 && minutes === 0 && dateObj.toTimeString().includes('00:00:00'));
            const timeStr = hasExactTime ? dateObj.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : '';
            const whenStr = timeStr ? (day + ' ' + timeStr + ' ET') : day;

            const diffMs = dateObj.getTime() - now.getTime();
            const diffSec = Math.floor(diffMs / 1000);
            let countdown = '';
            const st = String(statusStr || '').toLowerCase();

            if (st.includes('live') || st.includes('progress') || (diffSec < 0 && diffSec > -10800 && hasExactTime)) {
                countdown = '· LIVE';
            } else if (st.includes('final') || st.includes('closed') || (diffSec <= -10800 && hasExactTime)) {
                countdown = '· Final';
            } else if (diffSec > 0) {
                const min = Math.floor(diffSec / 60);
                const hrs = Math.floor(min / 60);
                if (hrs >= 24) {
                    const days = Math.floor(hrs / 24);
                    countdown = '(in ' + days + 'd)';
                } else if (hrs > 0) {
                    countdown = '(in ' + hrs + 'h)';
                } else if (min > 0) {
                    countdown = '(in ' + min + 'm)';
                }
            }
            return [whenStr, countdown].filter(Boolean).join(' ');
        };

        window.__gameInfoLabel = function(tOrTicker) {
            const t = (tOrTicker && typeof tOrTicker === 'object') ? tOrTicker : null;
            const ticker = t ? (t.ticker || '') : String(tOrTicker || '');
            const gi = window.__gameInfo[ticker];
            
            let startDate = null;
            let status = '';
            let title = '';
            let extra = '';

            if (gi) {
                if (gi.start) {
                    const parsed = new Date(gi.start);
                    if (!isNaN(parsed.getTime())) startDate = parsed;
                }
                status = gi.status || '';
                title = gi.title || '';
                extra = gi.extra || '';
            }

            if (t) {
                let meta = t.metadata;
                if (typeof meta === 'string') {
                    try { meta = JSON.parse(meta); } catch(e) { meta = {}; }
                }
                let rj = t.raw_json;
                if (typeof rj === 'string') {
                    try { rj = JSON.parse(rj); } catch(e) { rj = {}; }
                }
                if (!title) {
                    const si = window.__getSportInfo ? window.__getSportInfo(t) : null;
                    title = (t.matchup || (meta && meta.matchup) || (rj && (rj.matchup || rj.strike_details || rj.market_title)) || (si && si.matchup) || '').trim();
                }
                if (!startDate) {
                    const rawDate = (meta && (meta.start_time || meta.game_time || meta.date || meta.commence_time || meta.start_label)) ||
                                    (rj && (rj.start_time || rj.game_time || rj.date || rj.commence_time || rj.start_label)) ||
                                    t.game_time || t.event_date || t.commence_time;
                    if (rawDate) {
                        const parsed = new Date(rawDate);
                        if (!isNaN(parsed.getTime())) startDate = parsed;
                    }
                }
            }
            if (!startDate) {
                startDate = window.__parseTickerSchedule(ticker);
            }

            const scheduleStr = window.__formatScheduleCountdown(startDate, status);

            const parts = [];
            if (title) parts.push(title);
            else if (extra) parts.push(extra);

            if (scheduleStr) {
                parts.push(scheduleStr);
            } else if (gi) {
                parts.push('Scheduled');
            } else {
                parts.push('Checking game time…');
            }

            return parts.join(' · ');
        };
        window.__fetchGameInfo = function(tickers) {
            const need = tickers.filter(tk => tk && !window.__gameInfo[tk] && !window.__gameInfoPending[tk]);
            if (!need.length) return;
            need.forEach(tk => { window.__gameInfoPending[tk] = Date.now(); });
            fetch((window.API_BASE_URL || '') + '/api/public/game_info?tickers=' + encodeURIComponent(need.join(',')))
                .then(r => r.json())
                .then(j => {
                    Object.assign(window.__gameInfo, (j && j.games) || {});
                    need.forEach(tk => { if (!window.__gameInfo[tk]) window.__gameInfo[tk] = { title: '', start: null, extra: '' }; });
                    if (typeof updateActivePositionHud === 'function' && window.lastDashboardStats) updateActivePositionHud(window.lastDashboardStats);
                    if (typeof window.renderTradesContainer === 'function' && window.lastDashboardStats) window.renderTradesContainer(window.lastDashboardStats);
                })
                .catch(() => { need.forEach(tk => { delete window.__gameInfoPending[tk]; }); });
        };

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
                const isSportsTicker = /^KX(NFL|MLB|NBA|NHL|NCAAF|NCAAB|WNBA|SOC|UFC|MMA|TEN|NPB|KBO|GAME|ATP|MVECROSSCATEGORY|MVE)/.test(tk) ||
                                       /^(NFL|MLB|NBA|NHL|NCAAF|NCAAB|WNBA|SOC|UFC|MMA|TEN)-/.test(tk) ||
                                       tk.startsWith('KALSHI-') ||
                                       tk.includes('KXMVECROSSCATEGORY') ||
                                       ['NFL','MLB','NBA','NCAAF','NCAAB','WNBA','NPB','KBO','NPB/KBO','NPB_KBO','NHL','SOC','UFC','TEN','MMA','SPORTS','MULTIVARIATE_COMBO'].includes(a);
                const isSportsStyle = String(t.trading_style || '').toUpperCase().startsWith('SPORTS') || String(t.trading_style || '').toUpperCase().includes('COMBO') || String(t.trading_style || '').toUpperCase() === 'SPORTS_AI';
                return isSportsStyle || hasSportProp || isSportsTicker;
            });
            const __inSports = window.currentUniverse === 'SPORTS';
            const __inInvestments = window.currentUniverse === 'INVESTMENTS';
            if (__inInvestments) {
                container.style.display = 'none';
                container.classList.add('hidden');
                return;
            }
            const isInvTradeFn = window.__isInvestmentTrade || (() => false);
            const activeMode = String(s.trading_mode || currentMode || 'PAPER').toUpperCase();
            const openTrades = (s.recent_trades || [])
                .filter(t => String(t.status || '').toUpperCase() === 'OPEN')
                .filter(t => String(t.mode || 'PAPER').toUpperCase() === activeMode)
                .filter(t => __inSports ? (__isSportTrade(t) && !isInvTradeFn(t)) : (!__isSportTrade(t) && !isInvTradeFn(t)));
            
            // Audio trigger on newly opened trade
            if (openTrades.length > previousOpenTradeCount && previousOpenTradeCount === 0) {
                soundEngine.play('order_fill');
            }
            previousOpenTradeCount = openTrades.length;

            if (openTrades.length === 0) {
                container.innerHTML = `
                    <div class="bg-[#0e1626]/95 border border-cyan-500/20 rounded-2xl px-4 py-3 shadow-md flex items-center justify-between">
                        <div class="flex items-center gap-2.5">
                            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                            <span class="text-[10px] font-bold uppercase tracking-wider text-gray-400">Position Scanner:</span>
                            <span class="text-[10px] font-mono text-emerald-400 font-bold">${__inSports ? 'READY · Watching AI Picks' : 'READY · Bot Scanning Active'}</span>
                        </div>
                        <span class="text-[9px] font-mono text-gray-400 uppercase tracking-widest">${__inSports ? 'SPORTS · NFL · MLB · NHL · SOCCER · UFC · TENNIS · NPB/KBO' : (s.trading_style || 'AUTO') + ' · CRYPTO ASSETS (BTC, ETH, SOL, DOGE)'}</span>
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
                const count = Number(t.count || t.size || 1) || 1;
                const entryPriceDollars = t.entry_price != null ? parseFloat(t.entry_price) : 0.50;
                const entryCentsRaw = entryPriceDollars * 100;
                const entryPrice = (Math.abs(entryCentsRaw - Math.round(entryCentsRaw)) > 0.04) ? entryCentsRaw.toFixed(1) : Math.round(entryCentsRaw);

                const isSport = window.__isSportTrade ? window.__isSportTrade(t) : false;
                const sportInfo = isSport && window.__getSportInfo ? window.__getSportInfo(t) : null;
                // User requested format: "YES BTC 11 Contracts @ 50c" or "YES Team 11 Contracts @ 50c" for sports
                const tradeLabel = isSport && sportInfo
                    ? `${dir} ${sportInfo.team} · ${count} Contracts @ ${entryPrice}¢`
                    : `${dir} ${asset} ${count} Contracts @ ${entryPrice}¢`;

                // Live PnL - dynamic real-time mark calculation when live bids or spot are available
                let estPnl = t.live_pnl !== undefined ? Number(t.live_pnl) : (t.pnl_dollars !== undefined ? Number(t.pnl_dollars) : 0);
                
                // If this is a financial position and we have fresh Kalshi bids for this asset
                if (!isSport && window.assetBids && window.assetBids[asset]) {
                    const bids = window.assetBids[asset];
                    const activeBid = isYes ? bids.yes_bid : bids.no_bid;
                    if (activeBid !== undefined && activeBid > 0 && activeBid < 100) {
                        const curPriceDollars = activeBid / 100;
                        estPnl = (curPriceDollars - entryPriceDollars) * count;
                        t.live_pnl = estPnl;
                    }
                } else if (!isSport && (asset === (window.currentAsset || 'BTC').toUpperCase())) {
                    const activeBid = isYes ? window.lastYesBid : window.lastNoBid;
                    if (activeBid !== undefined && activeBid > 0 && activeBid < 100) {
                        const curPriceDollars = activeBid / 100;
                        estPnl = (curPriceDollars - entryPriceDollars) * count;
                        t.live_pnl = estPnl;
                    }
                }
                
                totalOpenPnl += estPnl;
                const pnlColor = estPnl >= 0 ? 'text-emerald-400' : 'text-rose-400';
                const pnlStr = (estPnl >= 0 ? '+$' : '-$') + Math.abs(estPnl).toFixed(2);
                const costBasis = entryPriceDollars * count;
                const pnlPct = costBasis > 0 ? ((estPnl / costBasis) * 100).toFixed(1) : '0.0';

                // Strike & distance
                let spot = (window.assetSpotPrices && window.assetSpotPrices[asset]) ? window.assetSpotPrices[asset] : 0;
                if (!spot || spot <= 0) {
                    if (asset === 'BTC') spot = window.lastBtcPrice || window.lastSpotPrice || 0;
                    else if (asset === 'ETH') spot = window.lastEthPrice || 0;
                    else if (asset === 'GOLD') spot = window.lastGoldPrice || 0;
                    else spot = window.lastSpotPrice || 0;
                }

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
                                    ? `<span class="text-[9px] font-black px-1.5 py-0.5 rounded uppercase tracking-wider border bg-cyan-500/20 text-cyan-300 border-cyan-500/40">${sportInfo.icon} ${sportInfo.sport}</span> <span class="text-gray-300 ml-1 font-sans">${window.__gameInfoLabel ? window.__gameInfoLabel(t) : ''}</span>`
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

            if (window.__fetchGameInfo) window.__fetchGameInfo(sortedOpen.filter(x => window.__isSportTrade && window.__isSportTrade(x)).map(x => x.ticker));

            const totalColor = totalOpenPnl >= 0 ? 'text-emerald-400' : 'text-rose-400';
            const totalStr = (totalOpenPnl >= 0 ? '+$' : '-$') + Math.abs(totalOpenPnl).toFixed(2);

            container.innerHTML = `
                <div class="relative bg-[#0c1220]/95 border border-cyan-500/20 rounded-2xl shadow-md overflow-hidden">
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
                const token = localStorage.getItem('saas_token') || '';
                const headers = token ? { 'Authorization': 'Bearer ' + token } : {};
                const res = await fetch((window.API_BASE_URL||'')+'/api/engine/analytics/equity', {
                    headers: headers
                });
                if (!res.ok) throw new Error('Failed to fetch equity');
                const data = await res.json();
                const eq = (data && data.points) ? data : (data.equity || data || {});
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

        // ── Quant Lab & Strategy Graveyard Engine Script ──
        window.currentQuantLabTab = 'graveyard';

        window.openQuantLabModal = function(e) {
            if (e && e.stopPropagation) e.stopPropagation();
            document.getElementById('profileDropdown')?.classList.add('hidden');
            const uDd = document.getElementById('universe-dropdown');
            if (uDd) {
                uDd.classList.add('opacity-0', 'scale-95');
                setTimeout(() => uDd.classList.add('hidden'), 150);
            }
            const modal = document.getElementById('quant-lab-modal');
            if (modal) {
                modal.classList.remove('hidden');
                modal.style.display = 'flex';
            }
            document.body.style.overflow = 'hidden';
            window.fetchQuantLabData();
        };

        window.closeQuantLabModal = function(e) {
            if (e && e.stopPropagation) e.stopPropagation();
            const modal = document.getElementById('quant-lab-modal');
            if (modal) {
                modal.classList.add('hidden');
                modal.style.display = 'none';
            }
            document.body.style.overflow = 'auto';
        };

        window.switchQuantLabTab = function(tab) {
            window.currentQuantLabTab = tab;
            ['graveyard', 'incubator', 'registry'].forEach(t => {
                const btn = document.getElementById(`tab-btn-ql-${t}`);
                const panel = document.getElementById(`ql-panel-${t}`);
                if (t === tab) {
                    btn?.classList.add('border-purple-500', 'text-purple-300');
                    btn?.classList.remove('border-transparent', 'text-gray-400');
                    panel?.classList.remove('hidden');
                } else {
                    btn?.classList.remove('border-purple-500', 'text-purple-300');
                    btn?.classList.add('border-transparent', 'text-gray-400');
                    panel?.classList.add('hidden');
                }
            });
        };

        window.fetchQuantLabData = async function() {
            try {
                const res = await fetch((window.API_BASE_URL || '') + '/api/quant-lab/overview');
                if (!res.ok) throw new Error("Could not load Quant Lab data");
                const data = await res.json();

                const failEl = document.getElementById('ql-failures-count');
                if (failEl) failEl.innerText = data.stats?.total_failures || 0;
                const incEl = document.getElementById('ql-incubating-count');
                if (incEl) incEl.innerText = data.incubating_count || 0;
                const gradEl = document.getElementById('ql-graduated-count');
                if (gradEl) gradEl.innerText = data.graduated_count || 0;

                window.renderQuantLabGraveyard(data.recent_graveyard || []);
                window.renderQuantLabIncubator(data.incubating || []);
                window.renderQuantLabRegistry(data.recent_strategies || []);
            } catch (e) {
                console.error("[QuantLab] Error fetching data:", e);
            }
        };

        window.renderQuantLabGraveyard = function(entries) {
            const container = document.getElementById('ql-graveyard-list');
            if (!container) return;
            if (!entries || entries.length === 0) {
                container.innerHTML = '<div class="text-center py-8 text-xs text-gray-500 font-mono">Strategy Graveyard is clean. No failures logged yet.</div>';
                return;
            }

            container.innerHTML = entries.map(e => `
                <div class="bg-[#121829] border border-rose-500/20 rounded-xl p-3.5 space-y-2 hover:border-rose-500/40 transition-all">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-black text-white">${e.name || 'Unnamed Strategy'}</span>
                            <span class="px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider bg-rose-500/15 text-rose-400 border border-rose-500/30">
                                ${e.failure_stage || 'FAILED'}
                            </span>
                            <span class="px-1.5 py-0.5 rounded text-[8px] font-mono text-gray-400 bg-white/5">
                                ${e.asset || 'BTC'} ${e.target_interval || '15m'}
                            </span>
                        </div>
                        <span class="text-[9px] font-mono text-gray-500">${e.created_at || ''}</span>
                    </div>
                    <div class="text-[11px] text-gray-300">
                        <span class="text-gray-500 font-bold uppercase text-[9px] tracking-wider block mb-0.5">Post-Mortem Breakdown:</span>
                        ${e.post_mortem_summary || 'No breakdown recorded'}
                    </div>
                    <div class="bg-black/40 border border-white/5 rounded-lg p-2.5 text-[11px] text-amber-300/90 font-mono">
                        <span class="text-amber-500 font-bold uppercase text-[9px] tracking-wider block mb-0.5">🛡️ Synthesized Defensive Rule (AI Never Repeats):</span>
                        ${e.negative_rule || 'No negative rule'}
                    </div>
                </div>
            `).join('');
        };

        window.renderQuantLabIncubator = function(strategies) {
            const container = document.getElementById('ql-incubator-list');
            if (!container) return;
            if (!strategies || strategies.length === 0) {
                container.innerHTML = '<div class="text-center py-8 text-xs text-gray-500 font-mono">No strategies currently in forward incubation. Run a research cycle to discover and incubate new alphas.</div>';
                return;
            }

            container.innerHTML = strategies.map(s => {
                const tradesList = Array.isArray(s.trades) ? s.trades : [];
                const tradesRows = tradesList.length > 0 ? tradesList.map(t => {
                    const isWin = t.pnl > 0;
                    const pnlColor = isWin ? 'text-emerald-400' : (t.pnl < 0 ? 'text-rose-400' : 'text-gray-400');
                    const pnlStr = t.status === 'SETTLED' ? ((t.pnl >= 0 ? '+$' : '-$') + Math.abs(t.pnl).toFixed(2)) : 'OPEN';
                    return `
                        <div class="flex items-center justify-between py-1.5 px-2 bg-black/40 rounded border border-white/5 font-mono text-[10px]">
                            <div class="flex items-center gap-1.5 truncate min-w-0">
                                <span class="px-1 py-0.5 rounded text-[8px] font-black ${t.side === 'YES' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'}">${t.side}</span>
                                <span class="text-gray-300 truncate font-semibold">${t.ticker}</span>
                                <span class="text-gray-500">@ $${parseFloat(t.entry_price).toFixed(2)}</span>
                            </div>
                            <div class="flex items-center gap-2 shrink-0 ml-2">
                                <span class="text-[9px] text-gray-500 hidden sm:inline">${t.created_at ? t.created_at.split(' ').slice(1, 3).join(' ') : ''}</span>
                                <span class="font-bold tabular-nums ${pnlColor}">${pnlStr}</span>
                            </div>
                        </div>
                    `;
                }).join('') : '<div class="text-[10px] text-gray-500 font-mono py-1 text-center">No trades recorded yet. Waiting for market setup.</div>';

                return `
                <div class="bg-[#121829] border border-amber-500/20 rounded-xl p-3.5 space-y-2.5 hover:border-amber-500/40 transition-all">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-black text-white">${s.name}</span>
                            <span class="px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider bg-amber-500/15 text-amber-400 border border-amber-500/30">
                                FORWARD INCUBATING
                            </span>
                            <span class="px-1.5 py-0.5 rounded text-[8px] font-mono text-gray-400 bg-white/5">
                                ${s.asset}
                            </span>
                        </div>
                        <button onclick="promoteQuantLabStrategy('${s.strategy_id}')" class="px-2.5 py-1 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 rounded text-[9px] font-bold uppercase tracking-wider border border-emerald-500/40 transition-all cursor-pointer">
                            Promote to Live
                        </button>
                    </div>
                    <div class="grid grid-cols-4 gap-2 text-center bg-black/30 rounded-lg p-2 border border-white/5">
                        <div>
                            <span class="text-[8px] font-bold text-gray-500 uppercase tracking-wider block">Trades</span>
                            <span class="text-xs font-black text-white tabular-nums">${s.trades_count || 0}</span>
                        </div>
                        <div>
                            <span class="text-[8px] font-bold text-gray-500 uppercase tracking-wider block">Win Rate</span>
                            <span class="text-xs font-black text-emerald-400 tabular-nums">${s.trades_count > 0 ? ((s.wins_count / s.trades_count) * 100).toFixed(1) + '%' : '--%'}</span>
                        </div>
                        <div>
                            <span class="text-[8px] font-bold text-gray-500 uppercase tracking-wider block">Forward PnL</span>
                            <span class="text-xs font-black ${s.total_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'} tabular-nums">${(s.total_pnl >= 0 ? '+$' : '-$') + Math.abs(s.total_pnl || 0).toFixed(2)}</span>
                        </div>
                        <div>
                            <span class="text-[8px] font-bold text-gray-500 uppercase tracking-wider block">Max DD</span>
                            <span class="text-xs font-black text-amber-400 tabular-nums">${((s.max_drawdown || 0) * 100).toFixed(1)}%</span>
                        </div>
                    </div>

                    <!-- Expandable Forward Execution Log -->
                    <details class="group bg-black/20 rounded-lg border border-white/5 overflow-hidden">
                        <summary class="flex items-center justify-between px-3 py-2 text-[10px] font-mono text-gray-400 cursor-pointer hover:text-white select-none transition-colors">
                            <span class="flex items-center gap-1.5 font-bold uppercase tracking-wider text-amber-400/90">
                                <span>⚡</span> Forward Paper Trades (${tradesList.length})
                            </span>
                            <span class="text-[9px] text-gray-500 group-open:rotate-180 transition-transform">▼</span>
                        </summary>
                        <div class="p-2 space-y-1.5 max-h-48 overflow-y-auto custom-scrollbar border-t border-white/5">
                            ${tradesRows}
                        </div>
                    </details>
                </div>
                `;
            }).join('');
        };

        window.renderQuantLabRegistry = function(strategies) {
            const container = document.getElementById('ql-registry-list');
            if (!container) return;
            if (!strategies || strategies.length === 0) {
                container.innerHTML = '<div class="text-center py-8 text-xs text-gray-500 font-mono">No strategies registered yet.</div>';
                return;
            }

            container.innerHTML = strategies.map(s => `
                <div class="bg-[#121829] border border-white/10 rounded-xl p-3.5 space-y-2">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-black text-white">${s.name}</span>
                            <span class="px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider bg-white/10 text-gray-300">
                                ${s.status}
                            </span>
                            <span class="text-[9px] font-mono text-gray-500">${s.asset}</span>
                        </div>
                        <span class="text-[9px] font-mono text-gray-500">${s.created_at || ''}</span>
                    </div>
                    <p class="text-[11px] text-gray-300 italic">"${s.hypothesis}"</p>
                    <div class="bg-black/50 border border-white/5 rounded-lg p-2.5 overflow-x-auto">
                        <pre class="text-[10px] text-purple-300 font-mono leading-relaxed">${s.code ? s.code.replace(/</g, '&lt;').replace(/>/g, '&gt;') : 'No code'}</pre>
                    </div>
                </div>
            `).join('');
        };

        window.runQuantLabCycle = async function() {
            const btn = document.getElementById('btn-run-quant-cycle');
            const spinner = document.getElementById('ql-cycle-spinner');
            if (btn) btn.disabled = true;
            if (spinner) spinner.classList.remove('hidden');

            try {
                const res = await fetch((window.API_BASE_URL || '') + '/api/quant-lab/cycle/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ asset: 'BTC', target_interval: '15m' })
                });
                const data = await res.json();
                if (data.success && data.report) {
                    const r = data.report;
                    alert(`Research Cycle Complete!\nStrategy: ${r.name}\nOutcome: ${r.result}\n${r.validation?.passed ? 'Passed backtests and placed into Paper Incubation!' : 'Failed backtest hurdles and committed to Strategy Graveyard.'}`);
                }
                await window.fetchQuantLabData();
            } catch (e) {
                console.error("[QuantLab] Cycle execution error:", e);
                alert("Error executing research cycle: " + e.message);
            } finally {
                if (btn) btn.disabled = false;
                if (spinner) spinner.classList.add('hidden');
            }
        };

        window.promoteQuantLabStrategy = async function(strategyId) {
            if (!confirm("Promote this strategy to active production trading?")) return;
            try {
                const res = await fetch((window.API_BASE_URL || '') + `/api/quant-lab/strategy/${strategyId}/promote`, {
                    method: 'POST'
                });
                const data = await res.json();
                if (data.success) {
                    alert(data.message || "Strategy promoted!");
                    window.fetchQuantLabData();
                }
            } catch (e) {
                alert("Error promoting strategy: " + e.message);
            }
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
                let rawTs = p.ts;
                let parsedTs = typeof rawTs === 'number' ? rawTs : (Date.parse(rawTs) / 1000);
                let ts = (!isNaN(parsedTs) && parsedTs > 0) ? Math.floor(parsedTs) : (Math.floor(Date.now() / 1000) - (points.length - i) * 60);
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
            if (s.countdown && countdown && !window._kalshiClockSynced) countdown.textContent = s.countdown;
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
                modeBadge.className = s.mode === 'LIVE' ? 'w-12 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest text-center bg-red-500/20 text-red-300 border border-red-500/40' : 'w-12 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest text-center bg-cyan-500/20 text-cyan-300 border border-cyan-500/40';
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

            // Real-time update to Position Scanner & Nav Live PnL on spot price ticks
            if (window.lastDashboardStats) {
                if (typeof updateActivePositionHud === 'function') {
                    updateActivePositionHud(window.lastDashboardStats);
                }
                if (typeof window.updateNavLivePnl === 'function') {
                    window.updateNavLivePnl(window.lastDashboardStats);
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

        window._kalshiClockOffsetMs = window._kalshiClockOffsetMs || 0;
        window._kalshiCloseEpochMs = window._kalshiCloseEpochMs || 0;
        window._kalshiClockSynced = false;

        function tickExecCountdown() {
            const cdEl = document.getElementById('exec-countdown');
            if (!cdEl) return;
            const nowMs = Date.now() + (window._kalshiClockOffsetMs || 0);
            const nowSec = Math.floor(nowMs / 1000);
            let sec = 0;
            if (window._kalshiCloseEpochMs && window._kalshiCloseEpochMs > nowMs && (window._kalshiCloseEpochMs - nowMs) <= 960000) {
                sec = Math.max(0, Math.floor(window._kalshiCloseEpochMs / 1000) - nowSec);
            } else {
                sec = 900 - (nowSec % 900);
            }
            if (sec <= 0 || sec > 900) sec = 900;
            const mm = String(Math.floor(sec / 60)).padStart(2, '0');
            const ss = String(sec % 60).padStart(2, '0');
            const fmt = `${mm}:${ss}`;
            if (cdEl.textContent !== fmt) {
                cdEl.textContent = fmt;
            }
            if (sec <= 15 && sec > 0 && lastPlayedCountdownSec !== sec && (sec === 15 || sec === 10 || sec === 5)) {
                lastPlayedCountdownSec = sec;
                if (window.soundEngine) soundEngine.play('countdown_warning');
            }
        }
        setInterval(tickExecCountdown, 200);

        // Fetch Kalshi contract data for execution panel
        let _isFetchingKalshi = false;
        let _hasInitialKalshiLoaded = false;
        async function fetchKalshiData(force = false) {
            if ((document.hidden || !window.isTabActive) && !force && _hasInitialKalshiLoaded) return;
            if (_isFetchingKalshi && !force) return;
            _hasInitialKalshiLoaded = true;
            _isFetchingKalshi = true;
            const thisReqId = ++currentKalshiRequestId;
            const reqAsset = (window.currentAsset || 'BTC').toUpperCase();
            const curA = reqAsset.toLowerCase();

            try {
                const tReqStart = Date.now();
                const [kRes, cRes, tickerRes] = await Promise.all([
                    fetch((window.API_BASE_URL||'')+'/api/engine/' + curA + '/kalshi'),
                    fetch((window.API_BASE_URL||'')+'/api/engine/' + curA + '/countdown'),
                    fetch((window.API_BASE_URL||'')+'/api/engine/' + curA + '/ticker'),
                ]);
                const tReqMid = (tReqStart + Date.now()) / 2;

                // Drop response if user switched asset or a newer request superseded this one
                if (reqAsset !== (window.currentAsset || 'BTC').toUpperCase() || thisReqId < currentKalshiRequestId) {
                    return;
                }

                if (kRes.ok) {
                    const k = await kRes.json();
                    window.currentKalshiTarget = k.target_price;
                    if (k.close_epoch_ms && k.close_epoch_ms > 0) {
                        window._kalshiCloseEpochMs = Number(k.close_epoch_ms);
                    }
                    if (k.server_now_ms && k.server_now_ms > 0) {
                        window._kalshiClockOffsetMs = Number(k.server_now_ms) - tReqMid;
                        window._kalshiClockSynced = true;
                    }

                    // Save bids for active position PnL computation
                    if (!window.assetBids) window.assetBids = {};
                    if (k.yes_bid !== undefined) {
                        window.lastYesBid = Math.round(k.yes_bid * 100);
                        if (!window.assetBids[reqAsset]) window.assetBids[reqAsset] = {};
                        window.assetBids[reqAsset].yes_bid = window.lastYesBid;
                    }
                    if (k.no_bid !== undefined) {
                        window.lastNoBid = Math.round(k.no_bid * 100);
                        if (!window.assetBids[reqAsset]) window.assetBids[reqAsset] = {};
                        window.assetBids[reqAsset].no_bid = window.lastNoBid;
                    }
                    
                    if (window.lastDashboardStats) {
                        if (typeof updateActivePositionHud === 'function') {
                            updateActivePositionHud(window.lastDashboardStats);
                        }
                        if (typeof window.updateNavLivePnl === 'function') {
                            window.updateNavLivePnl(window.lastDashboardStats);
                        }
                    }

                    const strikeEl = document.getElementById('exec-strike');
                    if (strikeEl) {
                        const tp = Number(k.target_price);
                        const isFxStrike = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'].includes(reqAsset);
                        const strikeDec = reqAsset === 'USDJPY' ? 3 : (isFxStrike ? 5 : (reqAsset === 'DOGE' ? 4 : 2));
                        const strikePfx = isFxStrike ? '' : '$';
                        if (k.target_price && !isNaN(tp) && isFinite(tp) && tp > 0) {
                            strikeEl.textContent = strikePfx + tp.toLocaleString(undefined, {minimumFractionDigits: strikeDec, maximumFractionDigits: strikeDec});
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
                    if (c.server_now_ms && c.server_now_ms > 0) {
                        window._kalshiClockOffsetMs = Number(c.server_now_ms) - tReqMid;
                        window._kalshiClockSynced = true;
                    }
                    if (c.close_epoch_ms && c.close_epoch_ms > 0) {
                        window._kalshiCloseEpochMs = Number(c.close_epoch_ms);
                    }
                    tickExecCountdown();
                }

                if (tickerRes.ok) {
                    const tickerData = await tickerRes.json();
                    if (tickerData && tickerData.price) {
                        const spotVal = Number(tickerData.price);
                        if (isFinite(spotVal) && spotVal > 0) {
                            if (!spotWsLive()) {
                                updateSpotPriceDisplay(spotVal, reqAsset);
                            }
                        }
                    }
                }
            } catch(e) { console.warn('[ExecPanel] fetch err', e); }
            finally { _isFetchingKalshi = false; }
        }
        fetchKalshiData(true);
        if (typeof initSpotWebSocket === 'function') initSpotWebSocket();
        if (typeof syncSoundSettingsUI === 'function') syncSoundSettingsUI();
        setInterval(() => fetchKalshiData(false), 1000);

        // Real-Time 1-Second Open Trade PnL & Position Monitor Tick
        let _isTickOpenPnlRunning = false;
        async function tickOpenTradesPnL() {
            if (_isTickOpenPnlRunning) return;
            _isTickOpenPnlRunning = true;
            try {
                const s = window.lastDashboardStats;
                if (!s) return;

                // Identify assets of open trades
                const openTrades = (s.recent_trades || []).filter(t => String(t.status || '').toUpperCase() === 'OPEN');
                if (openTrades.length > 0) {
                    const openAssets = new Set();
                    openTrades.forEach(t => {
                        const isSport = window.__isSportTrade ? window.__isSportTrade(t) : false;
                        const isInv = window.__isInvestmentTrade ? window.__isInvestmentTrade(t) : false;
                        if (!isSport && !isInv) {
                            let a = String(t.asset || '').toUpperCase();
                            if (!a || a === 'NONE') {
                                const tk = String(t.ticker || '').toUpperCase();
                                if (tk.includes('BTC')) a = 'BTC';
                                else if (tk.includes('ETH')) a = 'ETH';
                                else if (tk.includes('SOL')) a = 'SOL';
                                else if (tk.includes('DOGE')) a = 'DOGE';
                            }
                            if (a && a !== (window.currentAsset || 'BTC').toUpperCase()) {
                                openAssets.add(a);
                            }
                        }
                    });

                    // Fetch bids for non-active open assets if any
                    if (openAssets.size > 0) {
                        await Promise.all(Array.from(openAssets).map(async (asset) => {
                            try {
                                const res = await fetch((window.API_BASE_URL || '') + '/api/engine/' + asset.toLowerCase() + '/kalshi');
                                if (res.ok) {
                                    const kd = await res.json();
                                    if (!window.assetBids) window.assetBids = {};
                                    if (!window.assetBids[asset]) window.assetBids[asset] = {};
                                    if (kd.yes_bid !== undefined) window.assetBids[asset].yes_bid = Math.round(kd.yes_bid * 100);
                                    if (kd.no_bid !== undefined) window.assetBids[asset].no_bid = Math.round(kd.no_bid * 100);
                                }
                            } catch(e) {}
                        }));
                    }
                }

                // Recalculate and update PnL everywhere every 1 second
                if (typeof updateActivePositionHud === 'function') {
                    updateActivePositionHud(s);
                }
                if (typeof window.updateNavLivePnl === 'function') {
                    window.updateNavLivePnl(s);
                }
                if (typeof window.renderTradesContainer === 'function') {
                    window.renderTradesContainer(s);
                }
            } catch(err) {
                console.warn('[RealtimePnL] tick err', err);
            } finally {
                _isTickOpenPnlRunning = false;
            }
        }
        setInterval(tickOpenTradesPnL, 1000);

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
