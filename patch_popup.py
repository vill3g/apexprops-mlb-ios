with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Update the HTML
old_html = """            <div class="text-right flex flex-col items-end gap-1">
                <div class="flex items-center gap-2">
                    <div id="ml-status-bubble" class="px-1.5 py-[2px] rounded text-[8px] font-bold uppercase tracking-widest bg-gray-800 text-gray-400 border border-gray-600 shadow-sm transition-colors duration-300">AI: --</div>
                    <div id="kalshi-time" class="text-[11px] font-black text-kalshi-blue uppercase tracking-wider tabular-nums">--:-- LEFT</div>
                </div>
            </div>"""

new_html = """            <div class="text-right flex flex-col items-end gap-1 relative">
                <div class="flex items-center gap-2">
                    <div id="ml-status-bubble" onclick="toggleMLPopup(event)" class="cursor-pointer px-1.5 py-[2px] rounded text-[8px] font-bold uppercase tracking-widest bg-gray-800 text-gray-400 border border-gray-600 shadow-sm transition-colors duration-300 hover:scale-105 active:scale-95">AI: --</div>
                    <div id="kalshi-time" class="text-[11px] font-black text-kalshi-blue uppercase tracking-wider tabular-nums">--:-- LEFT</div>
                </div>
                
                <!-- AI Popup -->
                <div id="ml-details-popup" class="hidden absolute top-full right-0 mt-2 w-64 bg-black border border-kalshi-border rounded-lg shadow-[0_10px_30px_rgba(0,0,0,0.8)] z-50 p-4 text-left">
                    <div class="flex justify-between items-center border-b border-kalshi-border pb-2 mb-3">
                        <h3 class="text-[10px] font-bold text-kalshi-blue uppercase tracking-widest">GodTierEnsemble AI</h3>
                        <button onclick="toggleMLPopup(event)" class="text-gray-500 hover:text-white"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button>
                    </div>
                    <div class="space-y-2 text-[10px]">
                        <div class="flex justify-between"><span class="text-gray-500 font-bold tracking-wider">BIAS</span><span id="popup-bias" class="font-bold text-white">--</span></div>
                        <div class="flex justify-between"><span class="text-gray-500 font-bold tracking-wider">CONFIDENCE</span><span id="popup-conf" class="font-bold text-white">--</span></div>
                        <div class="flex justify-between"><span class="text-gray-500 font-bold tracking-wider">PROBABILITY</span><span id="popup-prob" class="font-bold text-white">--</span></div>
                    </div>
                    <div class="mt-3 pt-2 border-t border-kalshi-border">
                        <p id="popup-summary" class="text-[9px] text-gray-400 italic leading-relaxed">Waiting for AI analysis...</p>
                    </div>
                </div>
            </div>"""

c = c.replace(old_html, new_html)

# 2. Update JavaScript pollML
old_poll = """            if(res.ok) {
                const data = await res.json();
                const bubble = document.getElementById('ml-status-bubble');
                if(data.direction === 'ABOVE') {
                    bubble.innerText = 'AI: BUY YES';
                    bubble.className = 'px-1.5 py-[2px] rounded text-[8px] font-bold uppercase tracking-widest bg-green-900/40 text-emerald-400 border border-green-500/50 shadow-sm transition-colors duration-300 animate-pulse';
                } else if(data.direction === 'BELOW') {
                    bubble.innerText = 'AI: BUY NO';
                    bubble.className = 'px-1.5 py-[2px] rounded text-[8px] font-bold uppercase tracking-widest bg-red-900/40 text-red-400 border border-red-500/50 shadow-sm transition-colors duration-300 animate-pulse';
                } else {
                    bubble.innerText = 'AI: HOLD (CHOP)';
                    bubble.className = 'px-1.5 py-[2px] rounded text-[8px] font-bold uppercase tracking-widest bg-gray-800 text-gray-400 border border-gray-600 shadow-sm transition-colors duration-300';
                }
            }"""

new_poll = """            if(res.ok) {
                const data = await res.json();
                lastMLData = data;
                fillMLPopup();
                
                const bubble = document.getElementById('ml-status-bubble');
                if(data.direction === 'ABOVE') {
                    bubble.innerText = 'AI: BUY YES';
                    bubble.className = 'cursor-pointer px-1.5 py-[2px] rounded text-[8px] font-bold uppercase tracking-widest bg-green-900/40 text-emerald-400 border border-green-500/50 shadow-sm transition-colors duration-300 animate-pulse hover:scale-105 active:scale-95';
                } else if(data.direction === 'BELOW') {
                    bubble.innerText = 'AI: BUY NO';
                    bubble.className = 'cursor-pointer px-1.5 py-[2px] rounded text-[8px] font-bold uppercase tracking-widest bg-red-900/40 text-red-400 border border-red-500/50 shadow-sm transition-colors duration-300 animate-pulse hover:scale-105 active:scale-95';
                } else {
                    bubble.innerText = 'AI: HOLD (CHOP)';
                    bubble.className = 'cursor-pointer px-1.5 py-[2px] rounded text-[8px] font-bold uppercase tracking-widest bg-gray-800 text-gray-400 border border-gray-600 shadow-sm transition-colors duration-300 hover:scale-105 active:scale-95';
                }
            }"""

c = c.replace(old_poll, new_poll)

# 3. Add helper JS for popup
new_js = """
    let lastMLData = null;
    
    function toggleMLPopup(e) {
        if(e) e.stopPropagation();
        const popup = document.getElementById('ml-details-popup');
        popup.classList.toggle('hidden');
        fillMLPopup();
    }
    
    function fillMLPopup() {
        if(!lastMLData) return;
        document.getElementById('popup-bias').innerText = lastMLData.primary_bias || '--';
        document.getElementById('popup-conf').innerText = `${lastMLData.confidence_percent || 0}%`;
        document.getElementById('popup-prob').innerText = `${((lastMLData.predicted_probability || 0)*100).toFixed(1)}%`;
        
        let confColor = 'text-gray-400';
        if(lastMLData.confidence_percent >= 60) confColor = 'text-kalshi-green';
        else if(lastMLData.confidence_percent <= 40) confColor = 'text-kalshi-red';
        document.getElementById('popup-conf').className = `font-bold ${confColor}`;
        
        let summaryText = '';
        if(lastMLData.summary) {
            summaryText = lastMLData.summary;
        } else {
            summaryText = `Model predicts ${lastMLData.primary_bias} with ${((lastMLData.predicted_probability || 0)*100).toFixed(1)}% probability based on timeframe analysis.`;
        }
        document.getElementById('popup-summary').innerText = summaryText;
    }
    
    // Close popup if clicking outside
    document.addEventListener('click', (e) => {
        const popup = document.getElementById('ml-details-popup');
        const bubble = document.getElementById('ml-status-bubble');
        if(popup && !popup.classList.contains('hidden') && !popup.contains(e.target) && !bubble.contains(e.target)) {
            popup.classList.add('hidden');
        }
    });
"""

c = c.replace("</script>", new_js + "\n</script>")

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
