import re

# Read original file to keep JS if needed, but it's easier to just write the whole thing
new_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AI Trader SaaS</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        kalshi: {
                            blue: '#0052ff',
                            green: '#00ff80',
                            red: '#ff4040',
                            dark: '#0a0e17',
                            border: '#1e293b'
                        }
                    }
                }
            }
        }
    </script>
</head>
<body class="bg-black text-white antialiased overflow-y-auto pb-8 font-sans selection:bg-kalshi-blue selection:text-white">

    <!-- Sticky Header -->
    <header class="sticky top-0 z-50 bg-black/90 backdrop-blur-md border-b border-kalshi-border px-4 py-3 flex justify-between items-center">
        <div class="flex items-center gap-2">
            <div class="w-7 h-7 rounded-full bg-kalshi-blue flex items-center justify-center font-bold text-white text-xs shadow-[0_0_15px_rgba(0,82,255,0.5)]">AI</div>
            <div>
                <h1 class="text-xs font-bold tracking-wider uppercase text-white leading-none mb-0.5">AI Copilot</h1>
                <div id="connection-status" class="text-[9px] uppercase font-bold text-gray-500 tracking-wider">Checking...</div>
            </div>
        </div>
        <div class="flex items-center gap-2">
            <button onclick="location.reload()" class="w-8 h-8 flex items-center justify-center bg-gray-800 text-gray-300 rounded-lg active:scale-95 transition-all">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
            </button>
            <button onclick="logout()" class="w-8 h-8 flex items-center justify-center bg-red-900/40 text-red-400 rounded-lg active:scale-95 transition-all border border-red-900">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg>
            </button>
        </div>
    </header>

    <main class="max-w-md mx-auto pt-4">
        
        <!-- Mode Switcher -->
        <div class="mx-4 mb-4 bg-[#131b2c] rounded-xl p-1 flex relative shadow-sm border border-kalshi-border">
            <div id="mode-slider" class="absolute top-1 bottom-1 w-[calc(50%-4px)] bg-kalshi-blue rounded-lg transition-transform duration-300 transform translate-x-0"></div>
            <button id="btn-mode-paper" onclick="setTradingMode('PAPER')" class="flex-1 relative z-10 py-2.5 text-[10px] font-bold uppercase tracking-wider text-white">Paper Trading</button>
            <button id="btn-mode-live" onclick="setTradingMode('LIVE')" class="flex-1 relative z-10 py-2.5 text-[10px] font-bold uppercase tracking-wider text-gray-400">Live Trading</button>
        </div>

        <!-- Balance Card -->
        <div class="mx-4 mb-5 bg-gradient-to-br from-[#1a233a] to-[#131b2c] border border-kalshi-border rounded-2xl p-5 shadow-lg">
            <div class="text-[9px] text-gray-400 uppercase tracking-widest font-bold flex gap-1.5 items-center">
                <span id="bal-mode-badge" class="px-1.5 py-0.5 rounded bg-kalshi-blue text-white leading-none">PAPER</span> BALANCE
            </div>
            <div id="val-balance" class="text-3xl font-black tabular-nums mt-1 text-white tracking-tighter">$--.--</div>
            <div class="flex justify-between mt-4 pt-3 border-t border-kalshi-border/50">
                <div>
                    <div class="text-[9px] text-gray-400 uppercase tracking-widest mb-0.5 font-bold">Net PnL</div>
                    <div id="val-pnl" class="text-sm font-black text-gray-500 tabular-nums">$--.--</div>
                </div>
                <div class="text-right">
                    <div class="text-[9px] text-gray-400 uppercase tracking-widest mb-0.5 font-bold">Win Rate</div>
                    <div id="val-winrate" class="text-sm font-black text-gray-300">--%</div>
                </div>
            </div>
        </div>

        <!-- Active Market & Execution -->
        <div class="mx-4 mb-5 bg-[#131b2c] border border-kalshi-border rounded-2xl overflow-hidden shadow-lg">
            <div class="bg-black/40 px-4 py-2.5 flex justify-between items-center border-b border-kalshi-border">
                <div class="text-[9px] font-bold text-gray-500 uppercase tracking-wider flex items-center gap-1.5">
                    BTC 15M <div class="w-1 h-1 rounded-full bg-kalshi-blue animate-pulse"></div> <span id="kalshi-target" class="text-white font-mono bg-gray-800 px-1 rounded">--</span>
                </div>
                <div id="kalshi-time" class="text-[10px] font-black text-kalshi-blue uppercase tabular-nums">--:--</div>
            </div>
            
            <div class="p-6 text-center">
                <div class="text-[9px] text-gray-500 font-bold uppercase tracking-widest mb-1">Live BTC Price</div>
                <div id="live-btc-price" class="text-4xl font-black text-white tabular-nums tracking-tighter animate-pulse">$--.--</div>
            </div>

            <div class="px-4 pb-5 grid grid-cols-2 gap-3">
                <div class="flex flex-col gap-1.5">
                    <div class="text-center text-[9px] font-bold text-gray-400 uppercase tracking-widest">YES PROB: <span id="kalshi-yes" class="text-kalshi-green ml-0.5 font-black text-xs">--%</span></div>
                    <button id="btn-buy-yes" onclick="executeManualTrade('yes')" class="py-4 bg-kalshi-green/10 border border-kalshi-green/30 text-kalshi-green font-black rounded-xl active:scale-95 transition-all text-sm shadow-[0_0_15px_rgba(0,255,128,0.1)] active:bg-kalshi-green/30 tracking-widest uppercase">BUY YES</button>
                </div>
                <div class="flex flex-col gap-1.5">
                    <div class="text-center text-[9px] font-bold text-gray-400 uppercase tracking-widest">NO PROB: <span id="kalshi-no" class="text-kalshi-red ml-0.5 font-black text-xs">--%</span></div>
                    <button id="btn-buy-no" onclick="executeManualTrade('no')" class="py-4 bg-kalshi-red/10 border border-kalshi-red/30 text-kalshi-red font-black rounded-xl active:scale-95 transition-all text-sm shadow-[0_0_15px_rgba(255,64,64,0.1)] active:bg-kalshi-red/30 tracking-widest uppercase">BUY NO</button>
                </div>
            </div>
        </div>

        <!-- AI Inline Copilot Card -->
        <div class="mx-4 mb-6 bg-purple-900/10 border border-purple-500/30 rounded-2xl p-4 shadow-lg relative overflow-hidden">
            <div class="absolute top-0 left-0 w-1 h-full bg-purple-500"></div>
            <div class="flex justify-between items-center mb-4 pl-2">
                <div class="flex items-center gap-2">
                    <span class="text-[10px] font-bold text-purple-400 uppercase tracking-widest">AI Intelligence</span>
                </div>
                <div id="ml-status-bubble" class="text-[8px] font-bold px-2 py-0.5 bg-black rounded-full border border-purple-500/50 text-purple-300 uppercase tracking-widest">STANDBY</div>
            </div>
            
            <div class="grid grid-cols-3 gap-2 mb-4 pl-2">
                <div class="bg-black/40 rounded-lg p-2 text-center border border-purple-500/20">
                    <div class="text-[8px] text-gray-500 uppercase font-bold mb-0.5 tracking-wider">Bias</div>
                    <div id="popup-bias" class="text-xs font-black text-white">--</div>
                </div>
                <div class="bg-black/40 rounded-lg p-2 text-center border border-purple-500/20">
                    <div class="text-[8px] text-gray-500 uppercase font-bold mb-0.5 tracking-wider">Conf</div>
                    <div id="popup-conf" class="text-xs font-black text-white">--%</div>
                </div>
                <div class="bg-black/40 rounded-lg p-2 text-center border border-purple-500/20">
                    <div class="text-[8px] text-gray-500 uppercase font-bold mb-0.5 tracking-wider">Prob</div>
                    <div id="popup-prob" class="text-xs font-black text-white">--%</div>
                </div>
            </div>
            
            <div id="popup-summary" class="text-[10px] text-gray-400 leading-relaxed mb-4 text-center pl-2 italic">Awaiting AI signal computation...</div>
            
            <div class="pl-2">
                <button onclick="forceMLTrade()" class="w-full py-3.5 bg-purple-600/20 border border-purple-500/50 text-purple-400 font-bold text-xs uppercase tracking-widest rounded-xl transition-all active:scale-95 active:bg-purple-600/40 shadow-[0_0_15px_rgba(168,85,247,0.15)]">Force AI Signal Now</button>
            </div>
        </div>

        <!-- SaaS Configuration -->
        <div class="mx-4 mb-6 bg-[#131b2c] border border-kalshi-border rounded-2xl overflow-hidden shadow-lg">
            <div class="bg-black/40 px-4 py-3 border-b border-kalshi-border">
                <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Bot Configuration</span>
            </div>
            <div class="p-4 space-y-4">
                <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                    <div>
                        <label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest">Trade Size ($)</label>
                        <div class="text-[8px] text-gray-500 uppercase font-bold">Dollar amount per trade</div>
                    </div>
                    <input type="number" id="trade-size-dollars" class="w-20 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-xs text-white font-bold text-center focus:border-kalshi-blue focus:outline-none" min="1" max="10000" inputmode="numeric">
                </div>
                <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                    <div>
                        <label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest">Trading Style</label>
                        <div class="text-[8px] text-gray-500 uppercase font-bold">Execution aggressiveness</div>
                    </div>
                    <select id="trading-style" class="w-28 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-[9px] uppercase tracking-wider text-white font-bold focus:border-kalshi-blue focus:outline-none">
                        <option value="AUTO">Auto</option>
                        <option value="SNIPER">Sniper</option>
                        <option value="MOMENTUM_SURFER">Momentum</option>
                        <option value="CHOP">Chop</option>
                    </select>
                </div>
                <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                    <div>
                        <label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest">Signal Source</label>
                        <div class="text-[8px] text-gray-500 uppercase font-bold">Primary engine</div>
                    </div>
                    <select id="signal-source" class="w-28 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-[9px] uppercase tracking-wider text-white font-bold focus:border-kalshi-blue focus:outline-none">
                        <option value="ML_ENSEMBLE">GodTier ML</option>
                        <option value="TECHNICAL_ONLY">Technical</option>
                    </select>
                </div>
                <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                    <div>
                        <label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest">Stop Loss (%)</label>
                        <div class="text-[8px] text-gray-500 uppercase font-bold">Auto-close threshold</div>
                    </div>
                    <input type="number" id="stop-loss-pct" class="w-16 bg-black border border-kalshi-border rounded-lg py-1.5 px-2 text-xs text-white font-bold text-center focus:border-kalshi-blue focus:outline-none" min="1" max="100" inputmode="numeric">
                </div>
                <div class="flex justify-between items-center border-b border-kalshi-border/50 pb-3">
                    <div>
                        <label class="text-[11px] font-bold text-purple-400 uppercase tracking-widest">Auto Force</label>
                        <div class="text-[8px] text-gray-500 uppercase font-bold">Always copy AI (ignore conf)</div>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer gap-2">
                      <span id="force-trade-text" class="text-[9px] font-bold text-gray-500 uppercase tracking-widest">OFF</span>
                      <input type="checkbox" id="force-trade-toggle" class="sr-only peer" onchange="document.getElementById('force-trade-text').innerText = this.checked ? 'ON' : 'OFF'; document.getElementById('force-trade-text').className = this.checked ? 'text-[9px] font-bold text-purple-400 uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';">
                      <div class="w-10 h-5 bg-gray-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[41px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-500"></div>
                    </label>
                </div>
                <div class="flex justify-between items-center pb-2">
                    <div>
                        <label class="text-[11px] font-bold text-kalshi-blue uppercase tracking-widest">1-Click Trade</label>
                        <div class="text-[8px] text-gray-500 uppercase font-bold">Skip confirm popups</div>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer gap-2">
                      <span id="one-click-text" class="text-[9px] font-bold text-gray-500 uppercase tracking-widest">OFF</span>
                      <input type="checkbox" id="one-click-toggle" class="sr-only peer" onchange="document.getElementById('one-click-text').innerText = this.checked ? 'ON' : 'OFF'; document.getElementById('one-click-text').className = this.checked ? 'text-[9px] font-bold text-kalshi-blue uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';">
                      <div class="w-10 h-5 bg-gray-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[41px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-kalshi-blue"></div>
                    </label>
                </div>
                
                <button onclick="saveUserConfig()" class="w-full mt-2 py-3.5 bg-kalshi-blue/10 border border-kalshi-blue/40 text-kalshi-blue hover:bg-kalshi-blue/20 active:bg-kalshi-blue/30 active:scale-95 font-black text-[10px] uppercase tracking-widest rounded-xl transition-all shadow-[0_0_15px_rgba(0,82,255,0.15)]">Save Configuration</button>
            </div>
        </div>
        
        <!-- Hidden input for manual trade fallback if needed by JS -->
        <input type="hidden" id="trade-amount" value="50">

        <!-- API Settings (Collapsible) -->
        <div class="mx-4 mb-6 bg-[#131b2c] border border-kalshi-border rounded-2xl overflow-hidden shadow-lg">
            <details class="group">
                <summary class="bg-black/40 px-4 py-3 cursor-pointer outline-none flex justify-between items-center list-none [&::-webkit-details-marker]:hidden">
                    <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">API Credentials</span>
                    <svg class="w-4 h-4 text-gray-500 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                </summary>
                <div class="p-4 border-t border-kalshi-border space-y-3">
                    <div>
                        <label class="block text-[9px] font-bold text-gray-500 uppercase tracking-widest mb-1.5">Key ID</label>
                        <input type="text" id="kalshi-key" class="w-full bg-black border border-kalshi-border rounded-lg px-3 py-2.5 text-xs text-white focus:border-kalshi-blue focus:outline-none" placeholder="e.g. 5f4dcc3b5...">
                    </div>
                    <div>
                        <label class="block text-[9px] font-bold text-gray-500 uppercase tracking-widest mb-1.5">Private Key (PEM)</label>
                        <textarea id="kalshi-priv" rows="3" class="w-full bg-black border border-kalshi-border rounded-lg px-3 py-2.5 text-[10px] font-mono text-gray-400 focus:border-kalshi-blue focus:outline-none" placeholder="-----BEGIN PRIVATE KEY-----"></textarea>
                    </div>
                    <button onclick="saveKeys()" class="w-full py-3 bg-gray-800 hover:bg-gray-700 active:scale-95 text-white font-bold text-[10px] uppercase tracking-widest rounded-xl transition-all mt-1">Update Keys</button>
                </div>
            </details>
        </div>

        <!-- Recent Trades -->
        <div class="mx-4 mb-6">
            <div class="flex justify-between items-end mb-2 px-1">
                <h3 class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Recent Executions</h3>
                <a href="/trades.html" class="text-[9px] font-bold text-kalshi-blue uppercase tracking-wider">View All</a>
            </div>
            
            <div class="bg-[#131b2c] border border-kalshi-border rounded-xl overflow-hidden shadow-lg">
                <table class="w-full text-left text-[10px]">
                    <thead class="bg-black/60 text-gray-500 text-[8px] uppercase tracking-widest border-b border-kalshi-border">
                        <tr>
                            <th class="py-2.5 px-3 font-bold">Time</th>
                            <th class="py-2.5 px-3 font-bold text-center">Side</th>
                            <th class="py-2.5 px-3 font-bold text-center">Strike</th>
                            <th class="py-2.5 px-3 font-bold text-right">PnL</th>
                        </tr>
                    </thead>
                    <tbody id="trades-body" class="divide-y divide-kalshi-border/50">
                        <!-- Trades Injected Here -->
                    </tbody>
                </table>
            </div>
        </div>

    </main>

    <!-- App JavaScript -->
    <script>
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
                    body: JSON.stringify({ direction: direction, count: Math.max(1, Math.floor(amt)) })
                });
                const data = await res.json();
                if(res.ok) {
                    if(!oneClick) alert(`Success! Bought ${data.count} ${direction.toUpperCase()} contracts.`);
                    loadDashboard();
                } else {
                    alert(`Failed: ${data.detail}`);
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
                    alert(`Failed: ${data.detail}`);
                }
            } catch(e) {
                alert("Network error.");
            }
        }

        async function saveUserConfig() {
            const size = parseFloat(document.getElementById('trade-size-dollars').value) || 50.0;
            const sl = parseFloat(document.getElementById('stop-loss-pct').value) || 10.0;
            const toggleEl = document.getElementById('one-click-toggle');
            const oneClick = toggleEl ? toggleEl.checked : false;
            const forceEl = document.getElementById('force-trade-toggle');
            const autoForce = forceEl ? forceEl.checked : false;
            const tStyle = document.getElementById('trading-style').value;
            const sSource = document.getElementById('signal-source').value;
            
            try {
                const res = await fetch('/api/auth/user/config', {
                    method: "POST",
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                    body: JSON.stringify({ trade_size_dollars: size, stop_loss_pct: sl, one_click_trade: oneClick, auto_force_trade: autoForce, trading_style: tStyle, signal_source: sSource })
                });
                if(res.ok) {
                    alert("Preferences Saved!");
                }
            } catch(e) {}
        }

        async function saveKeys() {
            const keyId = document.getElementById('kalshi-key').value;
            const privKey = document.getElementById('kalshi-priv').value;
            if(!keyId || !privKey) return alert("Please fill both key fields.");
            try {
                const res = await fetch('/api/auth/user/keys', {
                    method: "POST",
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                    body: JSON.stringify({ key_id: keyId, private_key: privKey })
                });
                if(res.ok) {
                    alert("Keys saved securely.");
                    document.getElementById('kalshi-key').value = '';
                    document.getElementById('kalshi-priv').value = '';
                }
            } catch(e) {}
        }

        function fillMLCard(lastMLData) {
            if(!lastMLData) return;
            document.getElementById('popup-bias').innerText = lastMLData.primary_bias || '--';
            document.getElementById('popup-conf').innerText = `${lastMLData.confidence_percent || 0}%`;
            document.getElementById('popup-prob').innerText = `${((lastMLData.predicted_probability || 0)*100).toFixed(1)}%`;
            
            let confColor = 'text-gray-400';
            if(lastMLData.confidence_percent >= 60) confColor = 'text-kalshi-green';
            else if(lastMLData.confidence_percent <= 40) confColor = 'text-kalshi-red';
            document.getElementById('popup-conf').className = `text-xs font-black ${confColor}`;
            
            let summaryText = lastMLData.summary ? lastMLData.summary : `Model predicts ${lastMLData.primary_bias} with ${((lastMLData.predicted_probability || 0)*100).toFixed(1)}% probability.`;
            document.getElementById('popup-summary').innerText = summaryText;
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
                    document.getElementById('val-balance').innerText = `$${s.paper_balance.toFixed(2)}`;
                    document.getElementById('val-balance').classList.remove('text-kalshi-red');
                } else {
                    if (s.balance_dollars !== undefined) {
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
                
                const oneClickEl = document.getElementById('one-click-toggle');
                if (oneClickEl && s.one_click_trade !== undefined) {
                    oneClickEl.checked = !!s.one_click_trade;
                    document.getElementById('one-click-text').innerText = oneClickEl.checked ? 'ON' : 'OFF';
                    document.getElementById('one-click-text').className = oneClickEl.checked ? 'text-[9px] font-bold text-kalshi-blue uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';
                }
                const forceEl = document.getElementById('force-trade-toggle');
                if (forceEl && s.auto_force_trade !== undefined) {
                    forceEl.checked = !!s.auto_force_trade;
                    document.getElementById('force-trade-text').innerText = forceEl.checked ? 'ON' : 'OFF';
                    document.getElementById('force-trade-text').className = forceEl.checked ? 'text-[9px] font-bold text-purple-400 uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';
                }

                // Recent trades
                const tbody = document.getElementById('trades-body');
                if (tbody) {
                    tbody.innerHTML = '';
                    const recent = (s.recent_trades || []).slice(0, 5);
                    if (recent.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="4" class="py-4 text-center text-[9px] text-gray-600 font-bold uppercase tracking-widest">No recent trades</td></tr>';
                    } else {
                        recent.forEach(t => {
                            const sideColor = t.side === 'yes' ? 'text-kalshi-green' : 'text-kalshi-red';
                            const pnlColor = t.pnl_dollars >= 0 ? 'text-kalshi-green' : 'text-kalshi-red';
                            const pnlStr = t.pnl_dollars >= 0 ? `+$${t.pnl_dollars.toFixed(2)}` : `-$${Math.abs(t.pnl_dollars).toFixed(2)}`;
                            tbody.innerHTML += `
                                <tr class="hover:bg-white/5 transition-colors">
                                    <td class="py-2.5 px-3 text-gray-400 tabular-nums">${t.time}</td>
                                    <td class="py-2.5 px-3 font-bold text-center ${sideColor} uppercase tracking-wider">${t.side}</td>
                                    <td class="py-2.5 px-3 text-white text-center font-mono">${t.strike}</td>
                                    <td class="py-2.5 px-3 font-black text-right ${pnlColor} tabular-nums">${pnlStr}</td>
                                </tr>
                            `;
                        });
                    }
                }
            } catch(e){}
        }

        async function pollKalshi() {
            try {
                const res = await fetch('/api/kalshi/market_data');
                if(!res.ok) return;
                const data = await res.json();

                const tData = data.ticker_data;
                if(tData && tData.price) {
                    document.getElementById('live-btc-price').innerText = '$' + parseFloat(tData.price).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    document.getElementById('live-btc-price').classList.remove('animate-pulse');
                }

                if (data.target_price) {
                    document.getElementById('kalshi-target').innerText = '$' + data.target_price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    const currentYesProb = data.yes_prob;
                    const currentNoProb = data.no_prob;
                    document.getElementById('kalshi-yes').innerText = currentYesProb + "%";
                    document.getElementById('kalshi-no').innerText = currentNoProb + "%";
                } else {
                    document.getElementById('kalshi-target').innerText = "--";
                    document.getElementById('kalshi-yes').innerText = "--";
                    document.getElementById('kalshi-no').innerText = "--";
                }

                if(data.minutes_remaining !== undefined) {
                    const mins = Math.floor(data.minutes_remaining);
                    const secs = Math.floor((data.minutes_remaining - mins) * 60);
                    document.getElementById('kalshi-time').innerText = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
                } else {
                    document.getElementById('kalshi-time').innerText = "--:--";
                }

                if(data.ml_reasoning) {
                    document.getElementById('ml-status-bubble').innerText = data.ml_reasoning.primary_bias;
                    document.getElementById('ml-status-bubble').className = "text-[8px] font-bold px-2 py-0.5 bg-black rounded-full border border-purple-500 text-purple-300 uppercase tracking-widest shadow-[0_0_10px_rgba(168,85,247,0.3)]";
                    fillMLCard(data.ml_reasoning);
                } else {
                    document.getElementById('ml-status-bubble').innerText = "STANDBY";
                    document.getElementById('ml-status-bubble').className = "text-[8px] font-bold px-2 py-0.5 bg-black rounded-full border border-gray-600 text-gray-500 uppercase tracking-widest";
                }
            } catch(e) {}
        }

        pollKalshi();
        loadDashboard();
        setInterval(pollKalshi, 1000);
        setInterval(loadDashboard, 1000);
    </script>
</body>
</html>
"""

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(new_html)
print("Dashboard completely rewritten!")
