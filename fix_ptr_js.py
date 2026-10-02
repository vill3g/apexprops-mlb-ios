import re

js_path = "static/js/dashboard.js"
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

ptr_js = """
        // Pull to Refresh Logic
        let ptrStartY = 0;
        let isPulling = false;
        const ptrIndicator = document.getElementById('ptr-indicator');
        const ptrSpinner = document.getElementById('ptr-spinner');
        
        document.addEventListener('touchstart', (e) => {
            if (window.scrollY <= 0) {
                ptrStartY = e.touches[0].clientY;
                isPulling = true;
                if (ptrIndicator) ptrIndicator.style.transition = 'none';
            }
        }, { passive: true });

        document.addEventListener('touchmove', (e) => {
            if (!isPulling) return;
            const y = e.touches[0].clientY;
            if (y > ptrStartY && window.scrollY <= 0) {
                // Pulling down
                const pullDistance = Math.min((y - ptrStartY) * 0.4, 60);
                if (ptrIndicator) {
                    ptrIndicator.style.transform = `translateY(${pullDistance - 60}px)`;
                    ptrSpinner.style.transform = `rotate(${pullDistance * 4}deg)`;
                }
            } else {
                if (ptrIndicator) {
                    ptrIndicator.style.transition = 'transform 0.2s';
                    ptrIndicator.style.transform = 'translateY(-100%)';
                }
            }
        }, { passive: true });

        document.addEventListener('touchend', (e) => {
            if (!isPulling) return;
            isPulling = false;
            
            const pullDistance = (e.changedTouches[0].clientY - ptrStartY) * 0.4;
            if (ptrIndicator) {
                ptrIndicator.style.transition = 'transform 0.2s';
                if (pullDistance > 55 && window.scrollY <= 0) {
                    // Trigger refresh
                    ptrIndicator.style.transform = 'translateY(10px)';
                    ptrSpinner.classList.add('animate-spin');
                    setTimeout(() => {
                        location.reload();
                    }, 200);
                } else {
                    ptrIndicator.style.transform = 'translateY(-100%)';
                }
            }
        });
"""

# Match single or double quotes for DOMContentLoaded
pattern = r"document\.addEventListener\(['\"]DOMContentLoaded['\"], \(\) => \{"
replacement = r"document.addEventListener('DOMContentLoaded', () => {\n" + ptr_js

js = re.sub(pattern, replacement, js)

with open(js_path, "w", encoding="utf-8") as f:
    f.write(js)
print("Added JS PTR logic successfully!")
