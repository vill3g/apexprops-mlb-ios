

// Custom Dropdown Logic
function closeAllDropdowns() {
    document.querySelectorAll('.dropdown-menu').forEach(m => {
        m.classList.remove('opacity-100', 'scale-100');
        m.classList.add('opacity-0', 'scale-95');
        const prevSvg = m.previousElementSibling?.querySelector('svg');
        if (prevSvg) prevSvg.classList.remove('rotate-180');
        setTimeout(() => {
            if (m.classList.contains('opacity-0')) {
                m.classList.add('hidden');
            }
        }, 150);
    });
}

function toggleDropdown(btn, e) {
    if (e && e.stopPropagation) e.stopPropagation();
    if (!btn) return;
    const menu = btn.nextElementSibling;
    if (!menu) return;
    const svg = btn.querySelector('svg');
    const isCurrentlyOpen = !menu.classList.contains('hidden');

    // Close all other dropdowns immediately
    document.querySelectorAll('.dropdown-menu').forEach(m => {
        if (m !== menu) {
            m.classList.remove('opacity-100', 'scale-100');
            m.classList.add('opacity-0', 'scale-95');
            const prevSvg = m.previousElementSibling?.querySelector('svg');
            if (prevSvg) prevSvg.classList.remove('rotate-180');
            m.classList.add('hidden');
        }
    });

    if (isCurrentlyOpen) {
        menu.classList.remove('opacity-100', 'scale-100');
        menu.classList.add('opacity-0', 'scale-95');
        if (svg) svg.classList.remove('rotate-180');
        setTimeout(() => {
            if (menu.classList.contains('opacity-0')) {
                menu.classList.add('hidden');
            }
        }, 150);
    } else {
        menu.classList.remove('hidden');
        void menu.offsetWidth; // trigger reflow for smooth transition
        menu.classList.remove('opacity-0', 'scale-95');
        menu.classList.add('opacity-100', 'scale-100');
        if (svg) svg.classList.add('rotate-180');
    }
}

function selectDropdownOption(item, val, label, e) {
    if (e && e.stopPropagation) e.stopPropagation();
    const container = item.closest('.custom-dropdown');
    if (!container) return;
    const targetId = container.getAttribute('data-target');
    const select = document.getElementById(targetId);
    
    // Update visible text
    const textEl = container.querySelector('.selected-text');
    if (textEl) textEl.innerHTML = label;
    
    // Update hidden select and trigger change event
    if (select) {
        select.value = val;
        select.dispatchEvent(new Event('change', { bubbles: true }));
    }
    
    // Explicitly close all dropdown menus immediately
    closeAllDropdowns();
    
    // Persist configuration
    saveUserConfig();
}

// Close glassy popups on outside click
document.addEventListener('click', (e) => {
    if (!e.target.closest('.flex-col.w-full.relative')) {
        document.querySelectorAll('.glassy-popup').forEach(p => {
            p.classList.remove('opacity-100');
            p.classList.add('opacity-0');
            setTimeout(() => p.classList.add('invisible'), 300);
        });
    }
});

// Close dropdowns on outside click
document.addEventListener('click', (e) => {
    if (!e.target.closest('.custom-dropdown')) {
        closeAllDropdowns();
    }
});

// Helper to sync custom UI when dashboard stats are loaded
function syncCustomDropdowns() {
    document.querySelectorAll('.custom-dropdown').forEach(container => {
        const targetId = container.getAttribute('data-target');
        const select = document.getElementById(targetId);
        if (select && select.options && select.selectedIndex >= 0) {
            const opt = select.options[select.selectedIndex];
            if (opt) {
                const textEl = container.querySelector('.selected-text');
                if (textEl) textEl.innerHTML = opt.text;
            }
        }
    });
}

