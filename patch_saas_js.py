import re

with open('static/js/dashboard.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Append Matrix Telemetry & CVD Gauge logic
js_append = """

// ==========================================
// Matrix Telemetry & CVD Gauge (SaaS)
// ==========================================
setInterval(() => {
    // Attempt to grab forecast from global vars typically updated in dashboard.js
    let forecast = null;
    if (window.lastBtcData && window.lastBtcData.target_benchmark && window.lastBtcData.target_benchmark.next_contract_forecast) {
        forecast = window.lastBtcData.target_benchmark.next_contract_forecast;
    }
    
    if (forecast) {
        // Telemetry
        if (forecast.catalysts) {
            const consoleEl = document.getElementById("matrixTelemetryConsoleSaaS");
            const hash = JSON.stringify(forecast.catalysts);
            if (consoleEl && window._lastMatrixCatalystsSaaS !== hash) {
                consoleEl.innerHTML = "";
                forecast.catalysts.forEach((c, idx) => {
                    const p = document.createElement("div");
                    p.className = "truncate opacity-0 transition-opacity duration-500 ease-in-out";
                    p.innerHTML = `> <span class="text-emerald-400">SYS:</span> ${c}`;
                    consoleEl.appendChild(p);
                    setTimeout(() => { p.classList.remove("opacity-0"); p.classList.add("opacity-100"); }, 100 * idx);
                });
                window._lastMatrixCatalystsSaaS = hash;
            }
        }
        
        // CVD Gauge
        const cvdFill = document.getElementById("cvdGaugeFillSaaS");
        if (cvdFill) {
            let pct = 50; 
            if (forecast.probability_percent) {
                const dir = forecast.direction || "";
                const prob = parseFloat(forecast.probability_percent);
                if (dir.includes("ABOVE") || dir.includes("YES")) {
                    pct = 50 + ((prob - 50) * 0.8);
                } else if (dir.includes("BELOW") || dir.includes("NO")) {
                    pct = 50 - ((prob - 50) * 0.8);
                }
            }
            pct = Math.max(10, Math.min(90, pct));
            cvdFill.style.width = `${pct}%`;
            if (pct > 55) {
                cvdFill.className = "h-full bg-emerald-400 transition-all duration-700 shadow-[0_0_8px_rgba(52,211,153,0.5)]";
            } else if (pct < 45) {
                cvdFill.className = "h-full bg-red-500 transition-all duration-700 shadow-[0_0_8px_rgba(239,68,68,0.5)]";
            } else {
                cvdFill.className = "h-full bg-kalshi-blue transition-all duration-700";
            }
        }
    }
}, 2000);
"""

with open('static/js/dashboard.js', 'a', encoding='utf-8') as f:
    f.write(js_append)

print("dashboard.js patched!")
