
        const token = localStorage.getItem('saas_token');
        if (!token) window.location.href = '/login.html';
        
        let currentMode = "PAPER";
        let aiEnabled = true; // Assume true since we removed toggle to simplify iPhone UI. We could re-add if requested.

        function logout() {
            localStorage.removeItem('saas_token');
            window.location.href = '/login.html';
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
                    loadDashboard();
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
                slider.className = "absolute top-1 bottom-1 w-[calc(50%-4px)] bg-kalshi-red rounded-lg transition-transform duration-300";
                btnLive.className = "flex-1 relative z-10 py-2.5 text-[10px] font-bold uppercase tracking-wider text-white";
                btnPaper.className = "flex-1 relative z-10 py-2.5 text-[10px] font-bold uppercase tracking-wider text-gray-500";
                badge.innerText = "LIVE";
                badge.className = "px-1.5 py-0.5 rounded bg-kalshi-red text-white leading-none";
            } else {
                slider.style.transform = "translateX(0%)";
                slider.className = "absolute top-1 bottom-1 w-[calc(50%-4px)] bg-kalshi-blue rounded-lg transition-transform duration-300";
                btnPaper.className = "flex-1 relative z-10 py-2.5 text-[10px] font-bold uppercase tracking-wider text-white";
                btnLive.className = "flex-1 relative z-10 py-2.5 text-[10px] font-bold uppercase tracking-wider text-gray-500";
                badge.innerText = "PAPER";
                badge.className = "px-1.5 py-0.5 rounded bg-kalshi-blue text-white leading-none";
            }
        }

        
        async function closeAllTrades() {
            const toggleEl = document.getElementById('one-click-toggle');
            const oneClick = toggleEl ? toggleEl.checked : false;
            
            if(!oneClick && !confirm('Are you sure you want to close all open trades?')) return;

            try {
                const res = await fetch('/api/auth/trade/close_all', {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + token }
                });
                if(res.ok) {
                    const data = await res.json();
                    if(!oneClick) alert(data.success ? 'Closed trades successfully.' : 'Failed to close trades: ' + data.error);
                    loadDashboard();
                } else {
                    const data = await res.json();
                    let errMsg = data.detail || data.error || 'Unknown Error';
                    if (typeof errMsg === 'object') errMsg = JSON.stringify(errMsg);
                    alert('Failed: ' + errMsg);
                }
            } catch(e) {
                alert('Error: ' + e);
            }
        }

        async function executeManualTrade(direction) {
            const sizeEl = document.getElementById('trade-size-dollars');
            const amt = parseFloat(sizeEl ? sizeEl.value : 50) || 50;
            const toggleEl = document.getElementById('one-click-toggle');
            const oneClick = toggleEl ? toggleEl.checked : false;
            
            if(!oneClick && !confirm(`Execute $${amt} manual trade for ${direction.toUpperCase()} in ${currentMode} mode?`)) return;
            
            try {
                const res = await fetch('/api/auth/trade/manual', {
                    method: "POST",
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                    body: JSON.stringify({ direction: direction, amount_dollars: parseFloat(amt) })
                });
                const data = await res.json();
                if(res.ok) {
                    let bCount = data.count !== undefined ? data.count : (data.trade ? data.trade.count : 'unknown');
                    if(!oneClick) alert(`Success! Bought ${bCount} ${direction.toUpperCase()} contracts.`);
                    loadDashboard();
                } else {
                    let _err = data.detail; if (typeof _err === "object") _err = JSON.stringify(_err); alert(`Failed: ${_err}`);
                }
            } catch(e) {
                alert("Network error.");
            }
        }

        async function forceMLTrade() {
            const toggleEl = document.getElementById('one-click-toggle');
            const oneClick = toggleEl ? toggleEl.checked : false;
            if(!oneClick && !confirm(`Force the AI's current signal in ${currentMode} mode?`)) return;
            
            try {
                const res = await fetch('/api/auth/trade/force_ml', {
                    method: "POST",
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                const data = await res.json();
                if(res.ok) {
                    if(!oneClick) alert(`Success! ML forced a ${data.side} trade for ${data.count} contracts.`);
                    loadDashboard();
                } else {
                    let _err = data.detail || data.error; if (typeof _err === "object") _err = JSON.stringify(_err); alert(`Failed: ${_err}`);
                }
            } catch(e) {
                alert(`Error: ${e}`);
            }
        }

        async function toggleAutoTrader(enabled) {
            try {
                // Optimistically sync both UI toggles
                const autoToggle = document.getElementById('auto-trader-toggle');
                const autoStatus = document.getElementById('auto-trader-status');
                const headerToggle = document.getElementById('header-auto-toggle');
                const headerStatus = document.getElementById('header-auto-status');
                
                if(autoToggle) autoToggle.checked = enabled;
                if(headerToggle) headerToggle.checked = enabled;
                
                const onClass = 'text-[9px] font-bold text-green-500 uppercase tracking-widest';
                const offClass = 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';
                
                if(autoStatus) {
                    autoStatus.innerText = enabled ? 'ON' : 'OFF';
                    autoStatus.className = enabled ? onClass : offClass;
                }
                if(headerStatus) {
                    headerStatus.innerText = enabled ? 'AUTO: ON' : 'AUTO: OFF';
                    headerStatus.className = enabled ? onClass : offClass;
                }

                const res = await fetch(`/api/engine/btc/trade/toggle?enabled=${enabled}`, {
                    method: "POST",
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if(!res.ok) {
                    throw new Error("Failed to toggle");
                }
            } catch(e) {
                console.error("Toggle error:", e);
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
                const res = await fetch(`/api/engine/btc/trade/manual?direction=${direction}&lots=${size}`, {
                    method: "POST",
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                const data = await res.json();
                if(res.ok || data.success) {
                    if(!oneClick) alert(`Success! Placed ${direction} trade.`);
                    loadDashboard();
                } else {
                    let _err = data.detail || data.error; if (typeof _err === "object") _err = JSON.stringify(_err); alert(`Failed: ${_err}`);
                }
            } catch(e) {
                alert(`Error: ${e}`);
            }
        }

        async function saveUserConfig() {
            const size = parseFloat(document.getElementById('trade-size-dollars').value) || 50.0;
            const sl = parseFloat(document.getElementById('stop-loss-pct').value) || 10.0;
            const tp = parseFloat(document.getElementById('take-profit-pct').value) || 50.0;
            const mdt = parseInt(document.getElementById('max-daily-trades').value) || 10;
            const mdr = parseFloat(document.getElementById('max-daily-risk').value) || 50.0;
            
            const forceEl = document.getElementById('force-trade-toggle');
            const autoForce = forceEl ? forceEl.checked : false;
            
            const techEl = document.getElementById('technical-force-toggle');
            const techForce = techEl ? techEl.checked : false;
            
            const oneshotEl = document.getElementById('one-shot-toggle');
            const oneshot = oneshotEl ? oneshotEl.checked : false;
            
            const tsToggle = document.getElementById('trailing-stop-toggle');
            const tsEnabled = tsToggle ? tsToggle.checked : false;
            const tsAct = parseFloat(document.getElementById('trailing-stop-activation-pct').value) || 35.0;
            const tsDist = parseFloat(document.getElementById('trailing-stop-distance-pct').value) || 6.0;
            
            const tStyle = document.getElementById('trading-style').value;
            const sSource = document.getElementById('signal-source').value;
            
            const modelChoice = document.getElementById('model-choice') ? document.getElementById('model-choice').value : "Swarm";
            const trainWindow = parseInt(document.getElementById('train-window')?.value) || 4000;
            const regC = parseFloat(document.getElementById('reg-c')?.value) || 0.5;
            const cWeight = document.getElementById('class-weight')?.value || "balanced";
            const xgbEst = parseInt(document.getElementById('xgb-estimators')?.value) || 300;
            const xgbDepth = parseInt(document.getElementById('xgb-max-depth')?.value) || 5;
            const xgbLR = parseFloat(document.getElementById('xgb-learning-rate')?.value) || 0.1;

            try {
                await fetch('/api/auth/user/config', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        trade_size_dollars: size,
                        stop_loss_pct: sl,
                        take_profit_pct: tp,
                        max_daily_trades: mdt,
                        max_daily_risk: mdr,
                        one_click_trade: false,
                        auto_force_trade: autoForce,
                        ignore_pass_technical: techForce,
                        one_shot_ai: oneshot,
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
                        xgb_learning_rate: xgbLR
                    })
                });
            } catch(e) {}
        }

        async function saveKeys() {
            const keyId = document.getElementById('kalshi-key').value;
            const privKey = document.getElementById('kalshi-priv').value;
            if(!keyId || !privKey) return alert("Please fill both key fields.");
            try {
                const res = await fetch('/api/auth/keys', {
                    method: "POST",
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                    body: JSON.stringify({ key_id: keyId, private_key: privKey })
                });
                if(res.ok) {
                    alert("Keys saved securely.");
                    document.getElementById('kalshi-key').value = '';
                    document.getElementById('kalshi-priv').value = '';
                } else {
                    const errorData = await res.json();
                    let _err = errorData.detail || 'Unknown error'; if (typeof _err === "object") _err = JSON.stringify(_err); alert(`Failed to save keys: ${_err}`);
                }
            } catch(e) {
                alert(`Error saving keys: ${e}`);
            }
        }

        function fillMLCard(lastMLData, fullData) {
            if(!lastMLData) return;
            document.getElementById('popup-bias').innerText = lastMLData.primary_bias || '--';
            document.getElementById('popup-conf').innerText = `${lastMLData.confidence_percent || 0}%`;
            
            // Use the actual AI ML predicted probability, fallback to Kalshi yes_prob if ML is unavailable
            const prob = (lastMLData && lastMLData.predicted_probability != null) 
                ? lastMLData.predicted_probability * 100 
                : ((fullData && fullData.yes_prob != null) ? fullData.yes_prob : 0);
            document.getElementById('popup-prob').innerText = `${parseFloat(prob).toFixed(1)}%`;
            
            let confColor = 'text-gray-400';
            if(lastMLData.confidence_percent >= 60) confColor = 'text-kalshi-green';
            else if(lastMLData.confidence_percent <= 40) confColor = 'text-kalshi-red';
            document.getElementById('popup-conf').className = `text-xs font-black ${confColor}`;
            
            let summaryText = lastMLData.summary ? lastMLData.summary : `Model predicts ${lastMLData.primary_bias} with ${parseFloat(prob).toFixed(1)}% YES probability.`;
            document.getElementById('popup-summary').innerText = summaryText;
        }

        async function loadConfig() {
            try {
                const res = await fetch('/api/engine/btc/trade/config', {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if(res.ok) {
                    const c = await res.json();
                    
                    // Auto-Trader Master Toggle
                    const autoToggle = document.getElementById('auto-trader-toggle');
                    const autoStatus = document.getElementById('auto-trader-status');
                    const headerToggle = document.getElementById('header-auto-toggle');
                    const headerStatus = document.getElementById('header-auto-status');
                    
                    const onClass = 'text-[9px] font-bold text-green-500 uppercase tracking-widest';
                    const offClass = 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';
                    
                    if(c.enabled !== undefined) {
                        if(autoToggle) autoToggle.checked = c.enabled;
                        if(headerToggle) headerToggle.checked = c.enabled;
                        
                        if(autoStatus) {
                            autoStatus.innerText = c.enabled ? 'ON' : 'OFF';
                            autoStatus.className = c.enabled ? onClass : offClass;
                        }
                        if(headerStatus) {
                            headerStatus.innerText = c.enabled ? 'AUTO: ON' : 'AUTO: OFF';
                            headerStatus.className = c.enabled ? onClass : offClass;
                        }
                    }

                    if(c.ai_settings) {
                        if(document.getElementById('trade-size-dollars')) document.getElementById('trade-size-dollars').value = c.ai_settings.trade_size_dollars || 50;
                        if(document.getElementById('stop-loss-pct')) document.getElementById('stop-loss-pct').value = c.ai_settings.stop_loss_pct || 10;
                        
                        const forceToggle = document.getElementById('force-trade-toggle');
                        if(forceToggle && c.ai_settings.auto_force_trade !== undefined) {
                            forceToggle.checked = c.ai_settings.auto_force_trade;
                        }
                        
                        const techToggle = document.getElementById('technical-force-toggle');
                        if(techToggle && c.ai_settings.ignore_pass_technical !== undefined) techToggle.checked = c.ai_settings.ignore_pass_technical;
                        
                        const oneshotToggle = document.getElementById('one-shot-toggle');
                        if(oneshotToggle && c.ai_settings.one_shot_ai !== undefined) oneshotToggle.checked = c.ai_settings.one_shot_ai;

                        const tsToggle = document.getElementById('trailing-stop-toggle');
                        if(tsToggle && c.ai_settings.trailing_stop_enabled !== undefined) {
                            tsToggle.checked = c.ai_settings.trailing_stop_enabled;
                        }
                        if(document.getElementById('trailing-stop-activation-pct')) document.getElementById('trailing-stop-activation-pct').value = c.ai_settings.trailing_stop_activation_pct || 35;
                        if(document.getElementById('trailing-stop-distance-pct')) document.getElementById('trailing-stop-distance-pct').value = c.ai_settings.trailing_stop_distance_pct || 6;

                        if(document.getElementById('take-profit-pct')) document.getElementById('take-profit-pct').value = c.ai_settings.take_profit_pct || 50;
                        if(document.getElementById('max-daily-trades')) document.getElementById('max-daily-trades').value = c.ai_settings.max_daily_trades || 10;
                        if(document.getElementById('max-daily-risk')) document.getElementById('max-daily-risk').value = c.ai_settings.max_daily_risk || 50;
                        
                        if(document.getElementById('trading-style')) document.getElementById('trading-style').value = c.ai_settings.trading_style || 'AUTO';
                        if(document.getElementById('signal-source')) document.getElementById('signal-source').value = c.ai_settings.signal_source || 'BLEND';
                        
                        if(document.getElementById('model-choice')) document.getElementById('model-choice').value = c.ai_settings.model_choice || 'Swarm';
                        
                        if(document.getElementById('train-window')) {
                            document.getElementById('train-window').value = c.ai_settings.train_window || 4000;
                            if(document.getElementById('train-win-val')) document.getElementById('train-win-val').innerText = c.ai_settings.train_window || 4000;
                        }
                        if(document.getElementById('reg-c')) document.getElementById('reg-c').value = c.ai_settings.regularization_c || 0.5;
                        if(document.getElementById('class-weight')) document.getElementById('class-weight').value = c.ai_settings.class_weight || 'balanced';
                        
                        if(document.getElementById('xgb-estimators')) document.getElementById('xgb-estimators').value = c.ai_settings.xgb_estimators || 300;
                        if(document.getElementById('xgb-max-depth')) document.getElementById('xgb-max-depth').value = c.ai_settings.xgb_max_depth || 5;
                        if(document.getElementById('xgb-learning-rate')) document.getElementById('xgb-learning-rate').value = c.ai_settings.xgb_learning_rate || 0.1;
                    }
                }
            } catch(e) {}
        }

        
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
        
        async function loadDashboard() {
            try {
                const res = await fetch('/api/auth/dashboard_stats', {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if(!res.ok) {
                    if(res.status === 401) logout();
                    return;
                }
                const s = await res.json();

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

                // Configs (prevent overwriting if user is typing)
                if (document.activeElement.id !== 'trade-size-dollars' && s.trade_size_dollars !== undefined) document.getElementById('trade-size-dollars').value = s.trade_size_dollars;
                if (document.activeElement.id !== 'trading-style' && s.trading_style !== undefined) document.getElementById('trading-style').value = s.trading_style;
                if (document.activeElement.id !== 'signal-source' && s.signal_source !== undefined) document.getElementById('signal-source').value = s.signal_source;
                if (document.activeElement.id !== 'stop-loss-pct' && s.stop_loss_pct !== undefined) document.getElementById('stop-loss-pct').value = s.stop_loss_pct;
                if (document.activeElement.id !== 'take-profit-pct' && s.take_profit_pct !== undefined) document.getElementById('take-profit-pct').value = s.take_profit_pct;
                if (document.activeElement.id !== 'max-daily-trades' && s.max_daily_trades !== undefined) document.getElementById('max-daily-trades').value = s.max_daily_trades;
                if (document.activeElement.id !== 'max-daily-risk' && s.max_daily_risk !== undefined) document.getElementById('max-daily-risk').value = s.max_daily_risk;
                
                if (document.activeElement.id !== 'trailing-stop-activation-pct' && s.trailing_stop_activation_pct !== undefined) document.getElementById('trailing-stop-activation-pct').value = s.trailing_stop_activation_pct;
                if (document.activeElement.id !== 'trailing-stop-distance-pct' && s.trailing_stop_distance_pct !== undefined) document.getElementById('trailing-stop-distance-pct').value = s.trailing_stop_distance_pct;
                
                const tsEl = document.getElementById('trailing-stop-toggle');
                if (tsEl && s.trailing_stop_enabled !== undefined && document.activeElement.id !== 'trailing-stop-toggle') {
                    tsEl.checked = !!s.trailing_stop_enabled;
                    document.getElementById('trailing-stop-text').innerText = tsEl.checked ? 'ON' : 'OFF';
                    document.getElementById('trailing-stop-text').className = tsEl.checked ? 'text-[9px] font-bold text-emerald-400 uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';
                }
                
                const oneClickEl = document.getElementById('one-click-toggle');
                if (oneClickEl && s.one_click_trade !== undefined && document.activeElement.id !== 'one-click-toggle') {
                    oneClickEl.checked = !!s.one_click_trade;
                    document.getElementById('one-click-text').innerText = oneClickEl.checked ? 'ON' : 'OFF';
                    document.getElementById('one-click-text').className = oneClickEl.checked ? 'text-[9px] font-bold text-kalshi-blue uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';
                }
                const forceEl = document.getElementById('force-trade-toggle');
                if (forceEl && s.auto_force_trade !== undefined && document.activeElement.id !== 'force-trade-toggle') {
                    forceEl.checked = !!s.auto_force_trade;
                    document.getElementById('force-trade-text').innerText = forceEl.checked ? 'ON' : 'OFF';
                    document.getElementById('force-trade-text').className = forceEl.checked ? 'text-[9px] font-bold text-purple-400 uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';
                }

                // Recent trades
                
                      const container = document.getElementById('tradesContainer');
                      const recent = (s.recent_trades || []).slice(0, 15);
                      if (recent.length === 0) {
                          container.innerHTML = '<div class="text-center py-6 text-[10px] text-gray-500 font-mono bg-[#131b2c] rounded-xl border border-kalshi-border">No recent trades found</div>';
                      } else {
                          let htmlString = '';
                          recent.forEach(t => {
                              const isWin = (t.status || "").toUpperCase().includes("WIN") || parseFloat(t.pnl_dollars || 0) > 0;
                              const isLoss = (t.status || "").toUpperCase().includes("LOSS") || parseFloat(t.pnl_dollars || 0) < 0;
                              
                              let borderClass = "border-l-2 border-l-kalshi-blue";
                              let statusBadge = '<span class="text-[9px] font-bold text-kalshi-blue">OPEN</span>';
                              
                              if (t.status === 'OPEN') {
                                  statusBadge = 
                                      <div class="flex items-center gap-1">
                                          <span class="text-[9px] font-bold text-yellow-400 animate-pulse">OPEN</span>
                                          <button onclick="closeTrade('')" class="px-1.5 py-0.5 bg-red-600/20 text-red-500 rounded text-[8px] font-bold border border-red-500/30 transition-colors">CLOSE</button>
                                      </div>
                                  ;
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

                              const pnlVal = parseFloat(t.pnl_dollars || 0);
                              const pnlColor = pnlVal > 0 ? "text-emerald-400" : (pnlVal < 0 ? "text-red-400" : "text-gray-400");
                              const pnlStr = pnlVal > 0 ? "+$" + pnlVal.toFixed(2) : (pnlVal < 0 ? "-$" + Math.abs(pnlVal).toFixed(2) : ".00");

                              const dir = String(t.side || "").toUpperCase();
                              const dirColor = dir === "YES" ? "text-kalshi-green" : "text-kalshi-red";

                              let badges = [];
                              const mode = String(t.mode || "PAPER").toUpperCase();
                              if (mode === "LIVE") {
                                  badges.push('<span class="text-[8px] font-black px-1.5 py-0.5 rounded uppercase bg-red-500/20 text-red-300 border border-red-500/40">LIVE</span>');
                              } else {
                                  badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">PAPER</span>');
                              }

                              const exitReason = String(t.exit_reason || t.reason || "").toUpperCase();
                              const isManual = t.is_manual === true || exitReason === "MANUAL" || exitReason === "MANUAL_CLOSE";

                              if (isManual) {
                                  badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-amber-500/15 text-amber-300 border border-amber-500/35">MANUAL</span>');
                              } else {
                                  const styleStr = t.trading_style ? String(t.trading_style).replace(/_/g, ' ') : "AUTO";
                                  badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-blue-500/20 text-blue-300 border border-blue-500/35">' + styleStr + '</span>');
                              }
                              
                              if (t.is_profit_reentry) {
                                  badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/35">2ND ENTRY</span>');
                              }
                              if (t.is_reversal || t.is_reverse) {
                                  badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase bg-purple-500/20 text-purple-400 border border-purple-500/35">REVERSAL</span>');
                              }

                              if (exitReason && exitReason !== 'KALSHI_POSITION_RECONCILED' && exitReason !== 'AI_SIGNAL' && exitReason !== 'SETTLEMENT' && !isManual) {
                                  let exitStr = exitReason.replace(/_/g, ' ');
                                  let exitColor = 'bg-slate-500/20 text-slate-400 border-slate-500/35';
                                  if (exitStr.includes('PROFIT') || exitStr.includes('TP')) exitColor = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/35';
                                  else if (exitStr.includes('STOP LOSS') || exitStr.includes('STOP_LOSS') || exitStr.includes('SL') || exitStr.includes('STOP')) exitColor = 'bg-red-500/20 text-red-400 border-red-500/35';
                                  badges.push('<span class="text-[8px] font-bold px-1.5 py-0.5 rounded uppercase border ' + exitColor + '">' + exitStr + '</span>');
                              }

                              htmlString += 
                                  <div class="bg-[#131b2c] rounded-xl p-2.5 shadow-sm border border-kalshi-border  flex flex-col gap-1.5">
                                      <div class="flex justify-between items-center">
                                          <div class="flex items-center gap-2">
                                              <span class="text-[10px] font-bold text-white"></span>
                                              <span class="text-[10px] font-black "></span>
                                          </div>
                                          <div class="flex items-center gap-2">
                                              
                                              <span class="text-[11px] font-mono font-bold "></span>
                                          </div>
                                      </div>
                                      <div class="flex justify-between items-center text-[9px] text-gray-500">
                                          <span></span>
                                          <span> Cont. @ {(t.entry_price || 0).toFixed(2)}</span>
                                      </div>
                                      <div class="flex flex-wrap gap-1 mt-0.5">
                                          
                                      </div>
                                  </div>
                              ;
                          });
                          container.innerHTML = htmlString;
                      }

                }
            } catch(e) {
                console.error("Dashboard render error:", e);
            }
        }

        window.closeTrade = async function(tradeId) {
            try {
                const token = localStorage.getItem('saas_token');
                const res = await fetch(`/api/auth/trade/close/${tradeId}`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` }
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

        async function pollKalshi() {
            try {
                // Fetch Ticker
                fetch('/api/engine/btc/ticker').then(r => r.json()).then(tData => {
                    if(tData && tData.price) {
                        document.getElementById('live-btc-price').innerText = '$' + parseFloat(tData.price).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                        document.getElementById('live-btc-price').classList.remove('animate-pulse');
                    }
                }).catch(e=>{});

                // Fetch Countdown
                fetch('/api/engine/btc/countdown').then(r => r.json()).then(cData => {
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
                const res = await fetch('/api/engine/btc/kalshi');
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
        setInterval(pollKalshi, 1000);
        setInterval(loadDashboard, 1000);

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
    