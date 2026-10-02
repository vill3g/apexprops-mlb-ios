import re

with open('static/js/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

patch = """
        cdPill.style.color = `rgb(${r}, ${g}, ${b})`;
        cdPill.style.borderColor = `rgba(${r}, ${g}, ${b}, 0.75)`;
        cdPill.style.backgroundColor = `rgba(${r}, ${g}, ${b}, 0.14)`;
        cdPill.style.boxShadow = `0 0 10px rgba(${r}, ${g}, ${b}, 0.3)`;
        
        // Also apply explicitly to the text and bar since Tailwind classes block inheritance
        const cdText = document.getElementById("btcCountdown");
        const cdBar = document.getElementById("btcCountdownBar");
        const cdLabels = cdPill.querySelectorAll("span");
        
        if (cdText) cdText.style.color = `rgb(${r}, ${g}, ${b})`;
        if (cdBar) {
            cdBar.style.backgroundColor = `rgb(${r}, ${g}, ${b})`;
            cdBar.style.boxShadow = `0 0 8px rgba(${r}, ${g}, ${b}, 0.6)`;
        }
        cdLabels.forEach(lbl => {
            if (lbl.id !== "btcCountdown") {
                lbl.style.color = `rgb(${r}, ${g}, ${b})`;
                if (lbl.classList.contains("bg-cyan-950/60")) {
                    lbl.style.backgroundColor = `rgba(${r}, ${g}, ${b}, 0.2)`;
                    lbl.style.borderColor = `rgba(${r}, ${g}, ${b}, 0.4)`;
                }
            }
        });
"""

content = content.replace("""
        cdPill.style.color = `rgb(${r}, ${g}, ${b})`;
        cdPill.style.borderColor = `rgba(${r}, ${g}, ${b}, 0.75)`;
        cdPill.style.backgroundColor = `rgba(${r}, ${g}, ${b}, 0.14)`;
        cdPill.style.boxShadow = `0 0 10px rgba(${r}, ${g}, ${b}, 0.3)`;
""".strip(), patch.strip())

with open('static/js/app.js', 'w', encoding='utf-8') as f:
    f.write(content)
