/* ShadowTrader AI: small-screen helpers for the sport filter row.
 *
 * - Marks the row that holds the sport chips (.ssp-chip-row) and adds an edge fade on the
 *   side(s) where more chips are scrolled out of view (styles in css/mobile-polish.css).
 * - After a sport is picked, scrolls that chip fully into view.
 *
 * Purely visual. To revert: remove the <script src="./js/small-screen-polish.js"> tag.
 */
(function () {
    'use strict';

    function row() {
        const chip = document.querySelector('#assetSelectorBar .asset-btn-sports');
        return chip ? chip.parentElement : null;
    }

    function updateFade(el) {
        if (!el) return;
        const max = el.scrollWidth - el.clientWidth;
        el.classList.toggle('ssp-fade-left', max > 2 && el.scrollLeft > 2);
        el.classList.toggle('ssp-fade-right', max > 2 && el.scrollLeft < max - 2);
    }

    function revealChip(btn) {
        const el = row();
        if (!el || !btn || btn.parentElement !== el) return;
        const r = btn.getBoundingClientRect();
        const p = el.getBoundingClientRect();
        if (r.left < p.left + 8 || r.right > p.right - 8) {
            const target = el.scrollLeft + (r.left - p.left) - (p.width - r.width) / 2;
            try { el.scrollTo({ left: Math.max(0, target), behavior: 'smooth' }); }
            catch (e) { el.scrollLeft = Math.max(0, target); }
        }
    }

    function init() {
        const el = row();
        if (!el) return;
        el.classList.add('ssp-chip-row');
        let raf = 0;
        const schedule = function () {
            if (raf) return;
            raf = requestAnimationFrame(function () { raf = 0; updateFade(el); });
        };
        el.addEventListener('scroll', schedule, { passive: true });
        window.addEventListener('resize', schedule);
        if ('ResizeObserver' in window) new ResizeObserver(schedule).observe(el);
        // Chips are shown/hidden when the universe changes; re-check then.
        if ('MutationObserver' in window) {
            new MutationObserver(schedule).observe(el, { attributes: true, subtree: true, attributeFilter: ['class', 'style'] });
        }
        el.addEventListener('click', function (e) {
            const btn = e.target.closest('.asset-btn-sports');
            if (btn) setTimeout(function () { revealChip(btn); }, 0);
        });
        schedule();
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
