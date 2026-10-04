
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
