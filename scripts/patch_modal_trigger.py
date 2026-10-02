import re

def patch_modal_script(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the script block at the end that contains DOMContentLoaded
    pattern = re.compile(r"<script>\s*document\.addEventListener\('DOMContentLoaded', \(\) => \{\s*// 1\. Update Alert Logic.*?</script>", re.DOTALL)
    
    new_script = """<script>
(function() {
    // 1. Update Alert Logic (IIFE to avoid DOMContentLoaded timing issues)
    const updateVersion = 'v3.0_god_tier_alert'; 
    if (!localStorage.getItem(updateVersion)) {
        setTimeout(() => {
            const modal = document.getElementById('updateAlertModal');
            if (modal) {
                modal.classList.remove('hidden');
                modal.classList.add('flex');
                
                const modalContent = modal.querySelector('div');
                if (modalContent) {
                    modalContent.style.opacity = '0';
                    modalContent.style.transform = 'scale(0.95) translateY(10px)';
                    
                    requestAnimationFrame(() => {
                        modalContent.style.transition = 'all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)';
                        modalContent.style.opacity = '1';
                        modalContent.style.transform = 'scale(1) translateY(0)';
                    });
                }
            }
        }, 500); 
    }
})();

window.dismissUpdateAlert = function() {
    const modal = document.getElementById('updateAlertModal');
    if (modal) {
        const modalContent = modal.querySelector('div');
        if (modalContent) {
            modalContent.style.transform = 'scale(0.95) translateY(10px)';
            modalContent.style.opacity = '0';
        }
        
        setTimeout(() => {
            modal.classList.add('hidden');
            modal.classList.remove('flex');
            localStorage.setItem('v3.0_god_tier_alert', 'true');
        }, 300);
    }
};
</script>"""

    if pattern.search(content):
        content = pattern.sub(new_script, content)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched {filepath}")
    else:
        print(f"Pattern not found in {filepath}")

patch_modal_script(r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html")
patch_modal_script(r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\index.html")
