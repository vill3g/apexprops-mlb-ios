/* ShadowTrader AI: sports trade details.
 *
 * Wraps openTradeDetailsModal(). For a sports trade it replaces the crypto-oriented sections
 * (trading style, RL model, entry catalysts, and a "55% conviction" that was a hard-coded
 * fallback) with:
 *   1. Kalshi event: matchup, the contract held, game time/status, live prices for every side.
 *   2. AI pick at entry: what the bot picked and the confidence/edge it recorded when it bought.
 *   3. AI pick now: a fresh prediction for the event plus the full breakdown the sports AI sends
 *      (line, sportsbook odds, model probability, EV, Kelly units, grade, venue, simulation size).
 * Crypto trades are left exactly as before. Styles: css/mobile-polish.css section 13 (.tsd-*).
 * To revert: remove the <script src="./js/sports-trade-details.js"> tag.
 */
(function () {
    'use strict';

    const esc = (v) => String(v == null ? '' : v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    const num = (v) => { const n = parseFloat(v); return isFinite(n) ? n : null; };
    const cents = (m, side) => {
        if (!m) return null;
        const d = m[side + '_ask_dollars'];
        if (d != null && d !== '') { const v = Math.round(parseFloat(d) * 100); return isFinite(v) ? v : null; }
        const c = m[side + '_ask'];
        if (c != null && c !== '') {
            let v = parseFloat(c);
            if (!isFinite(v)) return null;
            // The market cache sends dollars (0.51), older feeds sent cents (51).
            if (v > 0 && (v < 1 || (/\./.test(String(c)) && v <= 1))) v = v * 100;
            return Math.round(v);
        }
        return null;
    };
    const GENERIC = new Set(['the', 'and', 'city', 'team', 'club', 'vs', 'game', 'wins', 'win', 'will']);
    const tokens = (s) => new Set((String(s || '').toLowerCase().match(/[a-z0-9]+/g) || []).filter(w => w.length >= 3 && !GENERIC.has(w)));
    const sameTeam = (a, b) => {
        if (!a || !b) return false;
        const x = String(a).toLowerCase(), y = String(b).toLowerCase();
        if (x.includes(y) || y.includes(x)) return true;
        const ta = tokens(a), tb = tokens(b);
        for (const w of ta) if (tb.has(w)) return true;
        return false;
    };
    const authHeaders = () => {
        const tok = localStorage.getItem('saas_token');
        return tok ? { 'Authorization': 'Bearer ' + tok } : {};
    };

    // "[Moneyline] Moneyline | AI Edge: Edmonton Oilers (Conf: 70.0%, Edge: 14.0%)"
    function parseReason(reason) {
        const r = String(reason || '');
        const out = {};
        let m = r.match(/^\s*\[([^\]]+)\]\s*([^|]*)/);
        if (m) { out.market = m[1].trim(); out.line = m[2].trim(); }
        m = r.match(/AI Edge:\s*([^(|]+)/i); if (m) out.pick = m[1].trim();
        m = r.match(/Conf:\s*([\d.]+)%/i); if (m) out.conf = parseFloat(m[1]);
        m = r.match(/Edge:\s*(-?[\d.]+)%/i); if (m) out.edge = parseFloat(m[1]);
        return out;
    }

    function eventTickerOf(t) {
        const tk = String(t.event_ticker || (t.metadata && t.metadata.event_ticker) || '');
        if (tk) return tk;
        const parts = String(t.ticker || '').split('-');
        return parts.length >= 3 ? parts.slice(0, -1).join('-') : String(t.ticker || '');
    }

    function findEvent(t, list) {
        const tk = String(t.ticker || ''), ev = eventTickerOf(t);
        return (list || []).find(e => e && (e.ticker === tk || (Array.isArray(e.markets) && e.markets.some(m => m && m.ticker === tk))))
            || (list || []).find(e => e && e.event_ticker === ev && !/Player Prop/i.test(e.prop_type || ''));
    }

    async function loadEvent(t, sport) {
        let e = findEvent(t, window.__sportsEventsCache);
        if (e) return e;
        try {
            const q = sport && sport !== 'SPORTS' ? '&sport=' + encodeURIComponent(sport) : '';
            const res = await fetch((window.API_BASE_URL || '') + '/api/engine/sports/events?t=' + Date.now() + q, { headers: authHeaders(), cache: 'no-store' });
            if (!res.ok) return null;
            const data = await res.json();
            return findEvent(t, data.events);
        } catch (_) { return null; }
    }

    async function loadPrediction(t, sport, title) {
        try {
            const q = '&execute=false' + (sport && sport !== 'SPORTS' ? '&sport=' + encodeURIComponent(sport) : '') + (title ? '&title=' + encodeURIComponent(title) : '');
            const res = await fetch((window.API_BASE_URL || '') + '/api/engine/sports/predict?event_ticker=' + encodeURIComponent(eventTickerOf(t)) + q, { headers: authHeaders() });
            if (!res.ok) return null;
            return await res.json();
        } catch (_) { return null; }
    }

    const MONTH_MAP = { JAN:0, FEB:1, MAR:2, APR:3, MAY:4, JUN:5, JUL:6, AUG:7, SEP:8, OCT:9, NOV:10, DEC:11 };
    function extractEventEpoch(evt, t) {
        if (evt) {
            if (num(evt.start_epoch) != null) return num(evt.start_epoch);
            const md = evt.metadata || {};
            const aiPred = evt.ai_prediction || {};
            const aiMd = aiPred.metadata || {};
            const rawLabel = aiMd.start_epoch || aiMd.start_label || md.start_time || md.game_time || evt.game_time || '';
            if (rawLabel) {
                const ts = Date.parse(rawLabel);
                if (isFinite(ts)) return ts / 1000;
            }
            if (evt.event_date) {
                const ts = Date.parse(evt.event_date + 'T12:00:00Z');
                if (isFinite(ts)) return ts / 1000;
            }
        }
        // Fallback from ticker date (e.g. KXWTAMATCH-26OCT11TAUBOU)
        const tk = String((t && (t.ticker || t.event_ticker)) || (evt && (evt.ticker || evt.event_ticker)) || '');
        const m = tk.match(/-(\d{2})([A-Z]{3})(\d{2})/i);
        if (m) {
            const yr = 2000 + parseInt(m[1], 10);
            const mo = MONTH_MAP[m[2].toUpperCase()];
            const da = parseInt(m[3], 10);
            if (mo != null && da) return Date.UTC(yr, mo, da, 12, 0, 0) / 1000;
        }
        return null;
    }

    function getEventSchedule(evt, t) {
        const isClosed = !t || String(t.status || '').toUpperCase() !== 'OPEN';
        const epoch = extractEventEpoch(evt, t);
        if (!epoch) {
            const dateStr = (evt && evt.event_date) || '';
            if (dateStr) {
                return {
                    et: dateStr,
                    countdown: isClosed ? 'Final / Settled' : 'Scheduled',
                    full: `Scheduled: ${dateStr}`,
                    state: isClosed ? 'final' : 'upcoming'
                };
            }
            return {
                et: '',
                countdown: isClosed ? 'Final / Settled' : 'Scheduled',
                full: isClosed ? 'Final / Settled' : 'Time TBA',
                state: isClosed ? 'final' : 'upcoming'
            };
        }

        const d = new Date(epoch * 1000);
        let etTime = '';
        try {
            etTime = d.toLocaleString('en-US', {
                timeZone: 'America/New_York',
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            }) + ' ET';
        } catch (_) {
            etTime = d.toUTCString();
        }

        const now = Date.now() / 1000;
        const diffSec = epoch - now;
        let countdown = '';
        let state = 'upcoming';

        if (isClosed) {
            countdown = 'Final / Settled';
            state = 'final';
        } else if (diffSec <= -10800) {
            // Started more than 3h ago
            countdown = 'Final / Ending';
            state = 'final';
        } else if (diffSec < 0) {
            const agoM = Math.floor(Math.abs(diffSec) / 60);
            const agoH = Math.floor(agoM / 60);
            const remM = agoM % 60;
            countdown = agoH > 0 ? `Started ${agoH}h ${remM}m ago · Live` : `Started ${agoM}m ago · Live`;
            state = 'live';
        } else {
            const min = Math.floor(diffSec / 60);
            const hrs = Math.floor(min / 60);
            const remMin = min % 60;
            if (hrs >= 24) {
                const days = Math.floor(hrs / 24);
                const rH = hrs % 24;
                countdown = `Starts in ${days}d ${rH}h`;
            } else if (hrs > 0) {
                countdown = `Starts in ${hrs}h ${remMin}m`;
            } else {
                countdown = `Starts in ${min}m`;
            }
            state = 'upcoming';
        }

        return {
            epoch,
            et: etTime,
            countdown,
            full: `${etTime} (${countdown})`,
            state
        };
    }

    function statusOf(evt, t) {
        const sched = getEventSchedule(evt, t);
        if (sched.state === 'final') return { cls: 'tsd-st-final', text: 'Final' };
        if (sched.state === 'live') return { cls: 'tsd-st-live', text: 'Live In-Play' };
        return { cls: 'tsd-st-up', text: 'Upcoming' };
    }

    function row(label, value, cls) {
        if (value == null || value === '' || value === '—') return '';
        return `<div class="tsd-kv"><span>${esc(label)}</span><b class="${cls || ''}">${value}</b></div>`;
    }

    function describe(t, sInfo, parsed) {
        const team = (sInfo && sInfo.team) || parsed.pick || '';
        const pt = (sInfo && sInfo.propType) || parsed.market || 'Moneyline';
        const tk = String(t.ticker || '').toUpperCase();
        const seg = /KXNHL1P/.test(tk) ? '1st period' : /KXNHL2P/.test(tk) ? '2nd period' : /KXNHL3P/.test(tk) ? '3rd period' : /KXMLBF5/.test(tk) ? 'first 5 innings' : '';
        if (pt === 'Player Prop') return team + (sInfo && sInfo.line ? ' · ' + sInfo.line : '');
        if (pt === 'Spread') return team + ' ' + ((sInfo && (sInfo.spreadAmount || sInfo.line)) || 'spread');
        if (/total|o\/u/i.test(pt)) return (sInfo && (sInfo.strikeDetails || sInfo.line)) || team;
        return team + (seg ? ' wins ' + seg : ' to win');
    }


    // ── AI analysis: why the AI likes (or doesn't like) a pick ──────────────────────────
    // The sports AI sends numbers, not prose: model probability, sportsbook odds, edge, EV,
    // Kelly units, grade, venue, source. This turns them into a plain-English explanation.
    // If the AI ever sends written reasoning (metadata.reasoning / analysis / summary) or a
    // factor list (metadata.key_factors / factors / reasons), it is shown as well.
    function americanToProb(odds) {
        const a = parseFloat(String(odds || '').replace(/[^\d.+-]/g, ''));
        if (!isFinite(a) || a === 0) return null;
        return a < 0 ? (-a / (-a + 100)) * 100 : (100 / (a + 100)) * 100;
    }
    function pct(v) { return v == null ? '—' : (Math.round(v * 10) / 10).toFixed(1) + '%'; }

    function aiTextFields(md) {
        const text = md.reasoning || md.analysis || md.summary || md.explanation || md.rationale || '';
        let factors = md.key_factors || md.factors || md.reasons || md.drivers || [];
        if (typeof factors === 'string') factors = factors.split(/\n|;|•/).map(x => x.trim()).filter(Boolean);
        if (!Array.isArray(factors)) factors = [];
        factors = factors.map(f => (f && typeof f === 'object') ? [f.label || f.name || f.factor, f.value || f.detail || f.impact].filter(Boolean).join(': ') : String(f)).filter(Boolean).slice(0, 8);
        return { text: String(text || '').trim(), factors };
    }

    // One explanation format for every sport and market (see fixes/SPORTS_PICKS_FOR_ANTIGRAVITY.md §8):
    // metadata.explain = { market: moneyline|spread|total|period|prop, pick, side, line, segment,
    //   probability (of the picked side, for THIS market), projected, projected_unit, iterations,
    //   method, factors:[{label, detail, impact, unit}], not_used:[], narrative }
    // Older MLB moneyline payloads (win_prob, projected_total, win_impact/total_impact) still work.
    // Minimal, safe markdown for model-written text: escapes first, then **bold**, headings and bullets.
    function mdLite(txt) {
        const lines = String(txt || '').replace(/\r/g, '').split('\n');
        const out = []; let list = false;
        const inline = t => esc(t).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
        lines.forEach(raw => {
            const l = raw.trim();
            const bullet = l.match(/^[*\-\u2022]\s+(.*)$/);
            if (bullet) { if (!list) { out.push('<ul>'); list = true; } out.push(`<li>${inline(bullet[1])}</li>`); return; }
            if (list) { out.push('</ul>'); list = false; }
            if (!l || /^(-{3,}|\*{3,})$/.test(l)) return;
            const h = l.match(/^#{1,6}\s+(.*)$/);
            out.push(h ? `<p class="tsd-md-h"><b>${inline(h[1].replace(/\*\*/g, ''))}</b></p>` : `<p>${inline(l)}</p>`);
        });
        if (list) out.push('</ul>');
        return out.join('');
    }
    // Ignore explain payloads that are errors or generic placeholders (same % for every game,
    // a single 'baseline' factor, no pick). Showing those would present invented numbers as analysis.
    function usableExplain(ex) {
        if (!ex || typeof ex !== 'object' || Array.isArray(ex)) return null;
        if (ex.error || ex.detail) return null;
        const fx = Array.isArray(ex.factors) ? ex.factors : [];
        const real = fx.filter(f => f && !/baseline|placeholder|default|generic|:\s*(starting pitcher|tbd|unknown|n\/a)\s*$/i.test(String(f.label || f.name || f.key || '')) && !(f.impact !== null && f.impact !== undefined && f.impact !== '' && Number(f.impact) === 0));
        const hasNumbers = ex.win_prob != null || (ex.projected != null && Number(ex.projected) !== 0) || ex.projected_total != null || ex.iterations;
        if (!real.length && !ex.narrative && !(ex.pick && hasNumbers)) return null;
        // If the only input that moved the pick is home advantage (every team stat sat at league average),
        // the model had no team data; a 'home team wins' pick isn't analysis.
        if (real.length && real.every(f => /home[- ]?(field|court|ice)?\s*advantage|^home (court|field|ice)/i.test(String(f.label || f.name || '')))) return null;
        if (fx.some(f => /^\s*([\d.]+)\b.*\bvs\s+\1\b/i.test(String((f && f.detail) || ''))) && real.length <= 1) return null;
        // A total explanation whose projection contradicts its own pick (e.g. 'over 8.5' with a
        // 3.4-run projection) is a relabelled moneyline payload, so don't show it as the total's analysis.
        const mk = String(ex.market || '').toLowerCase();
        // A single input moving a game's win chance by 30+ points (or a total by 5+ runs/goals/points
        // in a game model) means the model isn't calibrated; don't present it as the reason.
        if (fx.some(f => { const v = parseFloat(f && f.impact); const u = String((f && f.unit) || '%');
            return isFinite(v) && (u === '%' ? Math.abs(v) >= 30 : Math.abs(v) >= 5); })) return null;
        // Sanity check on the pick's own probability: no game model is 97%+ or 3%- sure, and on a
        // two-sided spread/total (or a moneyline without a draw) the pick must be the likelier side.
        const pr = parseFloat(ex.probability);
        if (isFinite(pr)) {
            if (pr >= 97 || pr <= 3) return null;
            if (pr > 100) return null; // scaled twice (e.g. 7040 for 70.4%)
            const threeWay = ex.draw_prob != null || ex.draw_probability != null || /^draw$/i.test(String(ex.pick || '').trim()) || /draw|tie|3-?way/i.test(JSON.stringify(ex.not_used || []) + ' ' + String(ex.method || '') + ' ' + String(ex.sport || ''));
            if (pr < 50 && (/spread|total|over|under|run ?line|puck ?line/.test(mk) || (!threeWay && /moneyline|^$/.test(mk)))) return null;
            if (threeWay && ex.home_prob != null && ex.away_prob != null && ex.draw_prob != null && pr + 0.05 < Math.max(+ex.home_prob, +ex.away_prob, +ex.draw_prob)) return null;
        }
        if (/total|over|under/.test(mk)) {
            const side = String(ex.side || ex.pick || '').toLowerCase();
            const ln = parseFloat(String(ex.line || '').replace(/[^0-9.\-]/g, ''));
            const pj = parseFloat(ex.projected);
            if (isFinite(ln) && isFinite(pj) && pj > 0 && ((/over/.test(side) && pj < ln - 1) || (/under/.test(side) && pj > ln + 1))) return null;
        }
        const clean = Object.assign({}, ex, { factors: real.map(f => {
            const lb = String(f.label || f.name || f.key || '').replace(/\s*\((home|away)\)\s*$/i, '');
            return Object.assign({}, f, { label: lb });
        }) });
        // 'Home' / 'Away' is not a pick a user can act on; let the card's own team name be used instead.
        if (/^(home|away)$/i.test(String(clean.pick || '').trim())) { delete clean.pick; if (/^(home|away)$/i.test(String(clean.side || '').trim())) delete clean.side; }
        // A baseball game projected under 5 or over 14 total runs is a simulator bug; drop the projection.
        const pjv = parseFloat(clean.projected);
        if (/^runs?$/i.test(String(clean.projected_unit || '')) && isFinite(pjv) && (pjv < 5 || pjv > 14) && !/spread|run ?line/.test(String(clean.market || '').toLowerCase())) {
            delete clean.projected; delete clean.projected_total;
        }
        return clean;
    }
    function explainMarket(ex) {
        const m = String((ex && ex.market) || '').toLowerCase();
        if (!m) return (ex && (ex.win_prob != null || ex.factors)) ? 'moneyline' : '';
        if (/prop|player/.test(m)) return 'prop';
        if (/spread|run ?line|puck ?line|handicap/.test(m)) return 'spread';
        if (/total|over|under|o\/u/.test(m)) return 'total';
        if (/period|half|quarter|innings|f5|segment/.test(m)) return 'period';
        return 'moneyline';
    }
    function cardMarket(kind, segment) {
        const k = String(kind || '').toLowerCase();
        if (segment || /period/.test(k)) return 'period';
        if (/prop/.test(k)) return 'prop';
        if (/spread/.test(k)) return 'spread';
        if (/total|o\/u/.test(k)) return 'total';
        if (/futures/.test(k)) return 'futures';
        return 'moneyline';
    }
    function impactOf(f, mk, ex) {
        let v = num(f.impact), unit = f.unit || '';
        if (v == null && mk === 'total') { v = num(f.total_impact); unit = unit || (ex && ex.projected_unit) || 'runs'; }
        if (v == null) { v = num(f.win_impact); unit = unit || '%'; }
        if (v == null) return null;
        unit = unit || '%';
        const txt = (v > 0 ? '+' : '') + (Math.abs(v) < 10 ? v.toFixed(1) : v.toFixed(0)) + (unit === '%' ? '%' : ' ' + unit);
        return { v, txt };
    }

    // ctx: { pick, conf, priceC (Kalshi price of the picked side, cents), marketKind, segment, isProp }
    function explainPick(pred, ctx) {
        const md = (pred && pred.metadata) || {};
        const ex = usableExplain(md.explain || (pred && pred.explain));
        const exMk = explainMarket(ex);
        const cardMk = cardMarket(ctx.marketKind, ctx.segment);
        // An explanation made for this exact market supplies its own probability and wording.
        const exact = !!(ex && exMk && exMk === cardMk);
        let pick = ctx.pick || (pred && pred.predicted_team) || md.name || '';
        let conf = ctx.conf != null ? ctx.conf : num(pred && pred.confidence_pct);
        if (exact) {
            if (num(ex.probability) != null) conf = num(ex.probability);
            if (ex.line || ex.pick) {
                const lp = String(ex.line || ''), pp = String(ex.pick || '');
                pick = !lp ? pp : (!pp || lp.toLowerCase().includes(pp.toLowerCase())) ? lp : pp + ' · ' + lp;
            }
            ctx = Object.assign({}, ctx, { segment: '' });
        }
        const priceC = ctx.priceC;
        const bookProb = americanToProb(md.odds);
        const src = md.simulation
            ? `a Monte Carlo simulation${md.simulations_count ? ' of ' + Number(md.simulations_count).toLocaleString() + ' games' : ''}`
            : (md.pick_id || md.sportsbook || md.stat_name ? 'the ApexProps model' : 'the sports AI');
        const parts = [];
        const what = exact ? esc(pick) : (md.line && md.line !== pick ? `${esc(pick)} (${esc(md.line)})` : esc(pick));
        const srcTxt = exact && ex.iterations ? `${Number(ex.iterations).toLocaleString()} simulations` : src;
        if (conf != null) parts.push(`<p>Based on ${esc(srcTxt)}, the AI gives <b>${what}</b> a <b>${pct(conf)}</b> chance${ctx.segment ? ' to win the full game' : ''}.</p>`);
        if (exact && num(ex.projected) != null) {
            const lineNum = String(ex.line || '').match(/(\d+(?:\.\d+)?)\+?/);
            parts.push(`<p>Model projection: <b>${esc(num(ex.projected).toFixed(1))}${ex.projected_unit ? ' ' + esc(ex.projected_unit) : ''}</b>${lineNum ? ` (line ${esc(lineNum[0])})` : ''}.</p>`);
        }

        const cmp = [];
        if (priceC != null) cmp.push(ctx.segment
            ? `Kalshi prices ${esc(pick)} to win the ${esc(ctx.segment.toLowerCase())} at <b>${priceC}¢</b>, a different bet`
            : `Kalshi prices it at <b>${priceC}¢</b> (${priceC}% implied)`);
        if (bookProb != null) cmp.push(`${esc(md.sportsbook || 'the sportsbook')} at <b>${esc(md.odds)}</b> (${pct(bookProb)} implied)`);
        if (cmp.length) parts.push(`<p>${cmp.join('; ')}.</p>`);

        let verdict = '', vcls = 'tsd-v-neutral';
        if (ctx.segment) {
            verdict = `This is a ${esc(ctx.segment.toLowerCase())} market. The AI only predicts full games, so treat this as a lean, not a priced pick.`;
        } else if (!exact && ctx.marketKind && /spread|total/i.test(ctx.marketKind) && !/spread|puck|run line|total|over|under/i.test(String(md.type || md.stat_name || (pred && pred.market_type) || ''))) {
            verdict = `The AI's pick is for the game winner; it does not say whether this ${esc(ctx.marketKind.toLowerCase())} hits.`;
        } else if (conf != null && priceC != null) {
            const edge = conf - priceC;
            if (edge >= 5) { verdict = `<b>Value:</b> the model rates this ${edge.toFixed(1)} points more likely than Kalshi's price implies.`; vcls = 'tsd-v-good'; }
            else if (edge >= 0) { verdict = `<b>Thin edge:</b> only ${edge.toFixed(1)} points over Kalshi's price, within normal model error.`; vcls = 'tsd-v-warn'; }
            else { verdict = `<b>No value at this price:</b> Kalshi already prices it ${Math.abs(edge).toFixed(1)} points above the model.`; vcls = 'tsd-v-bad'; }
            if (bookProb != null) {
                const gap = priceC - bookProb;
                if (Math.abs(gap) >= 4) verdict += ` Kalshi is ${Math.abs(gap).toFixed(0)} points ${gap < 0 ? 'cheaper' : 'more expensive'} than the sportsbook line.`;
            }
        } else if (conf != null) {
            verdict = 'No Kalshi price to compare against right now.';
        }
        if (verdict) parts.push(`<div class="tsd-verdict ${vcls}">${verdict}</div>`);

        // ApexProps model breakdown (/api/mlb/explain/{game}): each input's effect on the pick,
        // measured by re-simulating with that input set to league average. Expected at
        // metadata.explain (or pred.explain): {pick, win_prob, projected_total, iterations,
        // method, factors:[{label, detail, win_impact, total_impact}], not_used:[...], narrative}.
        const capper = (pred && pred.metadata && pred.metadata.capper) || (pred && pred.capper);
        const narrative = (ex && ex.narrative) || md.narrative || (capper && capper.capper_thesis) || '';
        const { text, factors } = aiTextFields(md);
        const story = String(narrative || text || '').trim();
        if (story) parts.push(`<div class="tsd-ai-text">${mdLite(story)}</div>`);
        if (ex && Array.isArray(ex.factors) && ex.factors.length) {
            const fxMk = exact ? exMk : (exMk || 'moneyline');
            const rows = ex.factors.slice(0, 8).map(f => {
                const im = impactOf(f, fxMk, ex);
                const chip = !im ? '' : `<span class="tsd-imp ${im.v > 0 ? 'tsd-imp-up' : im.v < 0 ? 'tsd-imp-down' : ''}">${esc(im.txt)}</span>`;
                return `<li class="tsd-fx">${chip}<span><b>${esc(f.label || f.key || '')}</b>${f.detail ? `<em>${esc(f.detail)}</em>` : ''}</span></li>`;
            }).join('');
            const fxTitle = exact || !exMk || exMk === cardMk ? 'What moves the pick' : `What moves the ${exMk === 'moneyline' ? 'game-winner' : exMk} pick`;
            parts.push(`<div class="tsd-fx-h">${fxTitle}${ex.iterations ? ` · ${Number(ex.iterations).toLocaleString()} sims` : ''}</div><ul class="tsd-fx-list">${rows}</ul>`);
            if (ex.method) parts.push(`<p class="tsd-muted">${esc(ex.method)}</p>`);
            if (Array.isArray(ex.not_used) && ex.not_used.length) {
                parts.push(`<details class="tsd-notused"><summary>Not considered by the model (${ex.not_used.length})</summary><ul>${ex.not_used.map(x => `<li>${esc(x)}</li>`).join('')}</ul></details>`);
            }
        } else if (factors.length) {
            parts.push(`<ul class="tsd-factors">${factors.map(f => `<li>${esc(f)}</li>`).join('')}</ul>`);
        }
        if (capper && Array.isArray(capper.capper_notes) && capper.capper_notes.length) {
            const cRows = capper.capper_notes.map(n => `<li class="tsd-fx"><span class="tsd-imp tsd-imp-up">⚔️</span><span><b>${esc(n)}</b></span></li>`).join('');
            parts.push(`<div class="tsd-fx-h">⚡ Master Capper Situational & Head-to-Head Dynamics</div><ul class="tsd-fx-list">${cRows}</ul>`);
        }

        // Editorial & Tactical Intelligence Section
        const tac = (pred && pred.tactical_intel) || (md && md.tactical_intel);
        if (tac && typeof tac === 'object') {
            const tacSrc = tac.source || 'Editorial & Tactical Scouting';
            const tacAlign = tac.alignment;
            const tacBadge = tacAlign === 'AGREES' ? '<span class="spc-tag spc-tag-sharp" style="color:#34d399;background:rgba(16,185,129,0.15)">🟢 Consensus: Agrees with Model</span>'
                : tacAlign === 'DIVERGES' ? '<span class="spc-tag spc-tag-lean" style="color:#fbbf24;background:rgba(245,158,11,0.15)">🟠 Editorial Divergence</span>'
                : '<span class="spc-tag spc-tag-edge" style="color:#60a5fa;background:rgba(59,130,246,0.15)">🛡️ Verified Tactical Lineups</span>';
            
            let tacRows = [];
            if (tac.starting_goalies) {
                tacRows.push(`<li class="tsd-fx"><span class="tsd-imp tsd-imp-up">🥅</span><span><b>Goalies:</b> ${esc(tac.starting_goalies.home || 'TBD')} vs ${esc(tac.starting_goalies.away || 'TBD')}</span></li>`);
            }
            if (tac.tactical_factors && Array.isArray(tac.tactical_factors)) {
                tac.tactical_factors.forEach(tf => {
                    tacRows.push(`<li class="tsd-fx"><span class="tsd-imp tsd-imp-up">📋</span><span><b>${esc(tf.type || 'TACTIC')}:</b> ${esc(tf.label || '')}</span></li>`);
                });
            }
            if (tac.predicted_winner) {
                tacRows.push(`<li class="tsd-fx"><span class="tsd-imp ${tacAlign === 'AGREES' ? 'tsd-imp-up' : 'tsd-imp-down'}">✍️</span><span><b>${esc(tacSrc)} Pick:</b> ${esc(tac.predicted_winner)}</span></li>`);
            }
            parts.push(`<div class="tsd-fx-h">📰 Tactical Intel & Scouting (${esc(tacSrc)}) · ${tacBadge}</div><ul class="tsd-fx-list">${tacRows.join('')}</ul>`);
        }
        if (!story && !(ex && ex.factors && ex.factors.length) && !factors.length && !(capper && capper.capper_notes && capper.capper_notes.length)) {
            parts.push(`<p class="tsd-muted">The AI doesn't send written reasoning yet; this explanation is built from its numbers.</p>`);
        }
        return parts.join('');
    }

    function detailGrid(pred, ctx) {
        const md = (pred && pred.metadata) || {};
        const capper = (pred && pred.metadata && pred.metadata.capper) || (pred && pred.capper);
        const tac = (pred && pred.tactical_intel) || (md && md.tactical_intel);
        const ex = usableExplain(md.explain || (pred && pred.explain));
        const exact = !!(ex && explainMarket(ex) && explainMarket(ex) === cardMarket(ctx.marketKind, ctx.segment));
        const conf = exact && num(ex.probability) != null ? num(ex.probability) : (ctx.conf != null ? ctx.conf : num(pred && pred.confidence_pct));
        if (exact) ctx = Object.assign({}, ctx, { segment: '' });
        const edgeNow = (conf != null && ctx.priceC != null) ? conf - ctx.priceC : null;
        const odds = md.odds ? `${md.odds}${md.sportsbook ? ' (' + md.sportsbook + ')' : ''}` : null;
        const src = md.simulation ? `Simulation${md.simulations_count ? ' · ' + Number(md.simulations_count).toLocaleString() + ' runs' : ''}` : (md.pick_id || md.sportsbook ? 'ApexProps model' : 'Sports AI');
        return `<div class="tsd-grid">
            ${capper && capper.grade ? row('Master Capper', `${esc(capper.grade)} ${esc(capper.stars)} · ${esc(capper.tier_label || '')}`, capper.grade === 'A+' ? 'tsd-pos' : '') : (md.confidence ? row('Grade', esc(md.confidence)) : null)}
            ${row('Model probability', conf != null ? conf.toFixed(1) + '%' : null, conf >= 60 ? 'tsd-pos' : '')}
            ${row('Kalshi price', ctx.priceC != null ? ctx.priceC + '¢' : null)}
            ${row('Edge vs Kalshi', edgeNow != null && !ctx.segment ? (edgeNow >= 0 ? '+' : '') + edgeNow.toFixed(1) + ' pts' : null, edgeNow != null ? (edgeNow >= 0 ? 'tsd-pos' : 'tsd-neg') : '')}
            ${capper && capper.net_ev_pct != null ? row('Net EV (Post-Fee)', (capper.net_ev_pct > 0 ? '+' : '') + Number(capper.net_ev_pct).toFixed(1) + '%', capper.net_ev_pct > 0 ? 'tsd-pos' : 'tsd-neg') : (md.ev != null && md.ev !== '' && String(md.ev) !== '-0.0' && String(md.ev) !== '0.0' ? row('Expected value', esc(md.ev)) : null)}
            ${capper && capper.kelly_bankroll_pct != null ? row('Kelly Stake', Number(capper.kelly_bankroll_pct).toFixed(1) + '% ($' + (capper.recommended_wager != null ? Number(capper.recommended_wager).toFixed(2) : (Number(capper.kelly_bankroll_pct) * 10).toFixed(2)) + ')') : (md.kelly_units ? row('Kelly units', esc(md.kelly_units)) : null)}
            ${tac && tac.alignment ? row('Consensus', tac.alignment === 'AGREES' ? 'Agrees (🟢 ' + esc(tac.source || 'Editorial') + ')' : tac.alignment === 'DIVERGES' ? 'Diverges (🟠 ' + esc(tac.source || 'Editorial') + ')' : 'Confirmed Data (🛡️)', tac.alignment === 'AGREES' ? 'tsd-pos' : tac.alignment === 'DIVERGES' ? 'tsd-neg' : '') : null}
            ${row('Edge vs book', md.edge ? esc(String(md.edge).replace(/(\.\d)\d+%/, '$1%')) : null)}
            ${row('Market', esc(md.stat_name || md.type || (pred && pred.market_type) || ''))}
            ${row('Sportsbook odds', odds ? esc(odds) : null)}
            ${row('Venue', md.venue ? esc(md.venue) : null)}
            ${row(exact && ex.projected != null ? 'Projection' : 'Total (sim)', exact && ex.projected != null ? esc(num(ex.projected).toFixed(1) + (ex.projected_unit ? ' ' + ex.projected_unit : '')) : (md.recommended_total ? esc(md.recommended_total) : (ex && ex.projected_total ? esc(ex.projected_total) + ' runs' : null)))}
            ${row('Source', esc(src))}
        </div>`;
    }


    // A player prop must never show the game's moneyline pick ("Jacksonville 71.8%" on a
    // Receptions market). Returns true when the card is a prop but the pick is game-level.
    window.sportsGameLevelPickOnProp = function (evt, pred) {
        // True when the pick on this card is the GAME's moneyline pick but the card is a player
        // prop, total or spread ("New England 50.5%" on a Total Points market).
        try {
            evt = evt || {};
            const md = evt.metadata || {};
            const tk = String(evt.event_ticker || evt.ticker || '').toUpperCase();
            const series = tk.split('-')[0];
            const kind = String(evt.prop_type || md.prop_type || '');
            const isProp = /player prop/i.test(kind)
                || /^KX(NFL|MLB|NHL|NBA|NCAAF|NCAAB|EPL|MLS)(TD|REC|PASS|RUSH|HRR|HIT|HR|KS|TB|RBI|GOAL|SHOT|PTS|REB|AST|ANYTD)/.test(tk);
            const isTotal = !isProp && (/TOTAL/.test(series) || /total|o\/u/i.test(kind));
            const isSpread = !isProp && !isTotal && (/SPREAD/.test(series) || /spread/i.test(kind));
            if (!isProp && !isTotal && !isSpread) return false;
            const ex = ((pred && pred.metadata && pred.metadata.explain) || evt.explain || md.explain || {});
            const mk = String(ex.market || (pred && pred.market_type) || '').toLowerCase();
            const gameLike = /moneyline|game|winner/.test(mk);
            const texts = [pred && pred.predicted_team, ex.pick, evt.ai_pick, evt.predicted_team].map(x => String(x || '').trim()).filter(Boolean);
            if (isProp) {
                const propLike = /prop|player|reception|yard|touchdown|\btd\b|hit|home run|strikeout|bases|goal|shot|assist|rebound|points/.test(mk);
                return !(propLike && !gameLike);
            }
            if (isTotal) {
                if (texts.some(t => /^(over|under)\b/i.test(t))) return false;
                return true;
            }
            // spread
            if (texts.some(t => /[+-]\s?\d/.test(t))) return false;
            return gameLike || !/spread/.test(mk);
        } catch (e) { return false; }
    };

    // Prediction popup (querySportsAI): analysis block for an Active Predictions card.
    window.renderSportsAIAnalysis = function (data, evt) {
        try {
            evt = evt || {};
            const pred = data && data.prediction;
            const md0 = evt.metadata || {};
            const kind = evt.prop_type || md0.prop_type || '';
            const tkU = String(evt.event_ticker || evt.ticker || '').toUpperCase();
            const segment = evt.segment || md0.segment || (/KXNHL1P/.test(tkU) ? '1st Period' : /KXNHL2P/.test(tkU) ? '2nd Period' : /KXNHL3P/.test(tkU) ? '3rd Period' : /KXMLBF5/.test(tkU) ? 'First 5 Innings' : '');
            const conf = pred ? num(pred.confidence_pct) : null;
            if (!pred || !(conf > 0) || window.sportsGameLevelPickOnProp(evt, pred)) {
                const why = /player prop/i.test(kind) ? 'The sports AI has no prediction for this player prop.' : 'The sports AI has no prediction for this market yet.';
                return `<section class="tsd-box tsd-in-popup"><div class="tsd-h"><span>🧠 AI analysis</span></div><p class="tsd-muted">${why} Prices shown are Kalshi's.</p></section>`;
            }
            // The events feed may already carry the explanation; use it if the prediction lacks one.
            const md1 = pred.metadata || {};
            const evEx = usableExplain(evt.explain || md0.explain);
            const p2 = (!usableExplain(md1.explain) && evEx) ? Object.assign({}, pred, { metadata: Object.assign({}, md1, { explain: evEx, reasoning: md1.reasoning || evt.reasoning || md0.reasoning }) }) : pred;
            const ex = usableExplain((p2.metadata || {}).explain);
            const segOk = segment && /period|innings|half|quarter/i.test(segment) ? segment : '';
            const exact = !!(ex && explainMarket(ex) && explainMarket(ex) === cardMarket(kind, segOk));
            const pick = (exact && ex.pick) || p2.predicted_team || (p2.metadata || {}).name || '';
            const markets = Array.isArray(evt.markets) ? evt.markets : [];
            let priceC = null;
            const side = String((exact && ex.side) || '').toUpperCase();
            const binary = markets.length === 1 || /spread|total|o\/u|prop/i.test(kind);
            const pm = markets.find(m => sameTeam(pick, m.yes_sub_title));
            if (exact && binary && markets[0] && !pm) {
                // Spread / total / prop: the price of the side the explanation picked on this market.
                priceC = cents(markets[0], /^(NO|UNDER)$/.test(side) ? 'no' : 'yes');
            } else if (pm) priceC = cents(pm, /^(NO|UNDER)$/.test(side) ? 'no' : 'yes');
            else if (markets.length === 1 && /player prop/i.test(kind)) priceC = cents(markets[0], 'yes');
            const ctx = { pick, conf, priceC, marketKind: kind, segment: segOk };
            const title = !(exact && ex.line) ? pick : (String(ex.line).toLowerCase().includes(String(pick).toLowerCase()) ? ex.line : (String(pick).replace(/\s+/g, '').includes(String(ex.line).replace(/\s+/g, '')) ? pick : `${pick} · ${ex.line}`));
            return `<section class="tsd-box tsd-in-popup">
                <div class="tsd-h"><span>🧠 Why the AI picked ${esc(title)}</span></div>
                <div class="tsd-explain">${explainPick(p2, ctx)}</div>
                ${detailGrid(p2, ctx)}
            </section>`;
        } catch (e) {
            console.warn('[SportsAIAnalysis]', e);
            return '';
        }
    };

    function render(t, sInfo) {
        const card = document.getElementById('tradeDetailsModalCard');
        const hero = document.getElementById('tdm-hero-card');
        if (!card || !hero) return;

        const side = String(t.side || 'YES').toUpperCase();
        const parsed = parseReason(t.reason);
        const sport = (sInfo && sInfo.sport) || 'SPORTS';
        const what = describe(t, sInfo, parsed);
        const entryNum = num(t.entry_price);
        const entryCentsRaw = entryNum != null ? entryNum * 100 : null;
        const entry = entryCentsRaw != null ? ((Math.abs(entryCentsRaw - Math.round(entryCentsRaw)) > 0.04) ? Number(entryCentsRaw.toFixed(1)) : Math.round(entryCentsRaw)) : null;
        const qty = Number(t.count || t.size || 0) || 0;
        const isManual = t.is_manual === true || (String(t.exit_reason || '').toUpperCase() === 'MANUAL' && !t.trading_style);
        const tkUp = String(t.ticker || t.market_ticker || '').toUpperCase();
        const isMveCombo = tkUp.includes('MVE') || tkUp.includes('CROSSCATEGORY') || String(t.trading_style || '').toUpperCase() === 'SPORTS_COMBO';

        // Header: say what the contract is, in words.
        const titleEl = document.getElementById('tdm-strike-title');
        if (titleEl) titleEl.textContent = (side === 'NO' ? 'NO · ' : '') + (isMveCombo ? (t.predicted_team || what) : what);
        const tickerEl = document.getElementById('tdm-ticker');
        if (tickerEl) tickerEl.textContent = isMveCombo
            ? `🎯 MULTI-SPORT COMBO · ${t.line || 'RFQ Parlay'}`
            : `${(sInfo && sInfo.icon) || '🏟️'} ${sport} · ${(sInfo && sInfo.propType) || parsed.market || 'Moneyline'}`;

        // Hide the crypto-only sections for sports trades (thesis with the 55% fallback,
        // trading style / RL model, entry catalysts).
        ['tdm-ai-summary', 'tdm-model-pill', 'tdm-catalysts-container'].forEach(id => {
            const el = document.getElementById(id);
            const boxEl = el && el.closest('.rounded-2xl');
            if (boxEl && boxEl !== card) boxEl.classList.add('tsd-crypto-only');
        });
        card.classList.add('tsd-sport');

        let panel = document.getElementById('tdm-sports-panel');
        if (!panel) {
            panel = document.createElement('div');
            panel.id = 'tdm-sports-panel';
            hero.insertAdjacentElement('afterend', panel);
        }
        const token = (panel.dataset.req = String(Date.now() + Math.random()));

        if (isMveCombo) {
            const ls = t.mve_leg_stats || {};
            const legsTotal = ls.legs_total || 28;
            const legsWon = ls.legs_won || 0;
            const legsLost = ls.legs_lost || 0;
            const legsOpen = ls.legs_open != null ? ls.legs_open : (legsTotal - legsWon - legsLost);
            const curMark = num(t.current_bid ?? t.cur_price ?? t.exit_bid ?? t.entry_price);
            const curMarkCents = curMark != null ? ((Math.abs(curMark * 100 - Math.round(curMark * 100)) > 0.04) ? (curMark * 100).toFixed(1) : Math.round(curMark * 100)) : '--';
            const details = Array.isArray(ls.legs_details) ? ls.legs_details : [];
            const legsHtml = details.length ? details.map((lg, idx) => {
                const stBadge = lg.status === 'WON'
                    ? '<span class="tsd-st tsd-st-live" style="background:rgba(16,185,129,.18);color:#34d399;border-color:rgba(16,185,129,.4);">✓ WON</span>'
                    : lg.status === 'LOST'
                    ? '<span class="tsd-st tsd-st-fin" style="background:rgba(244,63,94,.18);color:#fb7185;border-color:rgba(244,63,94,.4);">✗ LOST</span>'
                    : `<span class="tsd-st tsd-st-up">${lg.prob != null ? Math.round(lg.prob * 100) + '¢' : 'OPEN'}</span>`;
                return `<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid rgba(255,255,255,.05);font-size:11px;">
                    <span style="color:#e2e8f0;font-weight:600;">${idx + 1}. ${esc(String(lg.side || 'YES').toUpperCase())} · ${esc(lg.title || lg.ticker)}</span>
                    ${stBadge}
                </div>`;
            }).join('') : '<div class="tsd-sub">Live leg quotes synced via Kalshi MVE engine.</div>';

            panel.innerHTML = `
                <section class="tsd-box">
                    <div class="tsd-h">
                        <span class="tsd-league-pill">🎯 Kalshi RFQ Master Combo</span>
                        <span class="tsd-st ${String(t.status || '').toUpperCase() === 'OPEN' ? 'tsd-st-live' : 'tsd-st-fin'}">${esc(String(t.status || 'OPEN').toUpperCase())}</span>
                    </div>
                    <div class="tsd-match-title">${esc(t.predicted_team || what)}</div>
                    <div class="tsd-hold">You hold <b>${qty} ${esc(side)}</b> contracts at <b>${entry != null ? entry + '¢' : '--'}</b> · Live Mark: <b>${curMarkCents}¢</b> ($${(qty * (curMark || 0)).toFixed(2)} value / $${qty.toFixed(2)} max payout)</div>
                    <div class="tsd-grid" style="margin-top:8px;">
                        ${row('Legs Won', `${legsWon} / ${legsTotal}`, legsWon > 0 ? 'tsd-pos' : '')}
                        ${row('Legs Open', `${legsOpen} / ${legsTotal}`)}
                        ${row('Legs Lost', `${legsLost} / ${legsTotal}`, legsLost > 0 ? 'tsd-neg' : '')}
                    </div>
                    <div class="tsd-tk" style="margin-top:6px;">${esc(t.ticker || '')}</div>
                </section>
                <section class="tsd-box">
                    <div class="tsd-h"><span>📋 Live Leg Tracker (${legsTotal} Legs)</span><span class="tsd-sub">${legsWon} Won · ${legsOpen} Active</span></div>
                    <div style="max-height:240px;overflow-y:auto;padding-right:4px;">${legsHtml}</div>
                </section>`;
            return;
        }

        const entryConf = parsed.conf != null ? parsed.conf : num(t.confidence);
        const valueAtEntry = (entryConf != null && entry != null) ? entryConf - entry : null;
        const initSched = getEventSchedule(null, t);
        panel.innerHTML = `
            <section class="tsd-box">
                <div class="tsd-h">
                    <span id="tsd-league-pill" class="tsd-league-pill">🏟️ Kalshi event</span>
                    <span class="tsd-st tsd-st-up" id="tsd-status">…</span>
                </div>
                <div class="tsd-match-title" id="tsd-match">${esc(what)}</div>
                <div class="tsd-schedule-bar" id="tsd-schedule-bar">
                    <span class="tsd-sched-icon">⏰</span>
                    <span class="tsd-sched-text" id="tsd-when">${esc(initSched.full || 'Loading event…')}</span>
                </div>
                <div class="tsd-prop-pill" id="tsd-prop-pill" style="display:none;"></div>
                <div class="tsd-hold">You hold <b>${qty} ${esc(side)}</b> on <b>${esc(what)}</b>${entry != null ? ` at <b>${entry}¢</b>` : ''}</div>
                <div class="tsd-prices" id="tsd-prices"></div>
                <div class="tsd-tk">${esc(eventTickerOf(t))} · ${esc(t.ticker || '')}</div>
            </section>
            <section class="tsd-box">
                <div class="tsd-h"><span>🎯 ${isManual ? 'Your pick' : 'AI pick at entry'}</span>${isManual ? '<span class="tsd-st tsd-st-up">Manual</span>' : ''}</div>
                ${isManual ? `<div class="tsd-sub">Placed manually${entryConf != null ? ' · AI was at ' + entryConf.toFixed(0) + '%' : ''}.</div>` : `
                <div class="tsd-pick">${esc(parsed.pick || (sInfo && sInfo.team) || '—')}</div>
                <div class="tsd-grid">
                    ${row('Confidence', entryConf != null ? entryConf.toFixed(1) + '%' : 'not recorded')}
                    ${row('Price paid', entry != null ? entry + '¢' : null)}
                    ${row('Value vs price', valueAtEntry != null ? (valueAtEntry >= 0 ? '+' : '') + valueAtEntry.toFixed(1) + ' pts' : null, valueAtEntry != null ? (valueAtEntry >= 0 ? 'tsd-pos' : 'tsd-neg') : '')}
                    ${row('Edge logged', parsed.edge != null ? parsed.edge.toFixed(1) + '%' : null)}
                    ${row('Market', parsed.market ? esc(parsed.market + (parsed.line && parsed.line !== parsed.market ? ' · ' + parsed.line : '')) : null)}
                </div>`}
            </section>
            <section class="tsd-box" id="tsd-now">
                <div class="tsd-h"><span>🧠 AI pick now</span><span class="tsd-sub">Loading…</span></div>
            </section>`;

        const sameReq = () => panel.dataset.req === token && !document.getElementById('tradeDetailsModal').classList.contains('hidden');

        loadEvent(t, sport).then(evt => {
            if (!sameReq()) return;
            const sched = getEventSchedule(evt, t);
            const st = statusOf(evt, t);
            const stEl = document.getElementById('tsd-status');
            if (stEl) { stEl.className = 'tsd-st ' + st.cls; stEl.textContent = st.text; }

            const md = (evt && evt.metadata) || {};
            const aiPred = (evt && evt.ai_prediction) || {};
            const aiMd = aiPred.metadata || {};

            // League / Tournament banner
            const league = aiPred.league || aiMd.league || evt?.league || (sInfo && sInfo.sport) || '';
            const leaguePill = document.getElementById('tsd-league-pill');
            if (leaguePill && league && league !== 'SPORTS') {
                leaguePill.textContent = `🏆 ${league}`;
            }

            // Full Matchup
            const matchup = (evt && (evt.matchup || md.matchup)) || (aiMd && aiMd.matchup) || '';
            const matchEl = document.getElementById('tsd-match');
            if (matchEl) {
                if (matchup) matchEl.textContent = matchup;
                else if (evt && evt.title) matchEl.textContent = evt.title;
            }

            // Schedule & Countdown
            const whenEl = document.getElementById('tsd-when');
            if (whenEl) {
                if (evt) {
                    whenEl.textContent = sched.full;
                } else {
                    whenEl.textContent = sched.full || 'Event is no longer listed on Kalshi (finished or closed).';
                }
            }

            // Prop / Market line badge
            const propType = (evt && (evt.prop_type || md.prop_type)) || (sInfo && sInfo.propType) || parsed.market || '';
            const propEl = document.getElementById('tsd-prop-pill');
            if (propEl && propType) {
                propEl.style.display = 'inline-flex';
                propEl.textContent = `🎯 ${propType}`;
            }

            const markets = (evt && Array.isArray(evt.markets)) ? evt.markets.filter(m => m && m.ticker) : [];
            const pricesEl = document.getElementById('tsd-prices');
            if (pricesEl && markets.length) {
                pricesEl.innerHTML = markets.slice(0, 4).map(m => {
                    const mine = m.ticker === t.ticker;
                    const y = cents(m, 'yes'), n = cents(m, 'no');
                    const name = String(m.yes_sub_title || m.title || m.ticker.split('-').pop());
                    const mineNow = mine ? (side === 'NO' ? n : y) : null;
                    return `<div class="tsd-px${mine ? ' tsd-px-mine' : ''}">
                        <span class="tsd-px-n">${esc(name)}${mine ? ' <i>yours</i>' : ''}</span>
                        <span class="tsd-px-p">YES ${y != null ? y + '¢' : '—'} · NO ${n != null ? n + '¢' : '—'}</span>
                        ${mine && mineNow != null && entry != null ? `<span class="tsd-px-d ${mineNow >= entry ? 'tsd-pos' : 'tsd-neg'}">${side} now ${mineNow}¢ (paid ${entry}¢)</span>` : ''}
                    </div>`;
                }).join('');
            }
            return evt;
        }).then(evt => loadPrediction(t, sport, evt && (evt.title || evt.matchup)).then(data => ({ evt, data })))
          .then(({ evt, data }) => {
            if (!sameReq()) return;
            const box = document.getElementById('tsd-now');
            if (!box) return;
            const p = data && data.prediction;
            if (!p || !(num(p.confidence_pct) > 0)) {
                box.innerHTML = `<div class="tsd-h"><span>🧠 AI pick now</span></div><div class="tsd-sub">No current AI prediction for this event${String(t.status || '').toUpperCase() === 'OPEN' ? '' : ' (game is over)'}.</div>`;
                return;
            }
            const md = p.metadata || {};
            const conf = num(p.confidence_pct);
            const pickNow = p.predicted_team || md.name || '';
            const entryPick = parsed.pick || (sInfo && sInfo.team) || '';
            const same = sameTeam(pickNow, entryPick);
            // Edge now = AI probability minus today's price of the side the AI picks.
            let priceNow = null;
            const markets = (evt && Array.isArray(evt.markets)) ? evt.markets : [];
            const pm = markets.find(m => sameTeam(pickNow, m.yes_sub_title));
            if (pm) priceNow = cents(pm, 'yes');
            const edgeNow = (conf != null && priceNow != null) ? conf - priceNow : null;
            const src = md.simulation ? `Simulation${md.simulations_count ? ' · ' + Number(md.simulations_count).toLocaleString() + ' runs' : ''}` : (md.pick_id || md.sportsbook ? 'ApexProps model' : 'Sports AI');
            const ctxNow = { pick: pickNow, conf, priceC: priceNow, marketKind: (evt && evt.prop_type) || '', segment: '' };
            box.innerHTML = `
                <div class="tsd-h"><span>🧠 AI pick now</span><span class="tsd-st ${same ? 'tsd-st-same' : 'tsd-st-flip'}">${same ? 'Same as entry' : 'Changed since entry'}</span></div>
                <div class="tsd-pick">${esc(pickNow || '—')}${md.line && md.line !== pickNow ? ` <span class="tsd-line">${esc(md.line)}</span>` : ''}</div>
                <div class="tsd-explain">${explainPick(p, ctxNow)}</div>
                ${detailGrid(p, ctxNow)}
                ${!same && entryPick ? `<div class="tsd-note">At entry the AI picked <b>${esc(entryPick)}</b>; it now favors <b>${esc(pickNow)}</b>.</div>` : ''}`;
        });
    }


    // Header: two tidy rows for every trade.
    //   row 1: sport/asset · market, LIVE/PAPER, status ........ [x]
    //   row 2: [YES] what was bought
    // Existing elements are moved (not copied), so the modal's own code keeps updating them.
    function tidyHeader() {
        const side = document.getElementById('tdm-side-badge');
        const head = side && side.closest('.sticky');
        if (!head) return;
        if (!head.dataset.tsdBuilt) {
            const ticker = document.getElementById('tdm-ticker');
            const mode = document.getElementById('tdm-mode-badge');
            const status = document.getElementById('tdm-status-badge');
            const title = document.getElementById('tdm-strike-title');
            const closeBtn = head.querySelector('button');
            if (!ticker || !mode || !status || !title || !closeBtn) return;
            const r1 = document.createElement('div'); r1.className = 'tsd-h1';
            const chips = document.createElement('div'); chips.className = 'tsd-h1-chips';
            chips.append(mode, status);
            r1.append(ticker, chips, closeBtn);
            const r2 = document.createElement('div'); r2.className = 'tsd-h2';
            r2.append(side, title);
            head.textContent = '';
            head.append(r1, r2);
            head.classList.add('tsd-head');
            head.dataset.tsdBuilt = '1';
        }
        side.textContent = String(side.textContent || '').replace(/^\s*BID\s+/i, '').trim();
        const st = document.getElementById('tdm-status-badge');
        if (st && /OPEN POSITION/i.test(st.textContent)) st.textContent = 'OPEN';
    }

    function install() {
        const orig = window.openTradeDetailsModal;
        if (typeof orig !== 'function' || orig.__tsdWrapped) return false;
        const wrapped = function (idOrObj) {
            const r = orig.apply(this, arguments);
            try { tidyHeader(); } catch (e) { console.warn('[SportsTradeDetails] header', e); }
            try {
                let t = null;
                if (idOrObj && typeof idOrObj === 'object') t = idOrObj;
                else if (window.tradesById && window.tradesById[idOrObj]) t = window.tradesById[idOrObj];
                else if (window.lastDashboardStats && window.lastDashboardStats.recent_trades) t = window.lastDashboardStats.recent_trades.find(x => String(x.id) === String(idOrObj));
                const card = document.getElementById('tradeDetailsModalCard');
                const isSport = t && window.__isSportTrade && window.__isSportTrade(t);
                if (!isSport) {
                    if (card) card.classList.remove('tsd-sport');
                    const p = document.getElementById('tdm-sports-panel');
                    if (p) p.remove();
                    return r;
                }
                render(t, window.__getSportInfo ? window.__getSportInfo(t) : null);
            } catch (e) { console.warn('[SportsTradeDetails]', e); }
            return r;
        };
        wrapped.__tsdWrapped = true;
        window.openTradeDetailsModal = wrapped;
        window.__getSportsSchedule = function(t, evt) {
            try {
                return getEventSchedule(evt || null, t || null);
            } catch(e) {
                return null;
            }
        };
        return true;
    }
    if (!install()) {
        document.addEventListener('DOMContentLoaded', install);
        window.addEventListener('load', install);
    }
})();
