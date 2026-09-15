
import re

with open("static/index.html", "r", encoding="utf-8") as f:
    html = f.read()

old_js = r"// --- Live Signals Scroller ---[\s\S]*?// ---------------------------"

new_js = """// --- Live Signals Scroller ---
    let signalIndex = 0;
    let signalInterval = null;
    let currentSignalLines = [];
    
    function startSignalCycler() {
      if (signalInterval) clearInterval(signalInterval);
      
      const container = document.getElementById("topBarSignalsContainer");
      if (!container) return;
      
      signalInterval = setInterval(() => {
        let factors = [];
        if (window.lockedContractForecast && window.lockedContractForecast.decision_factors) {
           factors = window.lockedContractForecast.decision_factors;
        } else if (window.cachedNextContractForecast && window.cachedNextContractForecast.catalysts) {
           factors = window.cachedNextContractForecast.catalysts;
        }
        
        if (!factors || factors.length === 0) {
           factors = ["Awaiting next prediction interval...", "Monitoring real-time orderbook flow..."];
        }
        
        const nextText = factors[signalIndex % factors.length];
        signalIndex++;
        
        const line = document.createElement("div");
        line.className = "whitespace-nowrap overflow-hidden text-ellipsis";
        line.innerHTML = "<span class=\\"text-cyan-500 mr-1\\">></span>" + nextText;
        container.appendChild(line);
        currentSignalLines.push(line);
        
        if (currentSignalLines.length > 3) {
            const rowHeight = line.offsetHeight || 12;
            const scrollAmount = (currentSignalLines.length - 3) * rowHeight;
            container.style.transform = "translateY(-" + scrollAmount + "px)";
            
            setTimeout(() => {
                while(currentSignalLines.length > 3) {
                    const oldLine = currentSignalLines.shift();
                    oldLine.remove();
                }
                container.style.transition = "none";
                container.style.transform = "translateY(0)";
                void container.offsetHeight;
                container.style.transition = "transform 700ms ease-in-out";
            }, 700);
        }
      }, 2500);
    }
    
    function initAccuracyTooltip() {
      setTimeout(startSignalCycler, 2000);
// ---------------------------"""

html = re.sub(old_js, new_js, html, flags=re.MULTILINE)
# Also fix the initAccuracyTooltip that got swallowed
html = html.replace("setTimeout(startSignalCycler, 2000);\n// ---------------------------", "setTimeout(startSignalCycler, 2000);\n// ---------------------------\n    function initAccuracyTooltip() {")

# Double check if I ruined function initAccuracyTooltip() {
# Ah, I replaced it earlier, let me just replace the exact block

with open("static/index.html", "w", encoding="utf-8") as f:
    f.write(html)

