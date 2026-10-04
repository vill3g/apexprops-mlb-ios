/* ShadowTrade AI — AI Backtesting Engine ("Time Machine") + Dynamic ATR readout.
 * Self-contained: builds its modal on first open; talks to /api/backtest/* and /api/risk/atr.
 */
(function () {
    'use strict';

    const API = () => (window.API_BASE_URL || '');
    const authHeaders = (json) => {
        const h = { 'Authorization': 'Bearer ' + (localStorage.getItem('saas_token') || '') };
        if (json) h['Content-Type'] = 'application/json';
        return h;
    };
    const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const money = (v) => (v >= 0 ? '+$' : '-$') + Math.abs(Number(v) || 0).toFixed(2);
    const pnlCls = (v) => (Number(v) >= 0 ? 'text-emerald-400' : 'text-rose-400');
    const ALL_ASSETS = ['BTC', 'ETH', 'SOL', 'DOGE', 'GOLD', 'NDQ', 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'];

    let built = false;
    let running = false;
    let defaultsLoaded = false;

    function build() {
        if (built) return;
        built = true;
        const el = document.createElement('div');
        el.id = 'backtestModal';
        el.className = 'fixed inset-0 z-[1000] hidden flex flex-col bg-[#0a0e17]';
        el.innerHTML = `
<div class="shrink-0 z-10 bg-black/80 border-b border-kalshi-border px-4 py-3 flex justify-between items-center gap-2" style="padding-top: calc(0.75rem + env(safe-area-inset-top, 0px));">
    <div class="flex flex-col min-w-0">
        <h2 class="text-white font-black tracking-wider uppercase text-sm flex items-center gap-2 truncate"><span>⏳</span> AI Time Machine</h2>
        <span class="text-[9px] text-gray-500 font-bold tracking-widest uppercase truncate">Replay your real trades under different risk settings</span>
    </div>
    <button onclick="closeBacktestModal()" class="shrink-0 flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 text-gray-300 rounded-lg hover:bg-gray-700 active:scale-95 transition-all cursor-pointer">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path></svg>
        <span class="text-xs font-bold uppercase tracking-wider">Back</span>
    </button>
</div>
<div class="flex-1 overflow-y-auto p-4 custom-scrollbar max-w-4xl mx-auto w-full space-y-4" style="padding-bottom: calc(2rem + env(safe-area-inset-bottom, 0px));">
    <div class="bg-[#0c0c10] border border-kalshi-border rounded-xl p-4 shadow-md space-y-3">
        <h3 class="text-xs font-black text-white uppercase tracking-wider flex items-center gap-1.5"><span>🎛️</span> Simulation Settings</h3>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <label class="flex flex-col gap-1">
                <span class="text-[9px] font-bold text-gray-500 uppercase tracking-widest">Lookback</span>
                <select id="bt-days" class="bg-black/40 border border-white/10 rounded-lg px-2 py-2 text-xs font-mono text-white outline-none">
                    <option value="7">7 days</option><option value="14">14 days</option><option value="30" selected>30 days</option>
                </select>
            </label>
            <label class="flex flex-col gap-1">
                <span class="text-[9px] font-bold text-gray-500 uppercase tracking-widest">Model</span>
                <select id="bt-model" class="bg-black/40 border border-white/10 rounded-lg px-2 py-2 text-xs font-mono text-white outline-none"><option value="ALL">All models</option></select>
            </label>
            <label class="flex flex-col gap-1">
                <span class="text-[9px] font-bold text-gray-500 uppercase tracking-widest">Trade Size ($)</span>
                <input id="bt-size" type="number" min="0" step="1" placeholder="as traded" inputmode="decimal" class="bg-black/40 border border-white/10 rounded-lg px-2 py-2 text-xs font-mono text-white outline-none">
            </label>
            <label class="flex items-center justify-between gap-2 bg-black/40 border border-white/10 rounded-lg px-2 py-2 mt-4 cursor-pointer">
                <span class="text-[10px] font-bold text-gray-300">⚖️ Kelly</span>
                <input id="bt-kelly" type="checkbox" class="w-4 h-4 accent-cyan-500">
            </label>
        </div>
        <div class="grid grid-cols-2 gap-3">
            <div class="bg-black/30 border border-white/5 rounded-lg p-2.5 space-y-1.5">
                <div class="flex items-center justify-between">
                    <span class="text-[10px] font-bold text-emerald-300">🎯 Take Profit</span>
                    <input id="bt-tp-on" type="checkbox" checked class="w-4 h-4 accent-emerald-500">
                </div>
                <div class="flex items-center gap-2">
                    <input id="bt-tp" type="range" min="5" max="200" step="5" value="20" class="flex-1 accent-emerald-500">
                    <span id="bt-tp-val" class="w-10 text-right text-xs font-mono font-bold text-white">20%</span>
                </div>
            </div>
            <div class="bg-black/30 border border-white/5 rounded-lg p-2.5 space-y-1.5">
                <div class="flex items-center justify-between">
                    <span class="text-[10px] font-bold text-rose-300">🛑 Stop Loss</span>
                    <input id="bt-sl-on" type="checkbox" checked class="w-4 h-4 accent-rose-500">
                </div>
                <div class="flex items-center gap-2">
                    <input id="bt-sl" type="range" min="5" max="95" step="5" value="50" class="flex-1 accent-rose-500">
                    <span id="bt-sl-val" class="w-10 text-right text-xs font-mono font-bold text-white">50%</span>
                </div>
            </div>
        </div>
        <div>
            <div class="text-[9px] font-bold text-gray-500 uppercase tracking-widest mb-1.5">Assets (none selected = all)</div>
            <div id="bt-assets" class="flex flex-wrap gap-1.5"></div>
        </div>
        <label class="flex items-center gap-2 text-[10px] text-gray-400 cursor-pointer">
            <input id="bt-manual" type="checkbox" class="w-3.5 h-3.5 accent-cyan-500"> Include my manual trades
        </label>
        <button id="bt-run" onclick="runBacktest()" class="w-full py-2.5 bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 text-white rounded-lg active:scale-95 transition-all font-black uppercase tracking-wider text-xs flex items-center justify-center gap-2 cursor-pointer">
            <span>⏳</span> Run Time Machine
        </button>
    </div>
    <div id="bt-results" class="space-y-4"></div>
</div>`;
        document.body.appendChild(el);

        const bindRange = (id, out) => {
            const r = document.getElementById(id), o = document.getElementById(out);
            r.addEventListener('input', () => { o.textContent = r.value + '%'; });
        };
        bindRange('bt-tp', 'bt-tp-val');
        bindRange('bt-sl', 'bt-sl-val');
        renderAssetChips([]);
    }

    function renderAssetChips(available) {
        const box = document.getElementById('bt-assets');
        if (!box) return;
        const selected = new Set([...box.querySelectorAll('button[data-on="1"]')].map(b => b.dataset.asset));
        const list = available && available.length ? available : ALL_ASSETS;
        box.innerHTML = list.map(a => {
            const on = selected.has(a);
            return `<button type="button" data-asset="${esc(a)}" data-on="${on ? 1 : 0}" class="bt-chip px-2 py-1 rounded-md text-[10px] font-mono font-bold border transition-all ${on ? 'bg-cyan-500/20 border-cyan-400/60 text-cyan-200' : 'bg-black/30 border-white/10 text-gray-400'}">${esc(a)}</button>`;
        }).join('');
        box.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
            const on = b.dataset.on !== '1';
            b.dataset.on = on ? '1' : '0';
            b.className = `bt-chip px-2 py-1 rounded-md text-[10px] font-mono font-bold border transition-all ${on ? 'bg-cyan-500/20 border-cyan-400/60 text-cyan-200' : 'bg-black/30 border-white/10 text-gray-400'}`;
        }));
    }

    async function loadDefaults() {
        if (defaultsLoaded) return;
        try {
            const res = await fetch(API() + '/api/backtest/defaults', { headers: authHeaders() });
            if (!res.ok) return;
            const d = await res.json();
            const set = (id, v) => { const e = document.getElementById(id); if (e && v != null) e.value = v; };
            set('bt-tp', Math.round(d.tp_pct)); document.getElementById('bt-tp-val').textContent = Math.round(d.tp_pct) + '%';
            set('bt-sl', Math.round(d.sl_pct)); document.getElementById('bt-sl-val').textContent = Math.round(d.sl_pct) + '%';
            document.getElementById('bt-tp-on').checked = !!d.tp_enabled;
            document.getElementById('bt-sl-on').checked = !!d.sl_enabled;
            document.getElementById('bt-kelly').checked = !!d.use_kelly;
            if (d.trade_size_dollars) set('bt-size', d.trade_size_dollars);
            defaultsLoaded = true;
        } catch (e) { /* form keeps its built-in defaults */ }
    }

    window.openBacktestModal = async function () {
        document.getElementById('profileDropdown')?.classList.add('hidden');
        build();
        document.getElementById('backtestModal').classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        await loadDefaults();
    };

    window.closeBacktestModal = function () {
        document.getElementById('backtestModal')?.classList.add('hidden');
        document.body.style.overflow = 'auto';
    };

    function sparkline(sim, act) {
        const all = [...sim, ...act, 0];
        if (sim.length < 2 && act.length < 2) return '<div class="text-[10px] text-gray-500 font-mono text-center py-6">Not enough trades to chart</div>';
        const W = 600, H = 160, P = 6;
        const min = Math.min(...all), max = Math.max(...all), span = (max - min) || 1;
        const path = (pts) => pts.map((v, i) => `${i ? 'L' : 'M'}${(P + i * (W - 2 * P) / Math.max(1, pts.length - 1)).toFixed(1)},${(H - P - (v - min) / span * (H - 2 * P)).toFixed(1)}`).join(' ');
        const zeroY = (H - P - (0 - min) / span * (H - 2 * P)).toFixed(1);
        return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" class="w-full h-40">
            <line x1="0" y1="${zeroY}" x2="${W}" y2="${zeroY}" stroke="#334155" stroke-dasharray="4,4" stroke-width="1"/>
            ${act.length > 1 ? `<path d="${path(act)}" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="5,4"/>` : ''}
            ${sim.length > 1 ? `<path d="${path(sim)}" fill="none" stroke="#22d3ee" stroke-width="2.5" stroke-linejoin="round"/>` : ''}
        </svg>`;
    }

    function statCard(label, value, cls) {
        return `<div class="bg-black/30 border border-white/5 rounded-lg p-2.5 text-center">
            <div class="text-[8px] font-bold text-gray-500 uppercase tracking-widest mb-0.5">${esc(label)}</div>
            <div class="text-sm font-black tabular-nums ${cls || 'text-white'}">${value}</div></div>`;
    }

    function renderResults(r) {
        const box = document.getElementById('bt-results');
        if (!box) return;
        if (!r.sample_size) {
            box.innerHTML = `<div class="bg-[#0c0c10] border border-kalshi-border rounded-xl p-6 text-center text-xs text-gray-400 font-mono">No resolvable trades match these filters in the selected window.${r.unresolved ? ` (${r.unresolved} still awaiting official settlement)` : ''}</div>`;
            return;
        }
        const s = r.simulated, a = r.actual, imp = r.improvement;
        const kinds = Object.entries(r.exit_breakdown || {}).map(([k, v]) => `<span class="px-1.5 py-0.5 rounded bg-white/5 border border-white/10">${esc(k.replace(/_/g, ' '))}: ${v}</span>`).join(' ');
        const best = r.best;
        const bestHtml = best ? `
            <div class="bg-gradient-to-r from-purple-950/40 to-cyan-950/30 border border-cyan-500/30 rounded-xl p-4 space-y-2">
                <div class="text-xs font-black text-cyan-200 uppercase tracking-wider flex items-center gap-1.5"><span>🏆</span> Best Combo Found (grid search)</div>
                <div class="text-[11px] text-gray-300 font-mono">TP <b class="text-white">${best.tp_pct == null ? 'OFF' : best.tp_pct + '%'}</b> · SL <b class="text-white">${best.sl_pct == null ? 'OFF' : best.sl_pct + '%'}</b>
                 → <b class="${pnlCls(best.net_pnl)}">${money(best.net_pnl)}</b> · ${best.win_rate}% WR over ${best.trades} trades</div>
                <button onclick="applyBacktestBest()" class="px-3 py-1.5 rounded-lg bg-cyan-600/30 hover:bg-cyan-600/50 border border-cyan-400/40 text-[10px] font-black uppercase tracking-wider text-cyan-100 active:scale-95 transition-all cursor-pointer">Load into simulator</button>
            </div>` : '';
        const assetRows = (r.by_asset || []).map(x => `
            <tr class="hover:bg-white/5 transition-colors">
                <td class="py-2 font-bold text-gray-200">${esc(x.asset)}</td>
                <td class="py-2 text-center text-gray-400">${x.trades}</td>
                <td class="py-2 text-center font-bold ${x.win_rate >= 50 ? 'text-emerald-400' : 'text-rose-400'}">${x.win_rate}%</td>
                <td class="py-2 text-right font-black ${pnlCls(x.net_pnl)}">${money(x.net_pnl)}</td>
            </tr>`).join('');

        box.innerHTML = `
            <div class="bg-[#0c0c10] border border-kalshi-border rounded-xl p-4 shadow-md space-y-3">
                <div class="flex items-center justify-between gap-2 flex-wrap">
                    <h3 class="text-xs font-black text-white uppercase tracking-wider flex items-center gap-1.5"><span>📊</span> Result · ${r.sample_size} trades</h3>
                    <span class="text-[10px] font-mono font-black px-2 py-1 rounded-lg border ${imp >= 0 ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300' : 'bg-rose-500/10 border-rose-500/40 text-rose-300'}">${money(imp)} vs. what actually happened</span>
                </div>
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    ${statCard('Simulated PnL', money(s.net_pnl), pnlCls(s.net_pnl))}
                    ${statCard('Actual PnL', money(a.net_pnl), pnlCls(a.net_pnl))}
                    ${statCard('Sim Win Rate', s.win_rate + '%', s.win_rate >= 50 ? 'text-emerald-400' : 'text-rose-400')}
                    ${statCard('Sim Max Drawdown', '-$' + Number(s.max_drawdown || 0).toFixed(2), 'text-rose-300')}
                    ${statCard('Profit Factor', Number(s.profit_factor || 0).toFixed(2))}
                    ${statCard('Avg Win', '+$' + Number(s.avg_win || 0).toFixed(2), 'text-emerald-400')}
                    ${statCard('Avg Loss', '-$' + Number(s.avg_loss || 0).toFixed(2), 'text-rose-400')}
                    ${statCard('Kelly Skipped', r.kelly_skipped || 0, 'text-amber-300')}
                </div>
                <div class="bg-black/30 border border-white/5 rounded-lg p-2">
                    <div class="flex items-center gap-3 text-[9px] font-mono text-gray-400 px-1 pb-1">
                        <span class="flex items-center gap-1"><span class="inline-block w-3 h-0.5 bg-cyan-400"></span> Simulated</span>
                        <span class="flex items-center gap-1"><span class="inline-block w-3 h-0.5 bg-slate-500"></span> Actual</span>
                    </div>
                    ${sparkline(r.equity_sim || [], r.equity_actual || [])}
                </div>
                <div class="flex flex-wrap gap-1.5 text-[9px] font-mono text-gray-400">${kinds}</div>
            </div>
            ${bestHtml}
            <div class="bg-[#0c0c10] border border-kalshi-border rounded-xl p-4 shadow-md space-y-2">
                <h3 class="text-xs font-black text-white uppercase tracking-wider flex items-center gap-1.5"><span>🪙</span> Simulated PnL by Asset</h3>
                <table class="w-full text-left font-mono text-[10px]">
                    <thead><tr class="text-gray-500 border-b border-white/5 uppercase text-[8px] tracking-wider">
                        <th class="pb-2">Asset</th><th class="pb-2 text-center">Trades</th><th class="pb-2 text-center">Win Rate</th><th class="pb-2 text-right">Net PnL</th>
                    </tr></thead>
                    <tbody class="divide-y divide-white/5">${assetRows}</tbody>
                </table>
            </div>
            <div class="text-[9px] leading-relaxed text-gray-500 font-mono bg-black/30 border border-white/5 rounded-lg p-3">
                ⓘ Replays your real closed trades against their official Kalshi outcomes. Stops are assumed to fire before targets when both
                were touched, and fill 2¢ below the trigger. The highest price each contract reached isn't recorded, so the benefit of
                Take Profit is <b>under</b>-estimated. Fees are not included. Treat results as directional, not exact.
                ${r.unresolved ? `${r.unresolved} trade(s) excluded: awaiting official settlement.` : ''} Computed in ${r.elapsed_ms} ms.
            </div>`;
        window._lastBacktest = r;
    }

    window.applyBacktestBest = function () {
        const b = window._lastBacktest && window._lastBacktest.best;
        if (!b) return;
        const tpOn = b.tp_pct != null, slOn = b.sl_pct != null;
        document.getElementById('bt-tp-on').checked = tpOn;
        document.getElementById('bt-sl-on').checked = slOn;
        if (tpOn) { document.getElementById('bt-tp').value = b.tp_pct; document.getElementById('bt-tp-val').textContent = b.tp_pct + '%'; }
        if (slOn) { document.getElementById('bt-sl').value = b.sl_pct; document.getElementById('bt-sl-val').textContent = b.sl_pct + '%'; }
        window.runBacktest();
    };

    window.runBacktest = async function () {
        if (running) return;
        running = true;
        const btn = document.getElementById('bt-run');
        const box = document.getElementById('bt-results');
        if (btn) { btn.disabled = true; btn.classList.add('opacity-60'); btn.innerHTML = '<span class="animate-spin inline-block">⏳</span> Simulating…'; }
        try {
            const assets = [...document.querySelectorAll('#bt-assets button[data-on="1"]')].map(b => b.dataset.asset);
            const sizeVal = parseFloat(document.getElementById('bt-size').value);
            const body = {
                days: parseInt(document.getElementById('bt-days').value, 10) || 30,
                model: document.getElementById('bt-model').value || 'ALL',
                tp_pct: parseFloat(document.getElementById('bt-tp').value),
                sl_pct: parseFloat(document.getElementById('bt-sl').value),
                tp_enabled: document.getElementById('bt-tp-on').checked,
                sl_enabled: document.getElementById('bt-sl-on').checked,
                use_kelly: document.getElementById('bt-kelly').checked,
                include_manual: document.getElementById('bt-manual').checked,
                trade_size_dollars: sizeVal > 0 ? sizeVal : null,
                assets,
                optimize: true,
            };
            const res = await fetch(API() + '/api/backtest/run', { method: 'POST', headers: authHeaders(true), body: JSON.stringify(body) });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.detail || ('HTTP ' + res.status));

            // Refresh model / asset filters from what actually exists in the user's history.
            const modelSel = document.getElementById('bt-model');
            const cur = modelSel.value;
            modelSel.innerHTML = '<option value="ALL">All models</option>' + (data.models_available || []).map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join('');
            modelSel.value = [...modelSel.options].some(o => o.value === cur) ? cur : 'ALL';
            renderAssetChips(data.assets_available || []);

            renderResults(data);
        } catch (e) {
            if (box) box.innerHTML = `<div class="bg-rose-950/30 border border-rose-500/40 rounded-xl p-4 text-xs text-rose-200 font-mono">⚠️ Backtest failed: ${esc(e.message || e)}</div>`;
        } finally {
            running = false;
            if (btn) { btn.disabled = false; btn.classList.remove('opacity-60'); btn.innerHTML = '<span>⏳</span> Run Time Machine'; }
        }
    };

    // ---- Dynamic ATR readout under the settings toggle (throttled) ----
    let atrLastFetch = 0;
    window.refreshAtrReadout = async function (force) {
        const toggle = document.getElementById('atr-risk-toggle');
        const out = document.getElementById('atr-mult-readout');
        if (!toggle || !out) return;
        if (!toggle.checked) { out.classList.add('hidden'); return; }
        if (!force && Date.now() - atrLastFetch < 60000) { out.classList.remove('hidden'); return; }
        atrLastFetch = Date.now();
        try {
            const res = await fetch(API() + '/api/risk/atr', { headers: authHeaders() });
            if (!res.ok) return;
            const d = await res.json();
            const parts = Object.entries(d.assets || {})
                .filter(([, v]) => v && v.ratio != null)
                .map(([k, v]) => `${k} ${Number(v.multiplier).toFixed(2)}×`);
            out.textContent = parts.length ? ('Live: ' + parts.join(' · ')) : 'Live volatility warming up…';
            out.classList.remove('hidden');
        } catch (e) { /* non-critical */ }
    };
})();
