/* ShadowTrader AI: confirm before switching from PAPER to LIVE trading.
 *
 * The header badges and the Settings buttons all call setTradingMode(mode). This file wraps
 * that function so a switch INTO live mode first shows a confirmation sheet. Switching back to
 * PAPER is never blocked. Styles live in css/mobile-polish.css (.lmc-*).
 *
 * To revert: remove the <script src="./js/live-mode-confirm.js"> tag.
 */
(function () {
    'use strict';

    function getMode() {
        try { return typeof currentMode !== 'undefined' ? String(currentMode).toUpperCase() : ''; }
        catch (e) { return ''; }
    }

    let sheet = null;
    let pending = null;
    let lastFocus = null;

    function build() {
        if (sheet) return sheet;
        sheet = document.createElement('div');
        sheet.id = 'liveModeConfirm';
        sheet.className = 'lmc-backdrop';
        sheet.hidden = true;
        sheet.innerHTML =
            '<div class="lmc-sheet" role="alertdialog" aria-modal="true" aria-labelledby="lmcTitle" aria-describedby="lmcBody">' +
            '  <div class="lmc-icon" aria-hidden="true">!</div>' +
            '  <h2 id="lmcTitle" class="lmc-title">Switch to LIVE trading?</h2>' +
            '  <p id="lmcBody" class="lmc-body">Trades will use real money from your Kalshi account, ' +
            'including trades the AI places automatically. You can switch back to Paper at any time.</p>' +
            '  <div class="lmc-actions">' +
            '    <button type="button" class="lmc-btn lmc-cancel" data-lmc="cancel">Stay in Paper</button>' +
            '    <button type="button" class="lmc-btn lmc-go" data-lmc="confirm">Switch to LIVE</button>' +
            '  </div>' +
            '</div>';
        sheet.addEventListener('click', function (e) {
            const action = e.target.closest('[data-lmc]');
            if (action) { close(action.getAttribute('data-lmc') === 'confirm'); return; }
            if (e.target === sheet) close(false);
        });
        document.addEventListener('keydown', function (e) {
            if (sheet.hidden) return;
            if (e.key === 'Escape') { e.preventDefault(); close(false); }
            if (e.key === 'Tab') { // keep focus inside the dialog
                const btns = sheet.querySelectorAll('button');
                const first = btns[0], last = btns[btns.length - 1];
                if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
                else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
            }
        });
        document.body.appendChild(sheet);
        return sheet;
    }

    function open() {
        return new Promise(function (resolve) {
            build();
            if (pending) pending(false);
            pending = resolve;
            lastFocus = document.activeElement;
            sheet.hidden = false;
            document.body.classList.add('lmc-open');
            const cancel = sheet.querySelector('.lmc-cancel');
            if (cancel) cancel.focus();
        });
    }

    function close(ok) {
        if (!sheet) return;
        sheet.hidden = true;
        document.body.classList.remove('lmc-open');
        const done = pending;
        pending = null;
        if (lastFocus && typeof lastFocus.focus === 'function') {
            try { lastFocus.focus(); } catch (e) { /* ignore */ }
        }
        if (done) done(ok);
    }

    function install() {
        const original = window.setTradingMode;
        if (typeof original !== 'function' || original.__lmcWrapped) return false;
        const wrapped = async function (mode) {
            const target = String(mode || '').toUpperCase();
            if (target === 'LIVE' && getMode() !== 'LIVE') {
                const ok = await open();
                if (!ok) {
                    if (typeof updateModeUI === 'function') { try { updateModeUI(); } catch (e) { /* ignore */ } }
                    return;
                }
            }
            return original.apply(this, arguments);
        };
        wrapped.__lmcWrapped = true;
        window.setTradingMode = wrapped;
        return true;
    }

    window.confirmLiveMode = open;
    if (!install()) {
        document.addEventListener('DOMContentLoaded', install);
        window.addEventListener('load', install);
    }
})();
