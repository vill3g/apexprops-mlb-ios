import re

file_path = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

modal_html = """
    <!-- Update Announcement Modal -->
    <div id="updateAnnouncementModal" class="hidden fixed inset-0 z-[200] items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" onclick="closeUpdateAnnouncement()"></div>
        <div class="bg-gradient-to-b from-[#1a233a] to-[#131b2c] border border-kalshi-blue/50 rounded-2xl p-5 shadow-2xl max-w-sm w-full relative z-10 transition-transform duration-300 transform scale-95 opacity-0" id="updateAnnouncementCard">
            
            <div class="flex items-center justify-center w-12 h-12 rounded-full bg-kalshi-blue/20 mb-4 mx-auto border border-kalshi-blue/30">
                <span class="text-2xl">??</span>
            </div>

            <h3 class="text-lg font-black text-white text-center mb-1">Update Available!</h3>
            <p class="text-xs text-kalshi-blue font-bold text-center uppercase tracking-widest mb-4">Version 2.5 is here</p>
            
            <div class="space-y-3 mb-6 text-sm text-gray-300">
                <div class="bg-black/30 p-3 rounded-xl border border-white/5">
                    <div class="font-bold text-white mb-1 flex items-center gap-2">
                        <span>??</span> AI Continuous Scalper
                    </div>
                    <div class="text-[11px] leading-relaxed text-gray-400">
                        A brand new Deep Q-Network strategy that continuously enters and exits positions <i>during</i> the 15-minute contract, actively hunting for unrealized PnL instead of holding until expiration. Enable it in <b>Settings -> Signal Source</b>.
                    </div>
                </div>
                
                <div class="bg-black/30 p-3 rounded-xl border border-white/5">
                    <div class="font-bold text-white mb-1 flex items-center gap-2">
                        <span>?</span> UI & UX Enhancements
                    </div>
                    <div class="text-[11px] leading-relaxed text-gray-400">
                        Settings have been streamlined. Auto-Trading Execution has been moved to the Active Trading Mode card, and API credentials now collapse by default to save screen space.
                    </div>
                </div>
            </div>

            <button onclick="closeUpdateAnnouncement()" class="w-full py-3 bg-kalshi-blue hover:bg-blue-600 text-white text-xs font-bold uppercase tracking-widest rounded-xl transition-colors shadow-lg shadow-kalshi-blue/20">
                Awesome, let's trade!
            </button>
        </div>
    </div>
"""

script_html = """
    // Update Announcement Logic
    const LATEST_UPDATE_ID = "v2.5_scalper_update";
    
    function checkUpdateAnnouncement() {
        const lastSeen = localStorage.getItem("kalshi_last_seen_update");
        if (lastSeen !== LATEST_UPDATE_ID) {
            setTimeout(() => {
                const modal = document.getElementById("updateAnnouncementModal");
                const card = document.getElementById("updateAnnouncementCard");
                if (modal && card) {
                    modal.classList.remove("hidden");
                    modal.classList.add("flex");
                    // Trigger reflow
                    void modal.offsetWidth;
                    card.classList.remove("scale-95", "opacity-0");
                    card.classList.add("scale-100", "opacity-100");
                }
            }, 1000); // Wait 1 second after page load
        }
    }

    function closeUpdateAnnouncement() {
        const modal = document.getElementById("updateAnnouncementModal");
        const card = document.getElementById("updateAnnouncementCard");
        if (modal && card) {
            card.classList.remove("scale-100", "opacity-100");
            card.classList.add("scale-95", "opacity-0");
            setTimeout(() => {
                modal.classList.add("hidden");
                modal.classList.remove("flex");
                localStorage.setItem("kalshi_last_seen_update", LATEST_UPDATE_ID);
            }, 300);
        }
    }
"""

if "updateAnnouncementModal" not in content:
    # insert html before last </body>
    content = content.replace("</body>", modal_html + "\n</body>")
    # insert js before last </script>
    # there might be multiple scripts. Just find the last one.
    idx = content.rfind("</script>")
    if idx != -1:
        content = content[:idx] + script_html + "\n" + content[idx:]
        
    # inject into DOMContentLoaded
    dom_hook = "document.addEventListener('DOMContentLoaded', () => {"
    if dom_hook in content:
        content = content.replace(dom_hook, dom_hook + "\n        checkUpdateAnnouncement();")
        
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Injected successfully.")
else:
    print("Already injected.")
