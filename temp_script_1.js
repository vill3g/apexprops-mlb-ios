

function toggleProfileDropdown() {
    const dd = document.getElementById('profileDropdown');
    if (!dd) return;
    const willOpen = dd.classList.contains('hidden');
    dd.classList.toggle('hidden');
    if (willOpen && typeof fetchDailyQuests === 'function') {
        fetchDailyQuests();
    }
}

function openSettings() {
    setTimeout(() => {
        const notifyToggle = document.getElementById("ios-notify-toggle");
        if (notifyToggle) notifyToggle.checked = window.enableIosNotifications;
    }, 50);
    window.isSettingsOpen = true;
    if (typeof syncSoundSettingsUI === 'function') {
        syncSoundSettingsUI();
    }
    if (typeof refreshWalletBalances === 'function') {
        refreshWalletBalances();
    }
    if (typeof populateUserSettings === 'function' && window.lastDashboardStats) {
        populateUserSettings(window.lastDashboardStats, true);
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
                        populateUserSettings(freshStats, true);
                    }
                }
            }
        }).catch(err => console.warn('Could not refresh settings on open:', err));
    }
    if (typeof syncChartSettingsUI === 'function') {
        syncChartSettingsUI();
    }
    if (typeof fetchTpSlRecommendations === 'function') {
        fetchTpSlRecommendations();
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
    const drawer = document.getElementById('settingsDrawer');
    const panel = document.getElementById('settingsPanel');
    const backdrop = document.getElementById('settingsBackdrop');
    
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
    const drawer = document.getElementById('settingsDrawer');
    const panel = document.getElementById('settingsPanel');
    const backdrop = document.getElementById('settingsBackdrop');
    
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
    
    document.body.style.overflow = '';
    
    setTimeout(() => {
        if (drawer) drawer.classList.add('hidden');
    }, 300);
}

// Swipe Right to Close Settings Menu
function initSettingsSwipeToClose() {
    const drawer = document.getElementById('settingsDrawer');
    const panel = document.getElementById('settingsPanel');
    const backdrop = document.getElementById('settingsBackdrop');
    if (!drawer || !panel) return;

    let touchStartX = 0;
    let touchStartY = 0;
    let touchCurrentX = 0;
    let isSwiping = false;
    let gestureDecided = false;
    let touchStartTime = 0;

    drawer.addEventListener('touchstart', (e) => {
        if (!window.isSettingsOpen && drawer.classList.contains('hidden')) return;
        if (e.touches.length !== 1) return;
        if (e.target.closest('input[type="range"]')) return;

        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
        touchCurrentX = touchStartX;
        isSwiping = false;
        gestureDecided = false;
        touchStartTime = Date.now();
    }, { passive: true });

    drawer.addEventListener('touchmove', (e) => {
        if (!window.isSettingsOpen && drawer.classList.contains('hidden')) return;
        if (e.touches.length !== 1) return;
        if (e.target.closest('input[type="range"]')) return;

        touchCurrentX = e.touches[0].clientX;
        const currentY = e.touches[0].clientY;
        const deltaX = touchCurrentX - touchStartX;
        const deltaY = currentY - touchStartY;

        if (!gestureDecided) {
            if (Math.hypot(deltaX, deltaY) > 8) {
                gestureDecided = true;
                if (deltaX > 0 && deltaX > Math.abs(deltaY) * 0.8) {
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

    // Desktop / Mouse drag support on the navigation bar
    let isMouseDown = false;
    let mouseStartX = 0;
    let mouseStartY = 0;
    let mouseCurrentX = 0;
    let isMouseSwiping = false;
    let mouseStartTime = 0;

    const navBar = panel.querySelector('.border-b');
    if (navBar) {
        navBar.style.cursor = 'grab';
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

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSettingsSwipeToClose);
} else {
    initSettingsSwipeToClose();
}

