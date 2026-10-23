/* Sports Universe settings: one collapsible panel per sport.
 *
 * The three legacy global lists (league / market / prop toggles) stay in the DOM,
 * hidden, and remain what saveUserConfig() reads. This layer only drives them:
 *   league toggle  = that sport's master switch
 *   market toggle  = enabled in at least one ON sport
 *   prop toggle    = enabled in at least one ON sport that allows PROP markets
 * The exact per-sport choices are also sent as `sports_sport_config` (JSON) and kept
 * in localStorage so they survive reloads even before the server stores them.
 * Remove this file's <script> tag and un-hide #sports-legacy-config to revert.
 */
(function () {
  'use strict';

  var LS_KEY = 'st_sports_sport_cfg_v1';

  var CAT = {
    'NFL': { icon: '🏈', name: 'NFL',
      markets: [['GAME', 'Winners', 'Moneyline'], ['SPREAD', 'Spreads', 'Point margin'], ['TOTAL', 'Totals', 'Over / Under points'], ['PROP', 'Player Props', 'Stat lines & TDs'], ['INNING', 'Halves', '1st / 2nd half']],
      props: [['ANYTIME_TD', 'Anytime TD'], ['FIRST_TD', 'First TD'], ['PASSING_YDS', 'Passing Yds'], ['RUSHING_YDS', 'Rushing Yds'], ['RECEIVING_YDS', 'Receiving Yds'], ['RECEPTIONS', 'Receptions'], ['OTHER', 'Other Props']] },
    'MLB': { icon: '⚾', name: 'MLB',
      markets: [['GAME', 'Winners', 'Moneyline'], ['SPREAD', 'Run Line', 'Spread'], ['TOTAL', 'Totals', 'Over / Under runs'], ['PROP', 'Player Props', 'Hits, HRs, Ks'], ['INNING', 'Innings', 'First 5 / innings']],
      props: [['HITS_RUNS_RBIS', 'Hits/Runs/RBIs'], ['HOME_RUNS', 'Home Runs'], ['STRIKEOUTS', 'Strikeouts'], ['TOTAL_BASES', 'Total Bases'], ['HITS', 'Hits'], ['RBIS', 'RBIs'], ['OTHER', 'Other Props']] },
    'NHL': { icon: '🏒', name: 'NHL',
      markets: [['GAME', 'Winners', 'Moneyline'], ['SPREAD', 'Puck Line', 'Spread'], ['TOTAL', 'Totals', 'Over / Under goals'], ['PROP', 'Player Props', 'Goals, points & assists'], ['INNING', 'Periods', '1st / 2nd / 3rd period']],
      props: [['GOAL', 'Anytime Goal'], ['POINTS', 'Points'], ['ASSISTS', 'Assists'], ['SAVES', 'Goalie Saves'], ['FIRST_GOAL', 'First Goalscorer'], ['OTHER', 'OT / 10-Min Goal']] },
    'SOC': { icon: '⚽', name: 'Soccer',
      markets: [['GAME', 'Winners', '3-way result'], ['SPREAD', 'Spreads', 'Goal margin'], ['TOTAL', 'Totals', 'Over / Under goals'], ['PROP', 'Specials / Props', 'BTTS, Corners, FTTS'], ['INNING', 'Halves', '1st / 2nd half']],
      props: [['BTTS', 'Both Teams To Score'], ['CORNERS', 'Corner Kicks'], ['FTTS', 'First Team To Score'], ['CORRECT_SCORE', 'Exact Score'], ['OTHER', 'Match Specials']] },
    'UFC': { icon: '🥊', name: 'UFC',
      markets: [['GAME', 'Fight Winner', 'Moneyline'], ['TOTAL', 'Rounds', 'Over / Under rounds'], ['PROP', 'Fight Props', 'Distance & method lines']],
      props: [['DISTANCE', 'Goes The Distance'], ['METHOD_OF_FINISH', 'Method of Finish (KO/Sub/Dec)'], ['ROUND_PROPS', 'Round Props / Specific Round'], ['OTHER', 'Fight Specials']] },
    'TEN': { icon: '🎾', name: 'Tennis',
      markets: [['GAME', 'Match Winner', 'Moneyline'], ['SPREAD', 'Game Handicap', 'Spread'], ['TOTAL', 'Total Games', 'Over / Under games'], ['INNING', 'Set Winner', '1st / specific set']],
      props: [] },
    'NPB/KBO': { icon: '⚾', name: 'NPB / KBO',
      markets: [['GAME', 'Winners', 'Moneyline'], ['SPREAD', 'Run Line', 'Spread'], ['TOTAL', 'Totals', 'Over / Under runs'], ['INNING', 'Innings', 'First Inning (NRFI/YRFI)']],
      props: [] },
    'NBA': { icon: '🏀', name: 'NBA',
      markets: [['GAME', 'Winners', 'Moneyline'], ['SPREAD', 'Spreads', 'Point margin'], ['TOTAL', 'Totals', 'Over / Under points'], ['PROP', 'Player Props', 'Pts, Rebs, Asts, 3s'], ['INNING', 'Halves', '1st / 2nd half']],
      props: [['POINTS', 'Points'], ['REBOUNDS', 'Rebounds'], ['ASSISTS', 'Assists'], ['THREES', '3-Pointers Made'], ['BLOCKS_STEALS', 'Blocks & Steals'], ['OTHER', 'Other Props']] },
    'NCAAF': { icon: '🎓', name: 'NCAAF',
      markets: [['GAME', 'Winners', 'Moneyline'], ['SPREAD', 'Spreads', 'Point margin'], ['TOTAL', 'Totals', 'Over / Under points'], ['INNING', 'Halves / Quarters', '1H / 2H / 4Q']],
      props: [] }
  };
  var ORDER = ['NFL', 'MLB', 'NHL', 'SOC', 'UFC', 'TEN', 'NPB/KBO', 'NBA', 'NCAAF'];

  var cfg = null;       // { SPORT: { on, markets: [], props: [] } }
  var openState = {};   // { SPORT: true } panels currently expanded

  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function codes(list) { return list.map(function (x) { return x[0]; }); }

  function fromHiddenInputs() {
    var leagues = {}, markets = {}, props = {};
    $$('input.sports-league-toggle').forEach(function (t) { if (t.checked) leagues[String(t.value).trim().toUpperCase()] = 1; });
    $$('input.sports-market-toggle').forEach(function (t) { if (t.checked) markets[String(t.value).trim().toUpperCase()] = 1; });
    $$('input.sports-prop-toggle').forEach(function (t) { if (t.checked) props[String(t.value).trim().toUpperCase()] = 1; });
    var anyM = Object.keys(markets).length, anyP = Object.keys(props).length;
    var out = {};
    ORDER.forEach(function (k) {
      out[k] = {
        on: !!leagues[k.toUpperCase()],
        markets: codes(CAT[k].markets).filter(function (c) { return !anyM || markets[c]; }),
        props: codes(CAT[k].props).filter(function (c) { return !anyP || props[c]; })
      };
    });
    return out;
  }

  function sanitize(raw) {
    var out = {};
    ORDER.forEach(function (k) {
      var r = raw && raw[k];
      if (!r) return;
      out[k] = {
        on: !!r.on,
        markets: (Array.isArray(r.markets) ? r.markets : []).filter(function (c) { return codes(CAT[k].markets).indexOf(c) >= 0; }),
        props: (Array.isArray(r.props) ? r.props : []).filter(function (c) { return codes(CAT[k].props).indexOf(c) >= 0; })
      };
    });
    return out;
  }

  function loadFrom(settings) {
    var raw = null;
    try {
      var s = settings && settings.sports_sport_config;
      if (s) raw = typeof s === 'string' ? JSON.parse(s) : s;
    } catch (e) { raw = null; }
    if (!raw) {
      try { var ls = localStorage.getItem(LS_KEY); if (ls) raw = JSON.parse(ls); } catch (e) { raw = null; }
    }
    var base = fromHiddenInputs();
    var saved = sanitize(raw);
    // The server's league list is authoritative for ON/OFF; saved config refines markets/props.
    ORDER.forEach(function (k) {
      if (saved[k]) {
        base[k].markets = saved[k].markets;
        base[k].props = saved[k].props;
        if (!settings || settings.sports_active_leagues === undefined) base[k].on = saved[k].on;
      }
    });
    cfg = base;
  }

  function persist() {
    try { localStorage.setItem(LS_KEY, JSON.stringify(cfg)); } catch (e) { /* private mode */ }
    window.__sportsSportConfig = JSON.stringify(cfg);
  }

  // Push the per-sport choices into the hidden legacy inputs that saveUserConfig() reads.
  function syncHidden() {
    var onSports = ORDER.filter(function (k) { return cfg[k].on; });
    var mk = {}, pr = {};
    onSports.forEach(function (k) {
      cfg[k].markets.forEach(function (c) { mk[c] = 1; });
      if (cfg[k].markets.indexOf('PROP') >= 0) cfg[k].props.forEach(function (c) { pr[c] = 1; });
    });
    $$('input.sports-league-toggle').forEach(function (t) {
      var k = String(t.value).trim().toUpperCase();
      var key = ORDER.filter(function (o) { return o.toUpperCase() === k; })[0];
      t.checked = !!(key && cfg[key].on);
    });
    $$('input.sports-market-toggle').forEach(function (t) { t.checked = !!mk[String(t.value).trim().toUpperCase()]; });
    $$('input.sports-prop-toggle').forEach(function (t) { t.checked = !!pr[String(t.value).trim().toUpperCase()]; });
  }

  function save() {
    persist();
    syncHidden();
    if (typeof window.updateSportsAssetSelectorVisibility === 'function') {
      window.updateSportsAssetSelectorVisibility();
    }
    if (typeof window.saveUserConfig === 'function') window.saveUserConfig();
    else if (typeof window.saveConfig === 'function') window.saveConfig();
  }

  function sw(attrs, checked) {
    return '<label class="ssp-switch" ' + attrs + '><input type="checkbox"' + (checked ? ' checked' : '') + '><span class="ssp-track"></span></label>';
  }

  function summary(k) {
    var c = cfg[k];
    if (!c.on) return 'Off';
    var n = c.markets.length;
    var p = c.markets.indexOf('PROP') >= 0 ? c.props.length : 0;
    return n + ' market' + (n === 1 ? '' : 's') + (CAT[k].props.length ? ' · ' + p + ' prop' + (p === 1 ? '' : 's') : '');
  }

  function render() {
    var host = document.getElementById('sports-sport-panels');
    if (!host || !cfg) return;
    var onCount = ORDER.filter(function (k) { return cfg[k].on; }).length;
    var html = '<div class="ssp-head"><span class="ssp-title">🏆 Sports &amp; Markets</span><span class="ssp-count">' + onCount + ' of ' + ORDER.length + ' on</span></div>' +
      '<div class="ssp-hint">Turn a sport on, then open it to pick the markets and player props the AI may trade.</div>';
    ORDER.forEach(function (k) {
      var def = CAT[k], c = cfg[k], open = !!openState[k];
      html += '<div class="ssp-panel' + (c.on ? ' is-on' : ' is-off') + (open ? ' is-open' : '') + '" data-sport="' + esc(k) + '">' +
        '<div class="ssp-row" role="button" tabindex="0" aria-expanded="' + open + '">' +
          '<span class="ssp-ico">' + def.icon + '</span>' +
          '<span class="ssp-name"><b>' + esc(def.name) + '</b><small>' + esc(summary(k)) + '</small></span>' +
          sw('data-role="master" aria-label="' + esc(def.name) + ' on or off"', c.on) +
          '<span class="ssp-chev" aria-hidden="true">▾</span>' +
        '</div>';
      if (open) {
        html += '<div class="ssp-body' + (c.on ? '' : ' is-disabled') + '">' +
          '<div class="ssp-sub">Market types</div><div class="ssp-grid">';
        def.markets.forEach(function (m) {
          var on = c.markets.indexOf(m[0]) >= 0;
          html += '<div class="ssp-item"><span class="ssp-lab"><b>' + esc(m[1]) + '</b><small>' + esc(m[2]) + '</small></span>' +
            sw('data-role="market" data-code="' + esc(m[0]) + '" aria-label="' + esc(m[1]) + '"', on) + '</div>';
        });
        html += '</div>';
        if (def.props.length) {
          var propsOn = c.markets.indexOf('PROP') >= 0;
          html += '<div class="ssp-sub">Player props' + (propsOn ? '' : ' <em>(turn on Player Props above)</em>') + '</div><div class="ssp-grid' + (propsOn ? '' : ' is-disabled') + '">';
          def.props.forEach(function (p) {
            var on = c.props.indexOf(p[0]) >= 0;
            html += '<div class="ssp-item"><span class="ssp-lab"><b>' + esc(p[1]) + '</b></span>' +
              sw('data-role="prop" data-code="' + esc(p[0]) + '" aria-label="' + esc(p[1]) + '"', on) + '</div>';
          });
          html += '</div>';
        }
        html += '</div>';
      }
      html += '</div>';
    });
    host.innerHTML = html;
  }

  function toggleIn(list, code, on) {
    var i = list.indexOf(code);
    if (on && i < 0) list.push(code);
    if (!on && i >= 0) list.splice(i, 1);
  }

  function bind() {
    var host = document.getElementById('sports-sport-panels');
    if (!host || host.__sspBound) return;
    host.__sspBound = true;

    host.addEventListener('change', function (e) {
      var input = e.target;
      var label = input.closest && input.closest('.ssp-switch');
      var panel = input.closest && input.closest('.ssp-panel');
      if (!label || !panel) return;
      var k = panel.getAttribute('data-sport');
      var role = label.getAttribute('data-role');
      var code = label.getAttribute('data-code');
      if (role === 'master') cfg[k].on = input.checked;
      else if (role === 'market') toggleIn(cfg[k].markets, code, input.checked);
      else if (role === 'prop') toggleIn(cfg[k].props, code, input.checked);
      render();
      save();
      refreshPredictions();
    });

    function toggleOpen(row) {
      var panel = row.closest('.ssp-panel');
      var k = panel.getAttribute('data-sport');
      openState[k] = !openState[k];
      render();
    }
    host.addEventListener('click', function (e) {
      if (e.target.closest && e.target.closest('.ssp-switch')) return;
      var row = e.target.closest && e.target.closest('.ssp-row');
      if (row) toggleOpen(row);
    });
    host.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      var row = e.target.classList && e.target.classList.contains('ssp-row') ? e.target : null;
      if (row) { e.preventDefault(); toggleOpen(row); }
    });
  }


  // ---- Active Predictions filter ------------------------------------------
  function sportOf(evt) {
    var s = String(evt.sport || evt.league || '').toUpperCase();
    var tk = String(evt.event_ticker || evt.ticker || '').toUpperCase();
    if (/^SOCCER|^SOC$|^EPL|^MLS|^LALIGA|^UCL|^UEL|^UECL|^EFL|^USL|^CONMEBOL|^ARG|^DIMAYOR|^BRAS|^ERED|^SAUDI|^SCOT|^LIGA/.test(s) || /^KX(EPL|MLS|LALIGA|UCL|SERIEA|BUNDES|LIGUE|UEL|UECL|WC|LIGA|EFL|USL|CONMEBOL|ARG|DIMAYOR|BRAS|ERED|SAUDI|SCOT)/.test(tk)) return 'SOC';
    if (/^TEN/.test(s) || /^KX(ATP|WTA)/.test(tk)) return 'TEN';
    if (/NPB|KBO/.test(s) || /^KX(NPB|KBO)/.test(tk)) return 'NPB/KBO';
    if (/^KXNFL/.test(tk) || s === 'NFL') return 'NFL';
    if (/^KXMLB/.test(tk) || s === 'MLB') return 'MLB';
    if (/^KXNHL/.test(tk) || s === 'NHL') return 'NHL';
    if (/^KXNBA/.test(tk) || s === 'NBA') return 'NBA';
    if (/^KXNCAAF/.test(tk) || s === 'NCAAF') return 'NCAAF';
    if (/^KXUFC/.test(tk) || s === 'UFC') return 'UFC';
    return ORDER.indexOf(s) >= 0 ? s : null;
  }
  function marketOf(evt) {
    var tk = String(evt.event_ticker || evt.ticker || '').toUpperCase();
    var series = tk.split('-')[0];
    var title = String(evt.title || '').toUpperCase();
    var sub = String(evt.sub_title || evt.yes_sub_title || '').toUpperCase();
    var comb = series + ' ' + title + ' ' + sub;

    // 1. Totals (Full Game, Half, Period, and Team Totals Over/Under)
    if (/TOTAL/.test(series) || /(ROUNDS)$/.test(series) || /OVER\/UNDER|TOTAL GAMES|TOTAL RUNS|TOTAL GOALS|TOTAL POINTS/.test(comb)) {
      return { m: 'TOTAL' };
    }

    // 2. Inning / Period / Halves / Sets / Derivatives
    if (/KX(NHL[123]P|MLBF5|ATPSETWINNER|WTASETWINNER|NPBRFI|KBORFI|NCAAF1H|NCAAF2H|NCAAF[1234]Q|NBA1H)/.test(series) ||
        /(1P|2P|3P|F5|F3|1H|2H|HALF|INNING|QTR|SETWINNER|RFI|1Q|2Q|3Q|4Q)$/.test(series) ||
        /SET 1|FIRST 5|1ST INNING|1ST HALF|2ND HALF|1ST PERIOD|2ND PERIOD|3RD PERIOD/.test(comb)) {
      return { m: 'INNING' };
    }

    // 3. Spread / Handicap / Run Line / Puck Line
    if (/SPREAD/.test(series) || /PUCK LINE|RUN LINE|HANDICAP|WINS BY OVER/.test(comb)) {
      return { m: 'SPREAD' };
    }

    // 4. Props / Specials
    // Soccer Specials
    if (/(BTTS|CORNERS|FTTS|SCORE)$/.test(series) || /KXEPL(BTTS|CORNERS|FTTS|SCORE)|KXMLS(BTTS|CORNERS|FTTS|SCORE)/.test(series)) {
      var socP = 'OTHER';
      if (/BTTS/.test(series)) socP = 'BTTS';
      else if (/CORNER/.test(series)) socP = 'CORNERS';
      else if (/FTTS/.test(series)) socP = 'FTTS';
      else if (/SCORE/.test(series)) socP = 'CORRECT_SCORE';
      return { m: 'PROP', p: socP };
    }

    // UFC Fight Props
    if (/(DISTANCE|MOF|MOV|VICROUND)$/.test(series) || /KXUFC(DISTANCE|MOF|MOV|VICROUND)/.test(series) || /GOES THE DISTANCE|METHOD OF FINISH|ROUND \d/.test(comb)) {
      var ufcP = 'OTHER';
      if (/DISTANCE/.test(series) || /GOES THE DISTANCE/.test(comb)) ufcP = 'DISTANCE';
      else if (/MOF|MOV/.test(series) || /METHOD|DECISION|SUBMISSION|KO|TKO/.test(comb)) ufcP = 'METHOD_OF_FINISH';
      else if (/VICROUND/.test(series) || /ROUND \d/.test(comb)) ufcP = 'ROUND_PROPS';
      return { m: 'PROP', p: ufcP };
    }

    // NHL Player & Game Props
    if (/KXNHL(GOAL|PTS|AST|SAVE|FIRSTGOAL|F10G|OT)/.test(series)) {
      var nhlP = 'OTHER';
      if (/GOAL$/.test(series)) nhlP = 'GOAL';
      else if (/PTS$/.test(series)) nhlP = 'POINTS';
      else if (/AST$/.test(series)) nhlP = 'ASSISTS';
      else if (/SAVE$/.test(series)) nhlP = 'SAVES';
      else if (/FIRSTGOAL$/.test(series)) nhlP = 'FIRST_GOAL';
      return { m: 'PROP', p: nhlP };
    }

    // MLB Player Props
    if (/KXMLB(HRR|HR|KS|TB|HIT|RBI)/.test(series)) {
      var mlbP = 'OTHER';
      if (/HRR$/.test(series)) mlbP = 'HITS_RUNS_RBIS';
      else if (/HR$/.test(series)) mlbP = 'HOME_RUNS';
      else if (/KS$/.test(series)) mlbP = 'STRIKEOUTS';
      else if (/TB$/.test(series)) mlbP = 'TOTAL_BASES';
      else if (/HIT$/.test(series)) mlbP = 'HITS';
      else if (/RBI$/.test(series)) mlbP = 'RBIS';
      return { m: 'PROP', p: mlbP };
    }

    // NFL Player Props
    if (/KXNFL(TD|PASSYDS|RSHYDS|RECYDS|REC|FIRSTTD)/.test(series)) {
      var nflP = 'OTHER';
      if (/FIRSTTD$/.test(series)) nflP = 'FIRST_TD';
      else if (/TD$/.test(series)) nflP = 'ANYTIME_TD';
      else if (/PASSYDS$/.test(series)) nflP = 'PASSING_YDS';
      else if (/RSHYDS$/.test(series)) nflP = 'RUSHING_YDS';
      else if (/RECYDS$/.test(series)) nflP = 'RECEIVING_YDS';
      else if (/REC$/.test(series)) nflP = 'RECEPTIONS';
      return { m: 'PROP', p: nflP };
    }

    // NBA Player Props
    if (/KXNBA(PTS|REB|AST|THREE|3PT|BLK|STL)/.test(series)) {
      var nbaP = 'OTHER';
      if (/PTS$/.test(series)) nbaP = 'POINTS';
      else if (/REB$/.test(series)) nbaP = 'REBOUNDS';
      else if (/AST$/.test(series)) nbaP = 'ASSISTS';
      else if (/THREE|3PT$/.test(series)) nbaP = 'THREES';
      else if (/BLK|STL$/.test(series)) nbaP = 'BLOCKS_STEALS';
      return { m: 'PROP', p: nbaP };
    }

    // General Prop Fallback by Series & Text
    if (/(HRR|HIT|HR|KS|RBI|TB|TD|REC|PASS|RUSH|GOAL|SHOT|PROP|PTS|REB|AST|SOG|SAVE|CORNER|BTTS)$/.test(series)) {
      return { m: 'PROP', p: 'OTHER' };
    }

    // 5. Game Winner / Match Winner / Moneyline
    if (/(GAME|MATCH|FIGHT)$/.test(series) || /WINNER|MONEYLINE/.test(comb)) return { m: 'GAME' };

    var pt = String(evt.prop_type || evt.market_type || '').toLowerCase();
    if (/prop/.test(pt)) return { m: 'PROP', p: 'OTHER' };
    if (/spread/.test(pt)) return { m: 'SPREAD' };
    if (/total|o\/u/.test(pt)) return { m: 'TOTAL' };
    if (/period|inning|half|set/.test(pt)) return { m: 'INNING' };
    if (/money|winner|game|fight/.test(pt)) return { m: 'GAME' };
    return null;
  }
  // True when the Sports & Markets settings allow this prediction card.
  window.sportsEventAllowed = function (evt) {
    try {
      if (!cfg || !evt) return true;
      var strat = window.currentSportsStrategy || 'STANDARD';
      var eStrat = evt.strategy_tag || '';
      if ((strat === 'FLOOR_TOTALS' || strat === 'POWER_COMBO' || strat === 'ULTRA_COMBO' || strat === 'MEGA_PARLAY') && eStrat === 'FLOOR_TOTALS') {
        return true;
      }
      if ((strat === 'MILESTONE_PROPS' || strat === 'POWER_COMBO' || strat === 'ULTRA_COMBO' || strat === 'MEGA_PARLAY') && eStrat === 'MILESTONE_PROPS') {
        return true;
      }
      var k = sportOf(evt);
      if (!k || !cfg[k]) return true;
      var c = cfg[k];
      if (!c.on) return false;
      if (eStrat === 'FLOOR_TOTALS') return true;
      var mk = marketOf(evt);
      if (!mk) return true;

      // Allow strategy-aligned markets if sport is active and strategy is selected
      if ((strat === 'FLOOR_TOTALS' || strat === 'POWER_COMBO' || strat === 'ULTRA_COMBO' || strat === 'MEGA_PARLAY') && mk.m === 'TOTAL') {
        return true;
      }
      if ((strat === 'MILESTONE_PROPS' || strat === 'POWER_COMBO' || strat === 'ULTRA_COMBO' || strat === 'MEGA_PARLAY') && mk.m === 'PROP') {
        return true;
      }

      if (c.markets.indexOf(mk.m) < 0) return false;
      if (mk.m === 'PROP' && CAT[k].props.length && c.props.indexOf(mk.p) < 0) return false;
      return true;
    } catch (e) { return true; }
  };
  function refreshPredictions() {
    try { if (typeof window.renderSportsEvents === 'function') window.renderSportsEvents(); } catch (e) { /* list not on screen */ }
  }

  // Called by the settings loader once the server values are in the hidden inputs.
  window.sportsPanelsFromSettings = function (settings) {
    loadFrom(settings || {});
    persist();
    bind();
    render();
    if (typeof window.updateSportsAssetSelectorVisibility === 'function') {
      window.updateSportsAssetSelectorVisibility();
    }
    refreshPredictions();
  };

  // Extra payload field for saveUserConfig().
  window.getSportsSportConfig = function () { return window.__sportsSportConfig || null; };

  function init() {
    if (!document.getElementById('sports-sport-panels')) return;
    if (!cfg) { loadFrom({}); persist(); }
    bind();
    render();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
