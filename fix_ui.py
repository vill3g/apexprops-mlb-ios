import re

path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    html = f.read()

# Fix 1: Remove dynamic island toggle
html = re.sub(r'<!-- Dynamic Island Toggle -->.*?</div>\s*</div>', '', html, flags=re.DOTALL)

# Fix 2: Remove duplicated trade execution panel
blocks = re.findall(r'(<!-- Trade Execution Panel -->.*?</div>\s*</div>\s*</div>)', html, flags=re.DOTALL)
if len(blocks) > 1:
    html = html.replace(blocks[1], '')

# Fix 3: Add swipe right to close settings
swipe_script = '''
<script>
document.addEventListener("DOMContentLoaded", function() {
    let touchStartX = 0;
    let touchEndX = 0;
    const settingsPanel = document.getElementById("settings-panel");
    
    if (settingsPanel) {
        settingsPanel.addEventListener("touchstart", e => {
            touchStartX = e.changedTouches[0].screenX;
        }, {passive: true});
        
        settingsPanel.addEventListener("touchend", e => {
            touchEndX = e.changedTouches[0].screenX;
            handleSwipe();
        }, {passive: true});
        
        function handleSwipe() {
            if (touchEndX - touchStartX > 100) { // Swipe right
                if (typeof closeSettings === "function") closeSettings();
                else if (settingsPanel.classList.contains("open")) settingsPanel.classList.remove("open");
            }
        }
    }
});
</script>
'''

if 'handleSwipe()' not in html:
    html = html.replace('</body>', swipe_script + '\n</body>')

with open(path, 'w', encoding='utf-8') as f:
    f.write(html)
