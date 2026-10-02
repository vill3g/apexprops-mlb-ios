// Fills the "Strategy Performance" tiles with real results from /api/auth/strategy_stats
// (closed bot trades of all users, last 30 days). Tiles: [data-strat="SNIPER"] containing
// .strat-pct, .strat-win, .strat-loss and .strat-n.
(function () {
  const MIN_TRADES = 10;   // fewer trades than this is not a meaningful win rate
  const KEY = { MOMENTUM: 'MOMENTUM_SURFER' };

  function paint(styles) {
    document.querySelectorAll('[data-strat]').forEach(function (tile) {
      const name = tile.getAttribute('data-strat');
      const s = styles[KEY[name] || name] || { wins: 0, losses: 0, trades: 0, win_rate: null };
      const pctEl = tile.querySelector('.strat-pct');
      const winEl = tile.querySelector('.strat-win');
      const lossEl = tile.querySelector('.strat-loss');
      const nEl = tile.querySelector('.strat-n');
      const enough = s.trades >= MIN_TRADES && s.win_rate != null;
      const wr = enough ? s.win_rate : 0;
      if (pctEl) {
        pctEl.textContent = enough ? Math.round(wr) + '%' : '--';
        pctEl.classList.remove('text-emerald-400', 'text-amber-400', 'text-red-400', 'text-gray-500');
        pctEl.classList.add(!enough ? 'text-gray-500' : wr >= 55 ? 'text-emerald-400' : wr >= 45 ? 'text-amber-400' : 'text-red-400');
      }
      if (winEl) winEl.style.width = (enough ? wr : 0) + '%';
      if (lossEl) lossEl.style.width = (enough ? 100 - wr : 0) + '%';
      if (nEl) nEl.textContent = s.trades ? (s.trades + ' trades' + (enough ? '' : ' (too few)')) : 'no trades';
      tile.title = s.trades
        ? s.wins + ' wins / ' + s.losses + ' losses, P&L $' + Number(s.pnl || 0).toFixed(2) + ' (last 30 days, all users)'
        : 'No closed trades in the last 30 days';
    });
  }

  async function load() {
    if (!document.querySelector('[data-strat]')) return;
    try {
      const res = await fetch('/api/auth/strategy_stats');
      if (!res.ok) return;
      const data = await res.json();
      if (data && data.styles) paint(data.styles);
    } catch (e) { /* keep "--" */ }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load);
  else load();
  if(window._strategyStatsInterval) clearInterval(window._strategyStatsInterval); window._strategyStatsInterval = setInterval(load, 5 * 60 * 1000);
})();
