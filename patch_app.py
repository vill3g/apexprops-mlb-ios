import re

with open('static/js/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Append Profile toggle function and Matrix Telemetry logic
js_append = """
// ==========================================
// FEATURE 1: Sleek Desktop Profile Menu
// ==========================================
function toggleDesktopProfileMenu() {
    const menu = document.getElementById('desktopProfileMenu');
    if (menu) {
        if (menu.classList.contains('hidden')) {
            menu.classList.remove('hidden');
            // Animate in
            setTimeout(() => {
                menu.classList.remove('scale-95', 'opacity-0');
                menu.classList.add('scale-100', 'opacity-100');
            }, 10);
        } else {
            // Animate out
            menu.classList.remove('scale-100', 'opacity-100');
            menu.classList.add('scale-95', 'opacity-0');
            setTimeout(() => {
                menu.classList.add('hidden');
            }, 300);
        }
    }
}

// Close on outside click
document.addEventListener('click', (e) => {
    const menu = document.getElementById('desktopProfileMenu');
    const trigger = document.getElementById('btnProfileTrigger');
    if (menu && !menu.classList.contains('hidden') && !menu.contains(e.target) && (!trigger || !trigger.contains(e.target))) {
        toggleDesktopProfileMenu();
    }
});

// ==========================================
// FEATURE 2 & 3: Matrix Telemetry & CVD Gauge
// ==========================================
// We hook into the update loop or intercept the forecast update
setInterval(() => {
    const forecast = window.lockedContractForecast || window.cachedNextContractForecast;
    if (forecast) {
        // 2. Matrix Telemetry
        if (forecast.catalysts) {
            const consoleEl = document.getElementById("matrixTelemetryConsole");
            const hash = JSON.stringify(forecast.catalysts);
            if (consoleEl && window._lastMatrixCatalysts !== hash) {
                consoleEl.innerHTML = "";
                forecast.catalysts.forEach((c, idx) => {
                    const p = document.createElement("div");
                    p.className = "truncate opacity-0 transition-opacity duration-500 ease-in-out";
                    p.innerHTML = `> <span class="text-emerald-400">SYS:</span> ${c}`;
                    consoleEl.appendChild(p);
                    setTimeout(() => { p.classList.remove("opacity-0"); p.classList.add("opacity-100"); }, 100 * idx);
                });
                window._lastMatrixCatalysts = hash;
            }
        }
        
        // 3. CVD Gauge
        // Extract raw probability or derive CVD from forecast sentiment
        const cvdFill = document.getElementById("cvdGaugeFill");
        if (cvdFill) {
            let pct = 50; // Neutral 50%
            if (forecast.probability_percent) {
                // Approximate CVD bias from probability and direction
                const dir = forecast.direction || "";
                const prob = parseFloat(forecast.probability_percent);
                if (dir.includes("ABOVE") || dir.includes("YES")) {
                    pct = 50 + ((prob - 50) * 0.8); // Scale it slightly
                } else if (dir.includes("BELOW") || dir.includes("NO")) {
                    pct = 50 - ((prob - 50) * 0.8);
                }
            }
            // Clamp
            pct = Math.max(10, Math.min(90, pct));
            cvdFill.style.width = `${pct}%`;
            if (pct > 55) {
                cvdFill.className = "h-full bg-emerald-400 transition-all duration-700 shadow-sm shadow-emerald-400/50";
            } else if (pct < 45) {
                cvdFill.className = "h-full bg-red-400 transition-all duration-700 shadow-sm shadow-red-400/50";
            } else {
                cvdFill.className = "h-full bg-cyan-400 transition-all duration-700";
            }
        }
    }
}, 2000);
"""

with open('static/js/app.js', 'a', encoding='utf-8') as f:
    f.write(js_append)
print("app.js patched with JS logic for UI features.")
