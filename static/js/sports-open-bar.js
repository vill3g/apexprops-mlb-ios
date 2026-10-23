/* Sports "open positions" bar for phones/tablets.
 *
 * The Position Scanner panel (#activePositionHud) is rendered by
 * updateActivePositionHud() in saas_dashboard.html and sits after the long
 * picks list. On narrow screens this adds a slim bar pinned under the sport
 * filter row ("3 open  +$1.40  v"). Tapping it drops the existing panel down
 * over the picks, with its TP / Close buttons, so open trades are one tap away
 * wherever you are in the list.
 *
 * It only reads what the panel already shows (count and total P&L) and toggles
 * a body class; it never renders trades itself. CSS (mobile-polish.css) hides the bar and
 * leaves the panel alone on desktop and outside the Sports universe.
 */
(function () {
  'use strict';

  var bar = null;
  var scrim = null;

  // Read the open-trade count and total P&L straight from the rendered panel, so
  // the bar can never disagree with it (the panel already applies the sports filter).
  function readPanel() {
    var hud = document.getElementById('activePositionHud');
    var out = { count: 0, total: 0 };
    if (!hud) return out;
    out.count = hud.querySelectorAll('button[onclick*="closeTrade("]').length;
    var spans = hud.querySelectorAll('span');
    for (var i = 0; i < spans.length; i++) {
      if (/total\s*pnl/i.test(spans[i].textContent) && spans[i].nextElementSibling) {
        var txt = spans[i].nextElementSibling.textContent.trim();
        var v = parseFloat(txt.replace(/[^0-9.]/g, ''));
        if (!isNaN(v)) out.total = (txt.charAt(0) === '-' ? -1 : 1) * v;
        break;
      }
    }
    return out;
  }

  function money(n) {
    return (n >= 0 ? '+$' : '-$') + Math.abs(n).toFixed(2);
  }

  function isOpen() {
    return document.body.classList.contains('sp-hud-open');
  }

  function close() {
    // Only touch the DOM when something changes: rewriting body.class (even to the
    // same value) fires the MutationObserver below, which calls render(), which
    // calls close() again, and the page locks up in an endless loop.
    if (!isOpen()) return;
    document.body.classList.remove('sp-hud-open');
    if (bar) bar.setAttribute('aria-expanded', 'false');
    if (scrim) scrim.hidden = true;
  }

  function open() {
    if (!bar || bar.dataset.count === '0') return;
    // The dropdown is position:fixed, so anchor it to the bar's current bottom edge.
    document.body.style.setProperty('--sp-ob-bottom', Math.round(bar.getBoundingClientRect().bottom) + 'px');
    document.body.classList.add('sp-hud-open');
    bar.setAttribute('aria-expanded', 'true');
    if (scrim) scrim.hidden = false;
  }

  // Keep the bar pinned directly under the (sticky) sport filter row.
  function place() {
    var sel = document.getElementById('assetSelectorBar');
    if (!sel || !bar) return;
    var top = parseFloat(getComputedStyle(sel).top) || 0;
    bar.style.top = Math.round(top + sel.offsetHeight) + 'px';
  }

  function render() {
    if (!bar) return;
    if (!document.body.classList.contains('universe-sports')) { close(); return; }
    var p = readPanel();

    bar.dataset.count = String(p.count);
    var label = bar.querySelector('.sp-ob-label');
    var pnl = bar.querySelector('.sp-ob-pnl');
    if (p.count === 0) {
      label.textContent = 'No open positions';
      pnl.textContent = '';
      pnl.className = 'sp-ob-pnl';
      close();
    } else {
      label.textContent = p.count + ' open position' + (p.count === 1 ? '' : 's');
      pnl.textContent = money(p.total);
      pnl.className = 'sp-ob-pnl ' + (p.total >= 0 ? 'sp-ob-up' : 'sp-ob-down');
    }
    place();
  }

  function build() {
    var sel = document.getElementById('assetSelectorBar');
    if (!sel || document.getElementById('spOpenBar')) return;

    bar = document.createElement('button');
    bar.type = 'button';
    bar.id = 'spOpenBar';
    bar.dataset.count = '0';
    bar.setAttribute('aria-expanded', 'false');
    bar.setAttribute('aria-controls', 'activePositionHud');
    bar.innerHTML =
      '<span class="sp-ob-dot"></span>' +
      '<span class="sp-ob-label">No open positions</span>' +
      '<span class="sp-ob-pnl"></span>' +
      '<span class="sp-ob-chev" aria-hidden="true">&#9662;</span>';
    bar.addEventListener('click', function () { isOpen() ? close() : open(); });
    sel.insertAdjacentElement('afterend', bar);

    scrim = document.createElement('div');
    scrim.id = 'spOpenScrim';
    scrim.hidden = true;
    scrim.addEventListener('click', close);
    document.body.appendChild(scrim);

    // Leaving Sports (or rotating to a wide layout) must not leave the dropdown stuck open.
    new MutationObserver(function () { render(); }).observe(document.body, { attributes: true, attributeFilter: ['class'] });
    window.addEventListener('resize', function () { place(); if (isOpen()) close(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
    render();
  }

  // Refresh whenever the page refreshes the panel.
  function hook() {
    var orig = window.updateActivePositionHud;
    if (typeof orig !== 'function' || orig.__spWrapped) return typeof orig === 'function';
    var wrapped = function (s) {
      var r = orig.apply(this, arguments);
      try { render(); } catch (e) { /* never break the dashboard poll */ }
      return r;
    };
    wrapped.__spWrapped = true;
    window.updateActivePositionHud = wrapped;
    return true;
  }

  function init() {
    build();
    if (!hook()) {
      var tries = 0;
      var t = setInterval(function () { if (hook() || ++tries > 20) clearInterval(t); }, 250);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
