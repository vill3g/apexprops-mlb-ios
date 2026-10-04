
        document.addEventListener("DOMContentLoaded", () => {
            const splash = document.getElementById("splash-screen");
            const bar = document.getElementById("splash-bar");
            // Start loading bar animation on next frame
            if (bar) requestAnimationFrame(() => { bar.style.width = "100%"; });
            if (splash) {
                setTimeout(() => {
                    splash.style.opacity = "0";
                    splash.style.transform = "scale(1.03)";
                    setTimeout(() => splash.remove(), 700);
                }, 2500);
            }
        });

        // Dynamic Island logic
        window._dynamicIslandEnabled = localStorage.getItem('di_enabled') !== 'false';
        function updateDynamicIsland(autoOn) {
            if (!window._dynamicIslandEnabled) return;
            const pill = document.getElementById('dynamic-island-pill');
            const dot = document.getElementById('di-dot');
            const label = document.getElementById('di-label');
            if (!pill) return;
            if (autoOn) {
                pill.style.opacity = '1';
                pill.style.borderColor = 'rgba(52,211,153,0.5)';
                pill.style.boxShadow = '0 0 18px 4px rgba(52,211,153,0.35)';
                dot.className = 'w-2 h-2 rounded-full bg-emerald-400 shrink-0 animate-pulse';
                dot.style.boxShadow = '0 0 8px 2px rgba(52,211,153,0.8)';
                label.textContent = 'AUTO ON';
                label.className = 'text-[10px] font-black text-emerald-300 tracking-widest uppercase';
            } else {
                pill.style.opacity = '0';
            }
        }
        window.updateDynamicIsland = updateDynamicIsland;
    