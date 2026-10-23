

// Global Logout function accessible immediately from anywhere in document
window.logout = async function() {
    try {
        localStorage.removeItem('saas_token');
        localStorage.removeItem('saas_username');
        localStorage.removeItem('app_api_token');
        localStorage.removeItem('admin_api_token');
        localStorage.removeItem('api_token');
        localStorage.removeItem('is_admin_session');
        sessionStorage.clear();

        const expiredCookieStr = '=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; max-age=0; SameSite=Lax';
        document.cookie = 'saas_token' + expiredCookieStr;
        document.cookie = 'app_api_token' + expiredCookieStr;
        document.cookie = 'admin_api_token' + expiredCookieStr;
        await fetch((window.API_BASE_URL || '') + '/api/auth/logout', { method: 'POST', credentials: 'include' }).catch(() => {});
    } catch (err) {
        console.warn('[Auth] Error during logout cleanup:', err);
    }
    window.location.replace('./login.html?logged_out=1');
};
const logout = window.logout;

function toggleProfileDropdown() {
    const dd = document.getElementById('profileDropdown');
    if (!dd) return;
    const willOpen = dd.classList.contains('hidden');
    dd.classList.toggle('hidden');
    if (willOpen && typeof fetchDailyQuests === 'function') {
        fetchDailyQuests();
    }
}

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
    if (typeof fetchQuantLabData === 'function') {
        fetchQuantLabData();
    }
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

function openSettings(universe) {
    const targetUniv = (universe || window.currentUniverse || (window.lastDashboardStats && window.lastDashboardStats.trading_universe) || 'FINANCIAL').toUpperCase();
    const isInvestments = (targetUniv === 'INVESTMENTS');
    const isSports = (targetUniv === 'SPORTS');
    window.isSettingsOpen = true;
    window.activeSettingsDrawer = isInvestments ? 'INVESTMENTS' : (isSports ? 'SPORTS' : 'FINANCIAL');

    setTimeout(() => {
        const notifyToggle = document.getElementById(isInvestments ? "inv-ios-notify-toggle" : (isSports ? "sports-ios-notify-toggle" : "ios-notify-toggle"));
        if (notifyToggle) notifyToggle.checked = window.enableIosNotifications;
    }, 50);

    if (typeof syncSoundSettingsUI === 'function') {
        syncSoundSettingsUI();
    }
    if (typeof refreshWalletBalances === 'function') {
        refreshWalletBalances();
    }
    if (typeof updateModeUI === 'function') {
        updateModeUI();
    }
    if (typeof populateUserSettings === 'function' && window.lastDashboardStats) {
        populateUserSettings(window.lastDashboardStats, false);
    }
    const token = localStorage.getItem('saas_token');
    if (token) {
        fetch((window.API_BASE_URL||'')+'/api/auth/dashboard_stats', {
            headers: { 'Authorization': `Bearer ${token}` }
        }).then(r => r.ok ? r.json() : null).then(freshStats => {
            if (freshStats) {
                window.lastDashboardStats = freshStats;
                if (typeof populateUserSettings === 'function') {
                    const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
                    if (activeTag !== 'input' && activeTag !== 'select') {
                        populateUserSettings(freshStats, false);
                    }
                }
            }
        }).catch(err => console.warn('Could not refresh settings on open:', err));
    }
    if (typeof syncChartSettingsUI === 'function' && !isSports && !isInvestments) {
        syncChartSettingsUI();
    }
    if (typeof fetchTpSlRecommendations === 'function' && !isSports && !isInvestments) {
        fetchTpSlRecommendations();
    }
    if (isInvestments && typeof fetchInvestmentsConfig === 'function') {
        fetchInvestmentsConfig();
    }
    // Sync Dynamic Island toggle
    const diToggle = document.getElementById('di-toggle');
    const diBadge = document.getElementById('di-status-badge');
    const diOn = localStorage.getItem('di_enabled') !== 'false';
    if (diToggle) diToggle.checked = diOn;
    if (diBadge) {
        diBadge.textContent = diOn ? 'ON' : 'OFF';
        diBadge.className = diOn ? 'text-[9px] font-bold text-emerald-400 uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';
    }

    const drawerId = isInvestments ? 'investmentsSettingsDrawer' : (isSports ? 'sportsSettingsDrawer' : 'financialSettingsDrawer');
    const panelId = isInvestments ? 'investmentsSettingsPanel' : (isSports ? 'sportsSettingsPanel' : 'financialSettingsPanel');
    const backdropId = isInvestments ? 'investmentsSettingsBackdrop' : (isSports ? 'sportsSettingsBackdrop' : 'financialSettingsBackdrop');

    const drawer = document.getElementById(drawerId);
    const panel = document.getElementById(panelId);
    const backdrop = document.getElementById(backdropId);
    
    // Close other drawers if open
    ['financial', 'sports', 'investments'].forEach(prefix => {
        const otherDId = `${prefix}SettingsDrawer`;
        if (otherDId !== drawerId) {
            const od = document.getElementById(otherDId);
            const op = document.getElementById(`${prefix}SettingsPanel`);
            const ob = document.getElementById(`${prefix}SettingsBackdrop`);
            if (od && !od.classList.contains('hidden')) {
                if (op) { op.classList.remove('translate-x-0'); op.classList.add('translate-x-full'); }
                if (ob) { ob.classList.remove('opacity-100'); ob.classList.add('opacity-0'); }
                setTimeout(() => { if (od) od.classList.add('hidden'); }, 300);
            }
        }
    });

    if (panel) {
        panel.style.transform = '';
        panel.style.transition = '';
    }
    if (backdrop) {
        backdrop.style.opacity = '';
        backdrop.style.transition = '';
    }

    if (drawer) drawer.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            if (panel) {
                panel.classList.remove('translate-x-full');
                panel.classList.add('translate-x-0');
            }
            if (backdrop) {
                backdrop.classList.remove('opacity-0');
                backdrop.classList.add('opacity-100');
            }
        });
    });
}

async function fetchTpSlRecommendations() {
    const token = localStorage.getItem('saas_token');
    if (!token) return;
    try {
        const res = await fetch((window.API_BASE_URL || '') + '/api/engine/btc/tpsl/recommendations', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) return;
        const data = await res.json();
        const slEl = document.getElementById('sl-recommendation');
        const slVal = document.getElementById('sl-rec-value');
        const tpEl = document.getElementById('tp-recommendation');
        const tpVal = document.getElementById('tp-rec-value');
        if (slEl && slVal && data.recommended_sl != null) {
            slVal.textContent = data.recommended_sl;
            slEl.classList.remove('hidden');
        }
        if (tpEl && tpVal && data.recommended_tp != null) {
            tpVal.textContent = data.recommended_tp;
            tpEl.classList.remove('hidden');
        }
    } catch (e) {
        // Silently fail — recommendations are non-critical
    }
}

function closeSettings() {
    window.isSettingsOpen = false;
    ['financial', 'sports', 'investments'].forEach(prefix => {
        const drawer = document.getElementById(`${prefix}SettingsDrawer`);
        const panel = document.getElementById(`${prefix}SettingsPanel`);
        const backdrop = document.getElementById(`${prefix}SettingsBackdrop`);
        if (panel) {
            panel.style.transform = '';
            panel.style.transition = '';
            panel.classList.remove('translate-x-0');
            panel.classList.add('translate-x-full');
        }
        if (backdrop) {
            backdrop.style.opacity = '';
            backdrop.style.transition = '';
            backdrop.classList.remove('opacity-100');
            backdrop.classList.add('opacity-0');
        }
        if (drawer && !drawer.classList.contains('hidden')) {
            setTimeout(() => {
                if (drawer) drawer.classList.add('hidden');
            }, 300);
        }
    });

    const legacyDrawer = document.getElementById('settingsDrawer');
    if (legacyDrawer && !legacyDrawer.classList.contains('hidden')) {
        legacyDrawer.classList.add('hidden');
    }
    
    document.body.style.overflow = '';
}

// Swipe Right to Close Settings Menu for both drawers
function initSettingsSwipeToClose() {
    function bindSwipe(drawerId, panelId, backdropId) {
        const drawer = document.getElementById(drawerId);
        const panel = document.getElementById(panelId);
        const backdrop = document.getElementById(backdropId);
        if (!drawer || !panel) return;

        let touchStartX = 0;
        let touchStartY = 0;
        let touchCurrentX = 0;
        let isSwiping = false;
        let gestureDecided = false;
        let touchStartTime = 0;

        let isEligibleSwipeStart = false;

        drawer.addEventListener('touchstart', (e) => {
            if (drawer.classList.contains('hidden')) return;
            if (e.touches.length !== 1) return;
            if (e.target.closest('input, select, textarea, button, [role="button"]')) {
                isEligibleSwipeStart = false;
                return;
            }

            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
            touchCurrentX = touchStartX;
            isSwiping = false;
            gestureDecided = false;
            touchStartTime = Date.now();

            const panelRect = panel.getBoundingClientRect();
            const isNearLeftEdge = (touchStartX >= panelRect.left - 10 && touchStartX <= panelRect.left + 44);
            const isTopBar = Boolean(e.target.closest('.cursor-grab, [style*="safe-area-inset-top"]'));
            isEligibleSwipeStart = isNearLeftEdge || isTopBar;
        }, { passive: true });

        drawer.addEventListener('touchmove', (e) => {
            if (drawer.classList.contains('hidden')) return;
            if (e.touches.length !== 1) return;
            if (!isEligibleSwipeStart) return;

            touchCurrentX = e.touches[0].clientX;
            const currentY = e.touches[0].clientY;
            const deltaX = touchCurrentX - touchStartX;
            const deltaY = currentY - touchStartY;

            if (!gestureDecided) {
                if (Math.hypot(deltaX, deltaY) > 10) {
                    gestureDecided = true;
                    if (deltaX > 15 && deltaX > Math.abs(deltaY) * 1.5) {
                        isSwiping = true;
                        panel.style.transition = 'none';
                        if (backdrop) backdrop.style.transition = 'none';
                    } else {
                        isSwiping = false;
                    }
                }
            }

            if (isSwiping) {
                const clampedDeltaX = Math.max(0, deltaX);
                panel.style.transform = `translateX(${clampedDeltaX}px)`;

                if (backdrop) {
                    const panelWidth = panel.offsetWidth || 360;
                    const progress = Math.min(1, clampedDeltaX / panelWidth);
                    backdrop.style.opacity = Math.max(0, 1 - progress * 0.9);
                }

                if (e.cancelable) {
                    e.preventDefault();
                }
            }
        }, { passive: false });

        const handleTouchEnd = () => {
            if (!isSwiping) return;
            isSwiping = false;
            gestureDecided = false;

            const deltaX = touchCurrentX - touchStartX;
            const elapsed = Math.max(1, Date.now() - touchStartTime);
            const velocityX = deltaX / elapsed;
            const panelWidth = panel.offsetWidth || 360;

            panel.style.transition = '';
            if (backdrop) backdrop.style.transition = '';

            if (deltaX > 75 || deltaX > panelWidth * 0.20 || (deltaX > 35 && velocityX > 0.35)) {
                closeSettings();
            } else {
                panel.classList.remove('translate-x-full');
                panel.classList.add('translate-x-0');
                panel.style.transform = '';
                if (backdrop) {
                    backdrop.style.opacity = '';
                    backdrop.classList.add('opacity-100');
                    backdrop.classList.remove('opacity-0');
                }
            }
        };

        drawer.addEventListener('touchend', handleTouchEnd, { passive: true });
        drawer.addEventListener('touchcancel', handleTouchEnd, { passive: true });

        // Desktop / Mouse drag support on navigation bar
        const navBar = panel.querySelector('.border-b');
        if (navBar) {
            navBar.style.cursor = 'grab';
            let isMouseDown = false;
            let mouseStartX = 0;
            let mouseStartY = 0;
            let mouseCurrentX = 0;
            let isMouseSwiping = false;
            let mouseStartTime = 0;

            navBar.addEventListener('mousedown', (e) => {
                if (e.button !== 0) return;
                if (e.target.closest('button, input, select')) return;
                isMouseDown = true;
                isMouseSwiping = false;
                mouseStartX = e.clientX;
                mouseStartY = e.clientY;
                mouseCurrentX = mouseStartX;
                mouseStartTime = Date.now();
                navBar.style.cursor = 'grabbing';
            });

            window.addEventListener('mousemove', (e) => {
                if (!isMouseDown) return;
                mouseCurrentX = e.clientX;
                const deltaX = mouseCurrentX - mouseStartX;
                const deltaY = e.clientY - mouseStartY;

                if (!isMouseSwiping && deltaX > 8 && deltaX > Math.abs(deltaY)) {
                    isMouseSwiping = true;
                    panel.style.transition = 'none';
                    if (backdrop) backdrop.style.transition = 'none';
                }

                if (isMouseSwiping) {
                    const clamped = Math.max(0, deltaX);
                    panel.style.transform = `translateX(${clamped}px)`;
                    if (backdrop) {
                        const panelWidth = panel.offsetWidth || 360;
                        backdrop.style.opacity = Math.max(0, 1 - (clamped / panelWidth) * 0.9);
                    }
                }
            });

            window.addEventListener('mouseup', () => {
                if (!isMouseDown) return;
                isMouseDown = false;
                navBar.style.cursor = 'grab';
                if (!isMouseSwiping) return;
                isMouseSwiping = false;

                const deltaX = mouseCurrentX - mouseStartX;
                const elapsed = Math.max(1, Date.now() - mouseStartTime);
                const velocityX = deltaX / elapsed;
                const panelWidth = panel.offsetWidth || 360;

                panel.style.transition = '';
                if (backdrop) backdrop.style.transition = '';

                if (deltaX > 75 || deltaX > panelWidth * 0.20 || (deltaX > 35 && velocityX > 0.35)) {
                    closeSettings();
                } else {
                    panel.classList.remove('translate-x-full');
                    panel.classList.add('translate-x-0');
                    panel.style.transform = '';
                    if (backdrop) {
                        backdrop.style.opacity = '';
                        backdrop.classList.add('opacity-100');
                        backdrop.classList.remove('opacity-0');
                    }
                }
            });
        }
    }

    bindSwipe('financialSettingsDrawer', 'financialSettingsPanel', 'financialSettingsBackdrop');
    bindSwipe('sportsSettingsDrawer', 'sportsSettingsPanel', 'sportsSettingsBackdrop');
    bindSwipe('investmentsSettingsDrawer', 'investmentsSettingsPanel', 'investmentsSettingsBackdrop');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSettingsSwipeToClose);
} else {
    initSettingsSwipeToClose();
}

